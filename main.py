"""
AI-Driven Personalized VR Teaching System - FastAPI Server

Main entry point for the API. Combines existing RAG functionality
with the new multi-agent system for personalized VR teaching.
"""

import os
import json
from typing import List, Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyHttpUrl


# ============================================================================
# SSE Helper
# ============================================================================

async def sse_stream(generator) -> AsyncGenerator[str, None]:
    """
    Convert an async generator of dicts to Server-Sent Events format.
    
    Each yielded dict becomes an SSE event:
    - {"event": "progress", "step": "...", "progress": 50} → event: progress
    - {"event": "result", "data": {...}} → event: result
    - {"event": "error", "error": "..."} → event: error
    """
    try:
        async for event in generator:
            event_type = event.get("event", "progress")
            payload = json.dumps(event, default=str)
            yield f"event: {event_type}\ndata: {payload}\n\n"
        
        # Final done event  
        yield f"event: done\ndata: {{}}\n\n"
    except Exception as e:
        error_payload = json.dumps({"event": "error", "error": str(e)})
        yield f"event: error\ndata: {error_payload}\n\n"

# Existing RAG imports
from gen_topic import ingest_pdf_from_url
from gen_notes import generate_notes_for_topic
from gen_quiz import generate_quiz_for_topic
from rag_chatbot import chat_query, reset_session

# New multi-agent imports
from agents.orchestrator import orchestrator
from db.supabase_client import supabase_manager

# Content ingestion with class/subject metadata
from content_ingestion import (
    ingest_content_from_url,
    ingest_content_from_base64,
    ingest_content_from_bytes,
    search_content,
)


# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="Personalized VR Teaching System API",
    description="Multi-agent system for AI-driven personalized VR education",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

# --- Student Models ---
class CreateStudentRequest(BaseModel):
    name: str
    email: Optional[str] = None
    class_number: Optional[int] = 10


class StudentResponse(BaseModel):
    student_id: str
    message: str


# --- Onboarding Models ---
class OnboardingStartRequest(BaseModel):
    student_id: str
    subject_code: str


class OnboardingSubmitRequest(BaseModel):
    assessment_id: str
    student_id: str
    subject_code: str
    questions: list
    responses: list


# --- Teaching Models ---
class TeachingContentRequest(BaseModel):
    student_id: str
    subject_code: str
    topic_code: str
    topic_name: Optional[str] = None


class StartSessionRequest(BaseModel):
    student_id: str
    subject_code: str


# --- Assessment Models ---
class DiagnosticRequest(BaseModel):
    student_id: str
    subject_code: str
    topic_code: Optional[str] = None
    topic_name: Optional[str] = None
    stage: str = "initial"  # "initial", "mid_lesson", "post_lesson"


class SubmitAssessmentRequest(BaseModel):
    assessment_id: str
    student_id: str
    subject_code: str
    topic_code: str
    topic_name: Optional[str] = None
    questions: list
    responses: list


# --- Exam Models ---
class GenerateExamRequest(BaseModel):
    student_id: str
    subject_code: str
    topic_code: str
    topic_name: Optional[str] = None
    num_questions: int = 10


class SubmitExamRequest(BaseModel):
    exam: dict
    responses: list


# --- Legacy RAG Models (kept for backward compatibility) ---
class Gen_TopicRequest(BaseModel):
    url: AnyHttpUrl


class Gen_TopicResponse(BaseModel):
    pineconeID: str
    topicName: List[str]


class Gen_NotesRequest(BaseModel):
    pineconeID: str
    topicName: str


class Gen_NotesResponse(BaseModel):
    notes: str


class ChatRequest(BaseModel):
    pineconeID: str
    query: str


class ChatResponse(BaseModel):
    answer: str


class ResetRequest(BaseModel):
    pineconeID: str


class ResetResponse(BaseModel):
    message: str


class Gen_QuizRequest(BaseModel):
    pineconeID: str
    topicName: str
    difficulty: str
    numQuestions: int


class Gen_QuizResponse(BaseModel):
    title: str
    questions: list


# --- Content Ingestion Models ---
class ContentIngestUrlRequest(BaseModel):
    """Ingest content from URL with class/subject tagging."""
    url: str
    class_number: int
    subject_code: str


class ContentIngestFileRequest(BaseModel):
    """Ingest content from base64 file with class/subject tagging."""
    file_base64: str
    filename: str
    class_number: int
    subject_code: str


class ContentSearchRequest(BaseModel):
    """Search ingested content."""
    query: str
    class_number: int
    subject_code: str
    topic_code: Optional[str] = None
    top_k: int = 5


# ============================================================================
# STUDENT ENDPOINTS
# ============================================================================

