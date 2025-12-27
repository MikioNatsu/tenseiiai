import os, json, requests
import chromadb
from chromadb.config import Settings
from typing import List, Any, cast

OLLAMA_BASE = "http://localhost:11434"


def ollama_embed(text: str, model: str = "nomic-embed-text") -> List[float]:
    r = requests.post(
        f"{OLLAMA_BASE}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("embedding", [])


class OllamaEmbeddingFn:
    def __call__(self, input: List[str]) -> List[List[float]]:
        return [ollama_embed(x) for x in input]

    def embed_with_retries(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)


embed_fn = OllamaEmbeddingFn()

# Pylance bilan urushmaslik uchun Any qilamiz
_client: Any = None
_collection: Any = None


def get_collection(persist_dir: str = "data", name: str = "yuki_db"):
    global _client, _collection
    if _collection is not None:
        return _collection

    # Pylance ba'zan PersistentClient'ni "callable" deb ko'radi — shuning uchun cast qilamiz
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
    col = get_collection()
    res = col.query(query_texts=[query], n_results=k)
    docs = (res.get("documents") or [[]])[0]
    return docs
