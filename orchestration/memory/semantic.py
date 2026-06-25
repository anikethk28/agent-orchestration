"""Long-term semantic memory backed by ChromaDB — persists across tasks."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import chromadb
import structlog
from langchain_openai import OpenAIEmbeddings

from orchestration.config import get_settings
from orchestration.graph.state import AgentState

log = structlog.get_logger()


def _get_collection():
    settings = get_settings()
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def _embedder():
    settings = get_settings()
    return OpenAIEmbeddings(api_key=settings.openai_api_key)


def save_task_memory(state: AgentState) -> None:
    """Extract and embed key learnings from a completed task."""
    if not state.final_output:
        return

    collection = _get_collection()
    embedder = _embedder()

    documents = []
    metadatas = []
    ids = []

    # Embed original request + final output as a single document
    summary = f"Task: {state.original_request}\n\nResult: {state.final_output[:800]}"
    docs_to_embed = [summary]

    # Also embed each subtask outcome
    for subtask in (state.plan.subtasks if state.plan else []):
        if subtask.output:
            docs_to_embed.append(
                f"Subtask ({subtask.specialist}): {subtask.description}\nOutput: {subtask.output[:400]}"
            )

    embeddings = embedder.embed_documents(docs_to_embed)

    for doc, emb in zip(docs_to_embed, embeddings):
        mem_id = str(uuid.uuid4())
        documents.append(doc)
        metadatas.append({
            "task_id": state.task_id,
            "user_id": state.user_id,
            "created_at": datetime.utcnow().isoformat(),
            "importance": 1.0,
            "access_count": 0,
        })
        ids.append(mem_id)

    collection.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)
    log.info("semantic_memory_saved", task_id=state.task_id, doc_count=len(documents))


def retrieve_relevant_memories(query: str, user_id: str = "default", n_results: int = 5) -> list[dict[str, Any]]:
    """Query ChromaDB for memories relevant to the current task."""
    collection = _get_collection()
    embedder = _embedder()

    query_embedding = embedder.embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"user_id": user_id} if user_id != "default" else None,
    )

    memories = []
    if results["documents"]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            memories.append({
                "summary": doc,
                "metadata": meta,
                "relevance_score": 1.0 - dist,
            })
            _increment_access_count(results["ids"][0][len(memories) - 1])

    log.info("memories_retrieved", query_preview=query[:80], count=len(memories))
    return memories


def _increment_access_count(memory_id: str) -> None:
    try:
        collection = _get_collection()
        result = collection.get(ids=[memory_id])
        if result["metadatas"]:
            meta = result["metadatas"][0]
            meta["access_count"] = meta.get("access_count", 0) + 1
            collection.update(ids=[memory_id], metadatas=[meta])
    except Exception:
        pass


def delete_user_memories(user_id: str) -> int:
    """GDPR-style: delete all memories for a user."""
    collection = _get_collection()
    results = collection.get(where={"user_id": user_id})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    log.info("user_memories_deleted", user_id=user_id, count=len(ids))
    return len(ids)


def get_memory_stats(user_id: str | None = None) -> dict[str, Any]:
    collection = _get_collection()
    where = {"user_id": user_id} if user_id else None
    results = collection.get(where=where)
    metas = results.get("metadatas", [])
    return {
        "total_memories": len(metas),
        "most_accessed": sorted(metas, key=lambda m: m.get("access_count", 0), reverse=True)[:5],
    }
