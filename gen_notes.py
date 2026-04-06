import os
import json
import asyncio
from typing import List, Tuple

from pinecone import Pinecone
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv(override=True)

# /d:/Python/Hackathon/Study Buddy Backend/gen_notes.py
#
# This file now:
# 1. Takes a topic_name ("Operating Systems") and pinecone_id (namespace).
# 2. Generates a 3072-dimension embedding for the topic_name using Azure.
# 3. Queries the Pinecone namespace to get relevant text chunks.
# 4. Sorts chunks and passes them to the Azure Chat LLM to generate notes.

# --------- Pinecone connection ----------
def get_pinecone_index():
    """Connect to Pinecone using provided API key and index host."""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    host = os.getenv("PINECONE_HOST")
    if not host:
        raise ValueError("PINECONE_HOST environment variable not set or empty.")
    return pc.Index(host=host)


# --------- Azure OpenAI (LLM + Embeddings) ----------
def build_llm_notes() -> AzureChatOpenAI:
    """Build an Azure Chat LLM for notes generation."""
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        temperature=0,
        timeout=60,
        max_retries=2,
    )

def build_embeddings_client() -> AzureOpenAIEmbeddings:
    """Builds the client for text-embedding-3-large"""
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )

# --------- Retrieval from Pinecone ----------
def _extract_text_from_item(item: dict) -> str:
    """Get raw text from a Pinecone query result's metadata."""
    # We reliably stored the text in metadata.text in gen_topic.py
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
    # Default large numbers to push unknowns to the end
    page = int(page) if isinstance(page, int) else 10**9
    chunk_idx = int(chunk_idx) if isinstance(chunk_idx, int) else 10**9
    return (page, chunk_idx, -float(score)) # Sort by page, then chunk, then score


def aggregate_topic_content(pinecone_id: str, topic_name: str, top_k: int = 15) -> str:
    """Query Pinecone for a topic and return aggregated, sorted content."""
    
    index = get_pinecone_index()
    embed_client = build_embeddings_client()

    # 1. Create a 3072-dim vector for the query topic
    topic_vector = embed_client.embed_query(topic_name)

    # 2. Query Pinecone
    res = index.query(
        namespace=pinecone_id,
        top_k=top_k,
        include_values=False,
        include_metadata=True,
        vector=topic_vector,
    )

    items = res.get("matches", [])
    if not items:
        return ""

    # 3. Sort and concatenate
    unique_texts = []
    seen = set()

    try:
        items_sorted = sorted(items, key=_extract_sort_keys)
    except Exception:
        items_sorted = items

    for it in items_sorted:
        chunk_text = _extract_text_from_item(it).strip()
        if not chunk_text:
            continue
        key = chunk_text.replace("\n", " ").strip()
        if key and key not in seen:
            unique_texts.append(chunk_text)
            seen.add(key)

    return "\n\n".join(unique_texts)


# --------- Notes generation ----------
async def generate_notes_for_topic(pinecone_id: str, topic_name: str) -> str:
    """Retrieve content from Pinecone and produce concise study notes."""
    
    # Get a reasonable amount of context, sorted by page order
    content = aggregate_topic_content(pinecone_id, topic_name, top_k=15)
    if not content:
        raise ValueError("No relevant content found for the requested topic.")

    llm = build_llm_notes()

    # Keep within reasonable context size
    truncated = content[:20000]

    prompt = (
        f"Create well-structured study notes about the topic: '{topic_name}'.\n"
        "Use ONLY the provided source content. If a detail isn't in the content, omit it.\n"
        "Format as clean Markdown with sections, bullet points, and short examples when available.\n"
        "Include definitions, key ideas, steps, and important formulas using LaTeX when applicable.\n"
        "Return ONLY the notes, with no extra commentary or preface.\n\n"
        "SOURCE CONTENT BEGIN\n"
        f"{truncated}\n"
        "SOURCE CONTENT END"
    )

    resp = await asyncio.get_event_loop().run_in_executor(None, llm.invoke, prompt)
    notes = resp.content if hasattr(resp, "content") else str(resp)

    return notes.strip()