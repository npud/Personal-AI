# PersonAI

PersonAI is a local-first personal knowledge assistant that answers plain-language questions about your own data, starting with email. It parses an `.mbox` export, chunks and embeds each message, and stores the results in a local Chroma vector database. When you ask a question, it retrieves the most relevant passages and has a local LLM (via Ollama) synthesize an answer in which every claim cites a real source. The project is early: the LLM and embedding foundations are in place, the email parser is in progress, and the ingest and query pipeline is still to come.
