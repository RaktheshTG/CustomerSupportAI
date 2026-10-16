"""Retrieval-Augmented Generation over the CloudNest knowledge base.

The four .txt files in knowledge_base/ are split into chunks, embedded with a
local Ollama embedding model, and stored in a ChromaDB vector store. At query
time we embed the question and return the most similar chunks so the agent
answers from real company documents instead of making things up.
"""
from typing import List, Tuple

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import (
    KNOWLEDGE_BASE_DIR, VECTORSTORE_DIR, COLLECTION_NAME,
    EMBED_MODEL, OLLAMA_BASE_URL, CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVAL_K,
)

_embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def _load_documents() -> List[Document]:
    docs: List[Document] = []
    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        if text.strip():
            docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def _get_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_embeddings,
        persist_directory=str(VECTORSTORE_DIR),
    )


def build_vectorstore(force: bool = False) -> Chroma:
    """Build (or reuse) the vector store.

    If it already contains chunks and force is False, we reuse it so we don't
    re-embed on every run. Pass force=True to rebuild from scratch.
    """
    store = _get_store()
    try:
        existing = store._collection.count()
    except Exception:
        existing = 0

    if existing > 0 and not force:
        return store

    if force and existing > 0:
        # Clear the collection before re-ingesting.
        ids = store._collection.get()["ids"]
        if ids:
            store._collection.delete(ids=ids)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(_load_documents())
    if chunks:
        store.add_documents(chunks)
    return store


def retrieve(query: str, k: int = RETRIEVAL_K) -> Tuple[List[str], List[float]]:
    """Return (chunk_texts, distance_scores) for the query.

    Chroma returns a distance where LOWER means MORE similar. We surface the
    scores so the caller can log how confident the retrieval was.
    """
    store = _get_store()
    results = store.similarity_search_with_score(query, k=k)
    texts = [doc.page_content for doc, _ in results]
    scores = [float(score) for _, score in results]
    return texts, scores


if __name__ == "__main__":
    # Quick manual check: build the store and run a sample query.
    print("Building vector store...")
    build_vectorstore(force=True)
    print("Done. Sample query: 'how do I get a refund?'")
    texts, scores = retrieve("how do I get a refund?")
    for t, s in zip(texts, scores):
        print(f"\n[score={s:.3f}] {t[:200]}...")
