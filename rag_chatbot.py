"""
RAG Chatbot module

This module implements a retrieval-augmented chatbot over a Pinecone namespace
(identified by pineconeID). It keeps in-memory session history per pineconeID
so follow-up questions can reference prior turns.

Dependencies and env vars (same as other modules in this repo):
- PINECONE_API_KEY
- PINECONE_HOST  (index host URL)
- AZURE_OPENAI_DEPLOYMENT_NAME            (chat model deployment)
- AZURE_OPENAI_EMBEDDING_DEPLOYMENT       (embedding model deployment)
"""

from __future__ import annotations

import os
import asyncio
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

load_dotenv(override=True)


# --------------------------- Pinecone connection ---------------------------
def get_pinecone_index():
	pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
	host = os.getenv("PINECONE_HOST")
	if not host:
		raise ValueError("PINECONE_HOST environment variable not set or empty.")
	return pc.Index(host=host)


# --------------------------- Azure OpenAI clients --------------------------
def build_llm_chat() -> AzureChatOpenAI:
	return AzureChatOpenAI(
		azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
		temperature=0.2,
		timeout=60,
		max_retries=2,
	)


def build_embeddings_client() -> AzureOpenAIEmbeddings:
	return AzureOpenAIEmbeddings(
		azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
	)


# --------------------------- Utilities & parsing ---------------------------
def _extract_text_from_item(item: dict) -> str:
	meta = item.get("metadata") or {}
	if isinstance(meta, dict):
		txt = meta.get("text")
		if isinstance(txt, str) and txt.strip():
			return txt
	return ""


def _extract_sort_keys(item: dict) -> Tuple[int, int, float]:
	meta = item.get("metadata") or {}
	page = meta.get("page")
	chunk_idx = meta.get("chunk_index")
	score = item.get("score") or 0.0
	page = int(page) if isinstance(page, int) else 10**9
	chunk_idx = int(chunk_idx) if isinstance(chunk_idx, int) else 10**9
	return (page, chunk_idx, -float(score))


def _unique_sorted_texts(items: List[dict]) -> List[str]:
	if not items:
		return []
	try:
		items_sorted = sorted(items, key=_extract_sort_keys)
	except Exception:
		items_sorted = items

	texts: List[str] = []
	seen = set()
	for it in items_sorted:
		chunk_text = _extract_text_from_item(it).strip()
		if not chunk_text:
			continue
		key = chunk_text.replace("\n", " ").strip()
		if key and key not in seen:
			texts.append(chunk_text)
			seen.add(key)
	return texts


# --------------------------- Retrieval pipeline ---------------------------
def retrieve_context(pinecone_id: str, query: str, top_k: int = 8, max_chars: int = 20000) -> str:
	"""Retrieve relevant context for a query from Pinecone namespace.

	Returns a concatenated string of unique, sorted text chunks capped to max_chars.
	"""
	index = get_pinecone_index()
	embed_client = build_embeddings_client()

	query_vec = embed_client.embed_query(query)
	res = index.query(
		namespace=pinecone_id,
		top_k=top_k,
		include_values=False,
		include_metadata=True,
		vector=query_vec,
	)

	items = res.get("matches", [])
	texts = _unique_sorted_texts(items)
	if not texts:
		return ""
	context = "\n\n".join(texts)
	return context[:max_chars]


# --------------------------- Session memory -------------------------------
_SESSION_HISTORY: Dict[str, List[Dict[str, str]]] = {}
_LOCKS: Dict[str, asyncio.Lock] = {}


def _get_lock(pinecone_id: str) -> asyncio.Lock:
	if pinecone_id not in _LOCKS:
		_LOCKS[pinecone_id] = asyncio.Lock()
	return _LOCKS[pinecone_id]


def reset_session(pinecone_id: str) -> None:
	"""Clear the in-memory chat history for a given pineconeID."""
	_SESSION_HISTORY.pop(pinecone_id, None)


def get_session_history(pinecone_id: str) -> List[Dict[str, str]]:
	"""Return the full message history for a session (list of {role, content})."""
	return list(_SESSION_HISTORY.get(pinecone_id, []))


def _format_history_for_prompt(history: List[Dict[str, str]], max_messages: int = 12) -> str:
	"""Render the most recent messages as plain text for the prompt."""
	if not history:
		return ""
	# Keep the most recent N messages
	recent = history[-max_messages:]
	lines = ["Conversation history (most recent last):"]
	for msg in recent:
		role = msg.get("role", "user").capitalize()
		content = msg.get("content", "").strip()
		lines.append(f"{role}: {content}")
	return "\n".join(lines)


# --------------------------- Chat entry point -----------------------------
async def chat_query(
	pinecone_id: str,
	user_query: str,
	*,
	top_k: int = 8,
	max_history_messages: int = 12,
	max_context_chars: int = 20000,
) -> str:
	"""Answer a user query using RAG over the given Pinecone namespace.

	Session history is tracked in-memory by pineconeID. History is appended
	after each successful answer.
	"""

	lock = _get_lock(pinecone_id)
	async with lock:
		history = _SESSION_HISTORY.setdefault(pinecone_id, [])

		# 1) Retrieve relevant context for this query
		context = retrieve_context(pinecone_id, user_query, top_k=top_k, max_chars=max_context_chars)

		# 2) Build prompt including system guidance, conversation history, and context
		system_preamble = (
			"You are a helpful study assistant. Answer strictly using the provided\n"
			"document context from the student's study materials. If the context\n"
			"does not contain the answer, say you don't know and suggest a\n"
			"clarifying question. Keep answers concise and accurate. Use Markdown\n"
			"formatting and LaTeX for math when helpful.\n"
		)

		history_block = _format_history_for_prompt(history, max_messages=max_history_messages)
		context_block = context if context else "(No highly relevant passages were retrieved.)"

		prompt = (
			f"{system_preamble}\n"
			f"{history_block}\n\n"
			f"User question: {user_query}\n\n"
			"Relevant context from documents:\n"
			"CONTEXT BEGIN\n"
			f"{context_block}\n"
			"CONTEXT END\n\n"
			"Instructions:\n"
			"- Base your answer ONLY on the context above.\n"
			"- If the answer is not in the context, say you don't know.\n"
			"- Keep it clear, step-by-step when useful, and correct.\n"
		)

		# 3) Call the chat model
		llm = build_llm_chat()
		resp = await asyncio.get_event_loop().run_in_executor(None, llm.invoke, prompt)
		answer = resp.content if hasattr(resp, "content") else str(resp)
		answer = (answer or "").strip()

		# 4) Update history (user + assistant turn)
		history.append({"role": "user", "content": user_query})
		history.append({"role": "assistant", "content": answer})

		return answer


# --------------------------- Optional helpers -----------------------------
async def quick_answer(pinecone_id: str, query: str) -> str:
	"""Convenience wrapper around chat_query with defaults."""
	return await chat_query(pinecone_id, query)