@app.post("/students", tags=["Students"])
async def create_student(req: CreateStudentRequest):
    """Create a new student."""
    try:
        # Look up class_id from class_number if provided
        class_id = None
        if req.class_number:
            result = await supabase_manager.get_class_by_number(req.class_number)
            # Handle both string and ClassInfo object returns
            if result is not None:
                class_id = str(result.id) if hasattr(result, 'id') else str(result)
        
        student_id = await supabase_manager.create_user(
            name=req.name,
            email=req.email,
            class_id=class_id,
        )
        return JSONResponse(
            status_code=201,
            content={"student_id": student_id, "message": "Student created successfully"}
        )
    except Exception as e:
        print(f"[ERROR] create_student failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/students/{student_id}", tags=["Students"])
async def get_student_profile(student_id: str):
    """Get a student's learning profile."""
    try:
        profile = await supabase_manager.get_learner_profile(student_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Student not found")
        return JSONResponse(status_code=200, content=profile.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/students/{student_id}/recommendations", tags=["Students"])
async def get_student_recommendations(student_id: str):
    """Get personalized learning recommendations for a student."""
    try:
        result = await orchestrator.get_student_recommendations(student_id)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ONBOARDING ENDPOINTS (New User Flow)
# ============================================================================

@app.post("/onboarding/start", tags=["Onboarding"])
async def start_onboarding(req: OnboardingStartRequest):
    """
    Start onboarding assessment for a new student.
    
    Streams SSE progress events as questions are generated per topic,
    followed by a final result event with the complete assessment.
    """
    generator = orchestrator.run_onboarding_assessment_stream(
        student_id=req.student_id,
        subject_code=req.subject_code,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/onboarding/submit", tags=["Onboarding"])
async def submit_onboarding(req: OnboardingSubmitRequest):
    """
    Submit onboarding assessment and get personalized learning path.
    
    Streams SSE progress as each topic is evaluated, profile updated,
    and learning path generated.
    """
    generator = orchestrator.submit_onboarding_stream(
        student_id=req.student_id,
        assessment_id=req.assessment_id,
        subject_code=req.subject_code,
        questions=req.questions,
        responses=req.responses,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# TEACHING ENDPOINTS
# ============================================================================

@app.post("/teach/start", tags=["Teaching"])
async def start_teaching_session(req: StartSessionRequest):
    """
    Start a new teaching session.
    
    Streams SSE progress as profile is loaded, topic determined,
    pedagogy planned, and VR session generated.
    """
    generator = orchestrator.start_session_stream(
        student_id=req.student_id,
        subject_code=req.subject_code,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/teach/content", tags=["Teaching"])
async def get_teaching_content(req: TeachingContentRequest):
    """
    Generate teaching content for a specific topic.
    
    Streams SSE progress as curriculum, pedagogy, and VR session
    are generated for the requested topic.
    """
    generator = orchestrator.generate_teaching_content_stream(
        student_id=req.student_id,
        subject_code=req.subject_code,
        topic_code=req.topic_code,
        topic_name=req.topic_name,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# ASSESSMENT ENDPOINTS
# ============================================================================

@app.post("/assessments/diagnostic", tags=["Assessments"])
async def generate_diagnostic(req: DiagnosticRequest):
    """
    Generate diagnostic assessment questions.
    
    Streams SSE progress as questions are generated and VR layout created.
    """
    generator = orchestrator.generate_assessment_stream(
        student_id=req.student_id,
        subject_code=req.subject_code,
        topic_code=req.topic_code,
        topic_name=req.topic_name,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/assessments/submit", tags=["Assessments"])
async def submit_assessment(req: SubmitAssessmentRequest):
    """
    Submit assessment responses and get results.
    
    Streams SSE progress as MCQs evaluated, misconceptions identified,
    profile updated, and remediation generated.
    """
    generator = orchestrator.submit_assessment_stream(
        student_id=req.student_id,
        assessment_id=req.assessment_id,
        subject_code=req.subject_code,
        topic_code=req.topic_code,
        topic_name=req.topic_name,
        questions=req.questions,
        responses=req.responses,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# EXAM ENDPOINTS
# ============================================================================

@app.post("/exams/generate", tags=["Exams"])
async def generate_exam(req: GenerateExamRequest):
    """Generate a comprehensive exam. Streams SSE progress events."""
    generator = orchestrator.generate_exam_stream(
        student_id=req.student_id,
        subject_code=req.subject_code,
        topic_code=req.topic_code,
        topic_name=req.topic_name,
        num_questions=req.num_questions,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/exams/submit", tags=["Exams"])
async def submit_exam(req: SubmitExamRequest):
    """Submit exam and get graded results. Streams SSE progress events."""
    generator = orchestrator.grade_exam_stream(
        exam=req.exam,
        responses=req.responses,
    )
    return StreamingResponse(
        sse_stream(generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# CURRICULUM ENDPOINTS
# ============================================================================

@app.get("/curriculum/{subject_code}", tags=["Curriculum"])
async def get_syllabus(subject_code: str):
    """Get the syllabus structure for a subject."""
    try:
        result = orchestrator.get_syllabus(subject_code)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/curriculum/{student_id}/{subject_code}/path", tags=["Curriculum"])
async def get_learning_path(student_id: str, subject_code: str):
    """Get personalized learning path for a student in a subject."""
    try:
        result = await orchestrator.get_learning_path(student_id, subject_code)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LEGACY RAG ENDPOINTS (Backward Compatibility)
# ============================================================================

@app.post("/gen_topic", response_model=Gen_TopicResponse, tags=["Legacy RAG"])
async def ingest_pdf(req: Gen_TopicRequest):
    """Ingest PDF from URL and extract topics (Legacy)."""
    try:
        result = await ingest_pdf_from_url(str(req.url))
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gen_notes", response_model=Gen_NotesResponse, tags=["Legacy RAG"])
async def gen_notes(req: Gen_NotesRequest):
    """Generate notes for a topic from Pinecone (Legacy)."""
    try:
        notes = await generate_notes_for_topic(req.pineconeID, req.topicName)
        return JSONResponse(status_code=200, content={"notes": notes})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse, tags=["Legacy RAG"])
async def chat(req: ChatRequest):
    """RAG chatbot query (Legacy)."""
    try:
        answer = await chat_query(req.pineconeID, req.query)
        return JSONResponse(status_code=200, content={"answer": answer})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/reset", response_model=ResetResponse, tags=["Legacy RAG"])
async def chat_reset(req: ResetRequest):
    """Reset chat session (Legacy)."""
    try:
        reset_session(req.pineconeID)
        return JSONResponse(status_code=200, content={"message": "Session reset"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/gen_quiz", response_model=Gen_QuizResponse, tags=["Legacy RAG"])
async def gen_quiz(req: Gen_QuizRequest):
    """Generate quiz for a topic (Legacy - use /assessments/diagnostic instead)."""
    try:
        quiz = await generate_quiz_for_topic(
            req.pineconeID, req.topicName, req.difficulty, req.numQuestions
        )
        return JSONResponse(status_code=200, content=quiz)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONTENT INGESTION ENDPOINTS
# ============================================================================

@app.post("/content/ingest/url", tags=["Content"])
async def ingest_content_url(req: ContentIngestUrlRequest):
    """
    Ingest content from a URL with class/subject tagging.
    
    The content will be:
    1. Downloaded and parsed
    2. Chunked and embedded
    3. Stored in Pinecone with class/subject metadata
    4. Topics auto-detected
    """
    try:
        result = await ingest_content_from_url(
            url=req.url,
            class_number=req.class_number,
            subject_code=req.subject_code,
        )
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/content/ingest/file", tags=["Content"])
async def ingest_content_file(req: ContentIngestFileRequest):
    """
    Ingest content from a base64-encoded file with class/subject tagging.
    
    Send the PDF as base64 encoded string.
    """
    try:
        result = await ingest_content_from_base64(
            base64_content=req.file_base64,
            class_number=req.class_number,
            subject_code=req.subject_code,
            filename=req.filename,
        )
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/content/ingest/upload", tags=["Content"])
async def ingest_content_upload(
    file: UploadFile = File(...),
    class_number: int = Form(...),
    subject_code: str = Form(...),
):
    """
    Upload a PDF file directly (use this in Postman).
    
    In Postman:
    - Method: POST
    - Body → form-data
    - file: select your PDF file
    - class_number: 10
    - subject_code: physics
    """
    try:
        pdf_bytes = await file.read()
        result = await ingest_content_from_bytes(
            file_bytes=pdf_bytes,
            class_number=class_number,
            subject_code=subject_code,
            filename=file.filename or "uploaded.pdf",
        )
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/content/search", tags=["Content"])
async def search_ingested_content(req: ContentSearchRequest):
    """
    Search content filtered by class and subject.
    
    Returns relevant chunks from ingested documents.
    """
    try:
        results = await search_content(
            query=req.query,
            class_number=req.class_number,
            subject_code=req.subject_code,
            topic_code=req.topic_code,
            top_k=req.top_k,
        )
        return JSONResponse(status_code=200, content={"results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/", tags=["System"])
async def root():
    """API root with available endpoints."""
    return {
        "message": "Personalized VR Teaching System API",
        "docs": "/docs",
        "endpoints": {
            "content": ["POST /content/ingest/url", "POST /content/ingest/file", "POST /content/search"],
            "students": ["POST /students", "GET /students/{id}", "GET /students/{id}/recommendations"],
            "onboarding": ["POST /onboarding/start", "POST /onboarding/submit"],
            "teaching": ["POST /teach/start", "POST /teach/content"],
            "assessments": ["POST /assessments/diagnostic", "POST /assessments/submit"],
            "exams": ["POST /exams/generate", "POST /exams/submit"],
            "curriculum": ["GET /curriculum/{subject}", "GET /curriculum/{student}/{subject}/path"],
        }
    }
