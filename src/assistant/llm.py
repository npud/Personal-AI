import ollama
from . import config

_client = ollama.Client(host=config.OLLAMA_HOST)

def generate(prompt: str, system: str | None = None) -> str:
    """One-shot text generation. The single seam the whole app talks to.
    Phase 3 adds a Claude backend behind this same signature."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = _client.chat(model=config.GEN_MODEL, messages=messages)
    return resp["message"]["content"]