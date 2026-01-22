import io
import os
import json
import uuid
import asyncio
from typing import List, Tuple
import httpx
from pypdf import PdfReader
from pinecone import Pinecone
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

# /d:/Python/Hackathon/Study Buddy Backend/gen_topic.py
#
# This file now:
# 1. Downloads and parses PDF.
# 2. Manually generates 3072-dimension embeddings using AZURE_OPENAI_EMBEDDING_DEPLOYMENT.
# 3. Upserts vectors and metadata (including raw text) to Pinecone using index.upsert().
# 4. Uses AzureChatOpenAI to identify topic names.

APP_NAME = "study-buddy-core"

# --------- PDF => text ---------
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


# --------- Text chunking ----------
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


# --------- Azure OpenAI (LLM + Embeddings) ----------
def build_llm_json() -> AzureChatOpenAI:
    # Force JSON object response for reliable parsing
    # LangChain automatically reads main Azure env vars (KEY, ENDPOINT, API_VERSION)
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
        timeout=60,
        max_retries=2,
    )

def build_embeddings_client() -> AzureOpenAIEmbeddings:
    """Builds the client for text-embedding-3-large"""
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        # LangChain will automatically pick up KEY, ENDPOINT, and API_VERSION
    )

# --------- Pinecone connection ----------
def get_pinecone_index():
    """Connect to Pinecone using provided API key and index host."""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    host = os.getenv("PINECONE_HOST")
    return pc.Index(host=host)


# --------- Topic extraction via LLM ----------
async def infer_topics(llm: AzureChatOpenAI, sample_text: str, max_topics: int = 12) -> List[str]:
    truncated = sample_text[:20000]
    prompt = (
        "You are given academic or technical content. "
        f"Identify the top {max_topics} distinct high-level topics covered. "
        "Return a JSON object with a single key 'topics' whose value is an array of concise topic names. "
        "Use 1-4 words per topic. No explanations."
        "\n\nCONTENT START\n"
        f"{truncated}\n"
        "CONTENT END"
    )
    try:
        resp = await asyncio.get_event_loop().run_in_executor(None, llm.invoke, prompt)
        txt = resp.content if hasattr(resp, "content") else str(resp)
        data = json.loads(txt)
        topics = data.get("topics", [])
        out = []
        seen = set()
        for t in topics:
            if not isinstance(t, str): continue
            s = t.strip()
            if s and s.lower() not in seen:
                out.append(s)
                seen.add(s.lower())
        return out[:max_topics] if out else []
    except Exception:
        return []

async def ingest_pdf_from_url(url: str) -> dict:
    """Pipeline to download a PDF, create Azure embeddings, upsert to Pinecone, and infer topics."""
    
    # 1) Fetch PDF
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(str(url))
        r.raise_for_status()
        pdf_bytes = r.content

    # 2) Extract text
    pages = extract_pdf_text(pdf_bytes)
    if not pages:
        raise ValueError("No extractable text found in PDF.")
    merged_text = "\n\n".join([f"[Page {p}] {t}" for p, t in pages])
    
    # 3) Generate a unique ID for this document. This will be our namespace.
    document_id = str(uuid.uuid4())

    # 4) Chunk text and format for embedding
    chunks_with_metadata = []
    chunk_counter = 0
    all_chunk_texts = []
    
    for page_num, page_text in pages:
        for i, chunk in enumerate(split_text(page_text)):
            all_chunk_texts.append(chunk)
            metadata = {
                "text": chunk,  # <-- CRUCIAL: Store raw text for gen_notes.py
                "source": str(url),
                "page": page_num,
                "chunk_index": i,
                "document_id": document_id
            }
            chunks_with_metadata.append((f"{document_id}-{chunk_counter:06d}", metadata))
            chunk_counter += 1
            
    if not all_chunk_texts:
        raise ValueError("No text chunks produced from PDF.")

    # 5) Build clients
    llm = build_llm_json()
    embed_client = build_embeddings_client()
    index = get_pinecone_index()

    # 6) Generate all embeddings in a batch
    embeddings = await asyncio.get_event_loop().run_in_executor(
        None, embed_client.embed_documents, all_chunk_texts
    )
    
    # 7) Format vectors for Pinecone upsert
    vectors_to_upsert = []
    for i, (vec_id, metadata) in enumerate(chunks_with_metadata):
        vectors_to_upsert.append((vec_id, embeddings[i], metadata))
        
    # 8) Upsert to Pinecone
    # Use index.upsert, not upsert_records
    for i in range(0, len(vectors_to_upsert), 100): # Upsert in batches of 100
        batch = vectors_to_upsert[i:i+100]
        index.upsert(
            vectors=batch,
            namespace=document_id
        )

    # 9) Infer topics
    topics = await infer_topics(llm, merged_text, max_topics=12)

    # 10) Return
    return {"pineconeID": document_id, "topicName": topics}