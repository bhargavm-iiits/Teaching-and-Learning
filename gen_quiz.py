import os
import json
import asyncio
from typing import List, Tuple, Dict, Any

from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

load_dotenv()


# ------------------------ Pinecone connection ------------------------
def get_pinecone_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    host = os.getenv("PINECONE_HOST")
    if not host:
        raise ValueError("PINECONE_HOST environment variable not set or empty.")
    return pc.Index(host=host)


# ------------------------ Azure OpenAI clients -----------------------
def build_llm_quiz() -> AzureChatOpenAI:
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


# ------------------------ Retrieval helpers --------------------------
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


def retrieve_topic_context(pinecone_id: str, topic_name: str, top_k: int = 20, max_chars: int = 20000) -> str:
    index = get_pinecone_index()
    embed_client = build_embeddings_client()

    topic_vec = embed_client.embed_query(topic_name)
    res = index.query(
        namespace=pinecone_id,
        top_k=top_k,
        include_values=False,
        include_metadata=True,
        vector=topic_vec,
    )
    items = res.get("matches", [])
    texts = _unique_sorted_texts(items)
    if not texts:
        return ""
    return "\n\n".join(texts)[:max_chars]


# ------------------------ Quiz generation ----------------------------
def _build_quiz_prompt(topic_name: str, difficulty: str, num_questions: int, context: str) -> str:
    difficulty = (difficulty or "medium").lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    # Use .format but escape JSON braces with double braces.
    schema_block = (
        "{{\n"
        "  \"title\": \"{topic_name} Quiz\",\n"
        "  \"questions\": [\n"
        "    {{\n"
        "      \"question_text\": \"...\",\n"
        "      \"options\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"],\n"
        "      \"correct_answer\": \"C) ...\"\n"
        "    }}\n"
        "  ]\n"
        "}}"
    ).format(topic_name=topic_name)

    return (
        "You are a knowledgeable quiz generator.\n"
        "Create a multiple-choice quiz strictly based on the provided source context.\n"
        "- Do NOT invent facts not present in the context.\n"
        f"- Difficulty level: {difficulty}.\n"
        f"- Number of questions: {num_questions}.\n"
        "- Each question must have exactly four options labeled 'A)', 'B)', 'C)', 'D)'.\n"
        "- Ensure only one correct answer per question.\n"
        "- The correct_answer field MUST equal exactly one of the option strings.\n"
        "- Keep wording clear and concise.\n\n"
        "Return ONLY a valid JSON object matching this schema, with no extra text:\n"
        f"{schema_block}\n\n"
        "SOURCE CONTEXT BEGIN\n"
        f"{context}\n"
        "SOURCE CONTEXT END\n"
    )


def _coerce_json(text: str) -> Dict[str, Any]:
    """Best-effort to parse JSON from model output."""
    text = (text or "").strip()
    # Fast path
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to extract the first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            pass

    raise ValueError("Failed to parse quiz JSON from model output.")


def _validate_and_fix_quiz(doc: Dict[str, Any], expected_count: int) -> Dict[str, Any]:
    """Validate minimal schema and try small fixes: enforce 4 options and correct_answer match."""
    if not isinstance(doc, dict):
        raise ValueError("Quiz output is not a JSON object.")
    title = doc.get("title")
    questions = doc.get("questions")
    if not isinstance(title, str) or not isinstance(questions, list) or not questions:
        raise ValueError("Quiz JSON missing 'title' or 'questions'.")

    fixed_questions = []
    for q in questions[:expected_count]:
        if not isinstance(q, dict):
            continue
        qtext = q.get("question_text")
        options = q.get("options")
        answer = q.get("correct_answer")
        if not isinstance(qtext, str) or not isinstance(options, list):
            continue
        # Keep exactly 4 string options
        opts = [str(o) for o in options if isinstance(o, (str, int, float))]
        opts = [o.strip() for o in opts if o is not None]
        # Ensure labels A)-D)
        labels = ["A)", "B)", "C)", "D)"]
        normalized = []
        for i in range(4):
            text_i = opts[i] if i < len(opts) else f"{labels[i]} (placeholder)"
            # If missing label, add it
            if not text_i.startswith(labels[i]):
                # Remove any leading label-like pattern and reapply
                t = text_i
                # Strip common prefixes like "A) ", "A.", "(A)"
                t = t.lstrip(" (ABCDEF).:")
                text_i = f"{labels[i]} {t.strip()}"
            normalized.append(text_i)

        # Ensure correct_answer matches one of the options exactly
        if not isinstance(answer, str):
            answer = normalized[0]
        if answer not in normalized:
            # Try to match by leading label
            lead = answer[:2]
            found = None
            for opt in normalized:
                if opt.startswith(lead):
                    found = opt
                    break
            answer = found or normalized[0]

        fixed_questions.append(
            {
                "question_text": qtext.strip(),
                "options": normalized[:4],
                "correct_answer": answer,
            }
        )

    # If fewer than expected, just keep what we have
    doc["questions"] = fixed_questions
    return doc


async def generate_quiz_for_topic(
    pinecone_id: str,
    topic_name: str,
    difficulty: str,
    num_questions: int,
) -> Dict[str, Any]:
    """Generate an MCQ quiz JSON based on vector context for the given topic."""
    if num_questions <= 0:
        raise ValueError("num_questions must be > 0")

    context = retrieve_topic_context(pinecone_id, topic_name, top_k=20, max_chars=20000)
    if not context:
        raise ValueError("No relevant content found for the requested topic.")

    prompt = _build_quiz_prompt(topic_name, difficulty, num_questions, context)
    llm = build_llm_quiz()
    resp = await asyncio.get_event_loop().run_in_executor(None, llm.invoke, prompt)
    raw = resp.content if hasattr(resp, "content") else str(resp)

    doc = _coerce_json(raw)
    doc = _validate_and_fix_quiz(doc, expected_count=num_questions)

    # Trim to the requested number of questions
    if isinstance(doc.get("questions"), list):
        doc["questions"] = doc["questions"][: num_questions]
    return doc
