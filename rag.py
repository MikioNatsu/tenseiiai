import os, json, requests
import chromadb
from chromadb.config import Settings
from typing import List, Any, cast, Optional, Dict

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

_session = requests.Session()

def _try_embed(endpoint: str, text: str) -> Optional[List[float]]:
    url = f"{OLLAMA_BASE}{endpoint}"

    if endpoint == "/api/embeddings":
        payload: Dict[str, Any] = {"model": EMBED_MODEL, "prompt": text}
    else:
        payload = {"model": EMBED_MODEL, "input": text}

    r = _session.post(url, json=payload, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()

    # normalize possible responses
    if isinstance(data.get("embedding"), list):
        return data["embedding"]
    if isinstance(data.get("embeddings"), list) and data["embeddings"]:
        return data["embeddings"][0]
    if isinstance(data.get("data"), list) and data["data"]:
        emb = data["data"][0].get("embedding")
        if isinstance(emb, list):
            return emb

    raise RuntimeError(f"Unexpected embedding response keys={list(data.keys())}")

def ollama_embed(text: str) -> List[float]:
    # try both endpoints (covers different Ollama versions)
    emb = _try_embed("/api/embed", text)
    if emb is not None:
        return emb
    emb = _try_embed("/api/embeddings", text)
    if emb is not None:
        return emb
    raise RuntimeError("No supported Ollama embedding endpoint found.")

class OllamaEmbeddingFn:
    def __call__(self, input: List[str]) -> List[List[float]]:
        return [ollama_embed(x) for x in input]

    def embed_with_retries(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

embed_fn = OllamaEmbeddingFn()

_client: Any = None
_collection: Any = None

def get_collection(persist_dir: str = "data", name: str = "yuki_db"):
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = cast(
        Any,
        chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        ),
    )

    _collection = _client.get_or_create_collection(
        name=name,
        embedding_function=embed_fn,  # type: ignore[arg-type]
    )
    return _collection

def load_kb_docs() -> List[dict]:
    docs: List[dict] = []

    for fn in ["tenseii_rules.md", "tenseii_faq.md"]:
        path = os.path.join("kb", fn)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                docs.append({"id": fn, "text": f.read(), "meta": {"source": fn}})

    jpath = os.path.join("kb", "anime_catalog.json")
    if os.path.exists(jpath):
        with open(jpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for i, a in enumerate(data[:3000]):
            title = a.get("title", f"anime_{i}")
            mood = a.get("mood", "")
            genres = a.get("genres", [])
            genres_str = ", ".join(genres) if isinstance(genres, list) else str(genres)
            desc = a.get("description", "")
            text = f"TITLE: {title}\nGENRES: {genres_str}\nMOOD: {mood}\nDESC: {desc}".strip()

            docs.append(
                {
                    "id": f"anime_{i}_{title}",
                    "text": text,
                    "meta": {"source": "anime_catalog.json"},
                }
            )

    return docs

def ingest_all():
    col = get_collection()
    docs = load_kb_docs()
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metas = [d["meta"] for d in docs]

    try:
        col.delete(ids=ids)
    except Exception:
        pass

    col.add(ids=ids, documents=texts, metadatas=metas)

def retrieve(query: str, k: int = 4) -> List[str]:
    try:
        col = get_collection()
        res = col.query(query_texts=[query], n_results=k)
        docs = (res.get("documents") or [[]])[0]
        return docs
    except Exception as e:
        print(f"[RAG] retrieve failed (fallback to empty): {e}")
        return []
