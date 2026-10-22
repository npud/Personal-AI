import hashlib
import mailbox
import re
import sys
from email.utils import parsedate_to_datetime
from email.header import decode_header
from html import unescape

def decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)

def getBody(msg) -> str:
    """Extract the best text body, preferring text/plain but distrusting its label.

    Some senders label an HTML body as text/plain, so a plain part that looks
    like markup is rejected in favour of a real text/html sibling.
    """
    if msg.is_multipart():
        fallback = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                text = _decode_part(part)
                if looksLikeHtml(text):
                    fallback = fallback or text   # mislabelled: try the html part
                    continue
                return stripStrayTags(text)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return stripHtml(_decode_part(part))
        return stripHtml(fallback) if fallback else ""
    text = _decode_part(msg)
    if msg.get_content_type() == "text/html" or looksLikeHtml(text):
        return stripHtml(text)
    return stripStrayTags(text)

def _decode_part(part) -> str:
    payload = part.get_payload(decode=True) or b""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")

# Tags common in mail markup. Restricted to a known set so plain text keeps
# things like <noreply@example.com> and "a < b".
tag = r"</?(?:html|head|body|title|meta|link|style|script|div|span|table|tbody|thead|tr|td|th|p|br|hr|a|img|b|i|u|em|strong|font|center|ul|ol|li|h[1-6]|o:p|v:\w+)\b[^>]*>"
comment = r"<!--.*?-->|<!\[endif\]-->|<!doctype[^>]*>"

def looksLikeHtml(text: str) -> bool:
    head = text.lstrip()[:200].lower()
    if head.startswith(("<!doctype", "<html", "<head", "<body", "<table", "<div")):
        return True
    return len(re.findall(tag, text, re.I)) >= 10

def stripStrayTags(text: str) -> str:
    """Plain text that carries a few embedded tags/conditional comments."""
    text = re.sub(comment, "", text, flags=re.S | re.I)
    text = re.sub(tag, "", text, flags=re.I)
    return _collapse(unescape(text))

