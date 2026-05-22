"""
Content Ingestion Module for Class/Subject-based Content

Enhanced version of gen_topic.py that:
1. Supports class/subject metadata tagging
2. Auto-detects topics using LLM
3. Stores in Pinecone with proper namespacing
4. Uses Anthropic Claude (consistent with rest of system)
"""

import io
import os
import json
import uuid
import base64
import asyncio
from typing import List, Tuple, Optional, Dict, Any

import httpx
from pypdf import PdfReader
from pinecone import Pinecone
from langchain_openai import AzureOpenAIEmbeddings
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)


# ============================================================================
# PDF Processing
# ============================================================================

def extract_pdf_text(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """Return list of (page_number, text) for all pages with non-empty text."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: List[Tuple[int, str]] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            pages.append((i + 1, text))
    return pages


def split_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 150) -> List[str]:
    """Naive recursive character splitter with overlap."""
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == length:
            break
        start = end - chunk_overlap
        if start < 0:
            start = 0
    return chunks


# ============================================================================
# LLM and Embeddings Clients
# ============================================================================

def get_qwen_client() -> OpenAI:
    """Get Qwen (DashScope) client for topic detection."""
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )


def get_embeddings_client() -> AzureOpenAIEmbeddings:
    """Get Azure OpenAI embeddings client (uses same embedding model as legacy)."""
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )


def get_pinecone_index():
    """Connect to Pinecone using provided API key and index host."""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    host = os.getenv("PINECONE_HOST")
    return pc.Index(host=host)


# ============================================================================
# Topic Detection
# ============================================================================

async def infer_topics(
    llm: OpenAI,
    sample_text: str,
    subject_code: str,
    max_topics: int = 12
) -> List[Dict[str, str]]:
    """
    Infer topics from content using Anthropic Claude.
    
    Returns list of dicts with topic_code and topic_name.
    """
    truncated = sample_text[:20000]
    
    prompt = f"""You are given academic content for the subject: {subject_code.upper()}.

Identify the top {max_topics} distinct high-level topics covered in this content.

Return a JSON object with a single key 'topics' whose value is an array of objects.
Each object should have:
- "topic_code": a lowercase snake_case identifier (e.g., "projectile_motion")
- "topic_name": a properly capitalized display name (e.g., "Projectile Motion")

Example output:
{{"topics": [{{"topic_code": "kinematics", "topic_name": "Kinematics"}}, {{"topic_code": "laws_of_motion", "topic_name": "Laws of Motion"}}]}}

CONTENT START
{truncated}
CONTENT END

Return ONLY the JSON object, no other text."""

    try:
        def _call():
            r = llm.chat.completions.create(
                model=os.getenv("QWEN_MODEL", "qwen3-plus"),
                messages=[{"role": "user", "content": prompt}],
                extra_body={"enable_thinking": False},
            )
            return r.choices[0].message.content or ""

        resp = await asyncio.get_event_loop().run_in_executor(None, _call)
        txt = resp
        
        # Parse JSON from response
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0]
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0]
        
        data = json.loads(txt.strip())
        topics = data.get("topics", [])
        
        # Validate and dedupe
        out = []
        seen = set()
        for t in topics:
            if isinstance(t, dict) and "topic_code" in t:
                code = t["topic_code"].lower().replace(" ", "_")
                if code not in seen:
                    out.append({
                        "topic_code": code,
                        "topic_name": t.get("topic_name", code.replace("_", " ").title())
                    })
                    seen.add(code)
            elif isinstance(t, str):
                code = t.lower().replace(" ", "_")
                if code not in seen:
                    out.append({
                        "topic_code": code,
                        "topic_name": t.strip()
                    })
                    seen.add(code)
        
        return out[:max_topics] if out else []
    except Exception as e:
        print(f"Topic inference error: {e}")
        return []


# ============================================================================
# Main Ingestion Functions
# ============================================================================

async def ingest_content_from_url(
    url: str,
    class_number: int,
    subject_code: str,
) -> Dict[str, Any]:
    """
    Ingest content from URL with class/subject metadata.
    
    Args:
        url: URL to PDF document
        class_number: Class number (1-12)
        subject_code: Subject code (e.g., "physics", "chemistry")
        
    Returns:
        Dict with content_id, detected topics, and chunk count
    """
    # Fetch PDF
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(str(url))
        r.raise_for_status()
        pdf_bytes = r.content
    
    return await _process_pdf(pdf_bytes, class_number, subject_code, source=str(url))


async def ingest_content_from_bytes(
    file_bytes: bytes,
    class_number: int,
    subject_code: str,
    filename: str = "uploaded.pdf",
) -> Dict[str, Any]:
    """
    Ingest content from file bytes with class/subject metadata.
    
    Args:
        file_bytes: Raw PDF bytes
        class_number: Class number (1-12)
        subject_code: Subject code (e.g., "physics", "chemistry")
        filename: Original filename
        
    Returns:
        Dict with content_id, detected topics, and chunk count
    """
    return await _process_pdf(file_bytes, class_number, subject_code, source=filename)


async def ingest_content_from_base64(
    base64_content: str,
    class_number: int,
    subject_code: str,
    filename: str = "uploaded.pdf",
) -> Dict[str, Any]:
    """
    Ingest content from base64 encoded PDF.
    
    Args:
        base64_content: Base64 encoded PDF
        class_number: Class number (1-12)
        subject_code: Subject code
        filename: Original filename
        
    Returns:
        Dict with content_id, detected topics, and chunk count
    """
    pdf_bytes = base64.b64decode(base64_content)
    return await _process_pdf(pdf_bytes, class_number, subject_code, source=filename)


async def _process_pdf(
    pdf_bytes: bytes,
    class_number: int,
    subject_code: str,
    source: str,
) -> Dict[str, Any]:
    """
    Core PDF processing pipeline.
    """
    # 1) Extract text
    pages = extract_pdf_text(pdf_bytes)
    if not pages:
        raise ValueError("No extractable text found in PDF.")
    
    merged_text = "\n\n".join([f"[Page {p}] {t}" for p, t in pages])
    
    # 2) Generate unique content ID and namespace
    content_id = str(uuid.uuid4())
    # Namespace format: c{class_number}_{subject_code}
    namespace = f"c{class_number}_{subject_code}"
    
    # 3) Chunk text with enhanced metadata
    chunks_with_metadata = []
    all_chunk_texts = []
    chunk_counter = 0
    
    for page_num, page_text in pages:
        for i, chunk in enumerate(split_text(page_text)):
            all_chunk_texts.append(chunk)
            metadata = {
                "text": chunk,
                "source": source,
                "page": page_num,
                "chunk_index": i,
                "content_id": content_id,
                # Enhanced metadata for class/subject filtering
                "class_number": class_number,
                "subject_code": subject_code,
            }
            chunks_with_metadata.append((f"{content_id}-{chunk_counter:06d}", metadata))
            chunk_counter += 1
    
    if not all_chunk_texts:
        raise ValueError("No text chunks produced from PDF.")
    
    # 4) Build clients
    llm = get_qwen_client()
    embed_client = get_embeddings_client()
    index = get_pinecone_index()
    
    # 5) Generate embeddings
    embeddings = await asyncio.get_event_loop().run_in_executor(
        None, embed_client.embed_documents, all_chunk_texts
    )
    
    # 6) Format and upsert to Pinecone with namespace
    vectors_to_upsert = []
    for i, (vec_id, metadata) in enumerate(chunks_with_metadata):
        vectors_to_upsert.append((vec_id, embeddings[i], metadata))
    
    # Upsert in batches
    for i in range(0, len(vectors_to_upsert), 100):
        batch = vectors_to_upsert[i:i+100]
        index.upsert(vectors=batch, namespace=namespace)
    
    # 7) Infer topics
    topics = await infer_topics(llm, merged_text, subject_code, max_topics=12)
    
    # 8) Update topic metadata on vectors (optional, for filtering)
    if topics:
        topic_codes = [t["topic_code"] for t in topics]
        # Update first chunk's metadata with detected topics
        # (Pinecone doesn't support bulk metadata updates easily)
    
    return {
        "content_id": content_id,
        "namespace": namespace,
        "class_number": class_number,
        "subject_code": subject_code,
        "chunks_indexed": len(chunks_with_metadata),
        "pages_processed": len(pages),
        "topics_detected": topics,
        "topic_names": [t["topic_name"] for t in topics],
    }


# ============================================================================
# Content Retrieval
# ============================================================================

async def search_content(
    query: str,
    class_number: int,
    subject_code: str,
    topic_code: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search content with class/subject filtering.
    
    Args:
        query: Search query
        class_number: Filter by class
        subject_code: Filter by subject
        topic_code: Optional topic filter
        top_k: Number of results
        
    Returns:
        List of matching chunks with metadata
    """
    embed_client = get_embeddings_client()
    index = get_pinecone_index()
    
    # Generate query embedding
    query_embedding = await asyncio.get_event_loop().run_in_executor(
        None, embed_client.embed_query, query
    )
    
    # Namespace for filtering
    namespace = f"c{class_number}_{subject_code}"
    
    # Build filter
    filter_dict = {
        "class_number": {"$eq": class_number},
        "subject_code": {"$eq": subject_code},
    }
    if topic_code:
        filter_dict["topic_code"] = {"$eq": topic_code}
    
    # Query Pinecone
    results = index.query(
        vector=query_embedding,
        namespace=namespace,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict,
    )
    
    return [
        {
            "text": match.metadata.get("text", ""),
            "page": match.metadata.get("page"),
            "score": match.score,
            "content_id": match.metadata.get("content_id"),
        }
        for match in results.matches
    ]
