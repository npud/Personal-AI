import ollama
from . import config

_client = ollama.Client(host=config.OLLAMA_HOST)

def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    r = _client.embed(model=config.EMBED_MODEL, input = texts)
    return list(r["embeddings"])