def stripHtml(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(comment, " ", html, flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|tr|li|h[1-6])\s*>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _collapse(unescape(html))

def _collapse(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

miniContentWords = 12

url = re.compile(r"""(?xi)
    <\s*(?:https?://|www\.|mailto:)[^\s<>"')\]]*\s*>  # angle-bracketed, incl. empty <mailto:>
  | \b(?:https?://|www\.)[^\s<>"')\]]+                 # bare http(s) / www links
  | \bmailto:[^\s<>"')\]]*                             # bare mailto:
""")

# The nav/footer link labels left behind once their href is gone.
chromeLabel = r"""(?:
    unsubscribe(?:\s+here)?
  | manage\s+(?:your\s+)?(?:preferences|subscriptions?|email\s+preferences)
  | (?:email|notification|communication)\s+(?:preferences|settings)
  | opt[\s-]?out
  | view\s+(?:this\s+)?(?:e-?mail\s+)?in\s+(?:your\s+)?browser
  | view\s+as\s+(?:a\s+)?web\s*page
  | privacy\s+(?:policy|notice|statement)
  | terms\s+(?:and|&|of)\s+(?:conditions|use|service)
  | cookie\s+(?:policy|preferences)
  | help\s+(?:cent(?:er|re)|desk)
  | contact\s+us
  | add\s+us\s+to\s+your\s+address\s+book
)"""

# A line that is nothing but those labels, singly or in a "|" separated row
# ("Privacy Policy | Contact Us"), which is how footer link bars arrive.
chromeLine = re.compile(
    r"^\s*" + chromeLabel + r"(?:\s*[|·•]\s*" + chromeLabel + r")*[\s.|]*$",
    re.X | re.I,
)

# Link labels: a line that is nothing but a short bracketed phrase. Covers both
# "[Unsubscribe]" and "[image: Google]" — Gmail's plain-text form for a link.
linkLabelLine = re.compile(r"^\s*\[[^\]]{1,60}\]\s*$")

# Street-address footers, e.g. "3721 N. Clark St., Chicago, IL 60613"
addressLine = re.compile(
    r"^\s*\d+\s+[\w.'\- ]+,\s*[\w.'\- ]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?\.?\s*$"
)

# Separator debris left behind by stripped link rows: "|", "-----", "·"
separatorLine = re.compile(r"^\s*[|•·*\-=_~]+\s*$")

# Legal/list-management sentences. These soft-wrap across several lines, so
# they are matched against a whole paragraph and swallow the rest of it.
chromeBlock = re.compile(r"""(?xis)^\s*(?:
    (?:copyright\s*)?(?:\(c\)|©)
  | all\s+rights\s+reserved
  | you(?:'re|’re|\s+are)?\s+(?:have\s+)?receiv(?:ed|ing)\s+this
  | this\s+(?:e-?mail|message)\s+(?:was\s+sent|is\s+intended)
  | (?:please\s+)?do\s+not\s+reply\s+to\s+this
  | if\s+you\s+(?:no\s+longer\s+wish|would\s+prefer\s+not)\s+to
  | to\s+(?:stop|unsubscribe\s+from)\s+receiving
  | sent\s+(?:to\s+you\s+)?by\s+\S+\s+on\s+behalf\s+of
)""")

contentWord = re.compile(r"[A-Za-z0-9'’]{2,}")


def stripUrls(text: str) -> str:
    """Drop link targets and tracking URLs"""
    text = url.sub(" ", text)
    text = re.sub(r" +([.,;:!?])", r"\1", text)   # close the gap a stripped link left
    return _collapse(text)


def stripChrome(text: str) -> str:
    """Drop nav labels, legal footers and the separator debris between them."""
    kept_blocks = []
    for block in re.split(r"\n\s*\n", text):
        if chromeBlock.match(block):
            continue
        lines = [
            line for line in block.splitlines()
            if not (chromeLine.match(line)
                    or linkLabelLine.match(line)
                    or addressLine.match(line)
                    or separatorLine.match(line))
        ]
        if lines:
            kept_blocks.append("\n".join(lines))
    return _collapse("\n\n".join(kept_blocks))


def contentWords(text: str) -> int:
    return len(contentWord.findall(text))


def cleanBody(text: str) -> str:
    """Remove quoted replies and signatures so we keep only what was written."""
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        # quoted history: lines starting with ">"
        if stripped.startswith(">"):
            continue
        # "On <date>, <person> wrote:" reply headers — stop here, rest is quote
        if re.match(r"^On .+wrote:$", stripped):
            break
        # signature delimiter
        if stripped == "--":
            break
        # forwarded/original-message banners
        if re.match(r"^-+\s*(Original Message|Forwarded message)\s*-+$",
                    stripped, re.I):
            break
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)   # collapse blank runs
    return cleaned.strip()


def parseMbox(path: str) -> list[dict]:
    """Return a list of message documents with metadata + cleaned body."""
    box = mailbox.mbox(path)
    docs = []
    skipped = 0
    for msg in box:
        try:
            date = parsedate_to_datetime(msg.get("Date"))
            date_iso = date.isoformat() if date else ""
        except Exception:
            date_iso = ""

        body = stripChrome(stripUrls(cleanBody(getBody(msg))))
        if contentWords(body) < miniContentWords:
            skipped += 1
            continue   # empty, attachment-only, or nothing but mail chrome

        sender = decode(msg.get("From"))
        subject = decode(msg.get("Subject"))
        msg_id = (msg.get("Message-ID") or "").strip().strip("<>")
        if not msg_id:
            # No Message-ID: hash the content so the ID stays stable across
            # re-runs (a positional "noid-N" would shift if the export changes,
            # breaking upsert idempotency).
            msg_id = "noid-" + hashlib.sha1(
                f"{sender}|{date_iso}|{subject}|{body[:200]}".encode()
            ).hexdigest()[:16]

        docs.append({
            "id": msg_id,
            "sender": sender,
            "recipients": decode(msg.get("To")),
            "date": date_iso,
            "subject": subject,
            # thread linkage — free at parse time, Phase 5 synthesis needs it
            "in_reply_to": (msg.get("In-Reply-To") or "").strip(),
            "references": (msg.get("References") or "").strip(),
            "body": body,
        })
    if skipped:
        # stderr so a caller piping the parse output stays unpolluted
        print(f"skipped {skipped} low-content messages", file=sys.stderr)
    return docs


if __name__ == "__main__":
    from . import config
    docs = parseMbox(str(config.RAW_DIR / "export.mbox"))
    print(f"Parsed {len(docs)} messages")
    if docs:
        d = docs[0]
        print("---")
        print("From:", d["sender"])
        print("Date:", d["date"])
        print("Subject:", d["subject"])
        print("Body (first 400 chars):\n", d["body"][:400])
  