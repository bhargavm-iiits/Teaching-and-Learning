import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, AnyHttpUrl

from gen_topic import ingest_pdf_from_url
from gen_notes import generate_notes_for_topic
from gen_quiz import generate_quiz_for_topic
from rag_chatbot import chat_query, reset_session
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Helper Functions API")
app.add_middleware(CORSMiddleware, allow_origins=[
                   "*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class Gen_TopicRequest(BaseModel):
	url: AnyHttpUrl


class Gen_TopicResponse(BaseModel):
	pineconeID: str
	topicName: List[str]


@app.post("/gen_topic", response_model=Gen_TopicResponse)
async def ingest_pdf(req: Gen_TopicRequest):
	try:
		result = await ingest_pdf_from_url(str(req.url))
		return JSONResponse(status_code=200, content=result)
	except Exception as e:
		# Map to HTTP 500 by default; customize common cases if needed
		raise HTTPException(status_code=500, detail=str(e))


class Gen_NotesRequest(BaseModel):
	pineconeID: str
	topicName: str


class Gen_NotesResponse(BaseModel):
	notes: str


@app.post("/gen_notes", response_model=Gen_NotesResponse)
async def gen_notes(req: Gen_NotesRequest):
	try:
		notes = await generate_notes_for_topic(req.pineconeID, req.topicName)
		return JSONResponse(status_code=200, content={"notes": notes})
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


# ---------------- Chatbot endpoints ----------------
class ChatRequest(BaseModel):
	pineconeID: str
	query: str


class ChatResponse(BaseModel):
	answer: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
	try:
		answer = await chat_query(req.pineconeID, req.query)
		return JSONResponse(status_code=200, content={"answer": answer})
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


class ResetRequest(BaseModel):
	pineconeID: str


class ResetResponse(BaseModel):
	message: str


@app.post("/chat/reset", response_model=ResetResponse)
async def chat_reset(req: ResetRequest):
	try:
		reset_session(req.pineconeID)
		return JSONResponse(status_code=200, content={"message": "Session reset"})
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


# ---------------- Quiz generation endpoint ----------------
class Gen_QuizRequest(BaseModel):
	pineconeID: str
	topicName: str
	difficulty: str
	numQuestions: int


class Gen_QuizResponse(BaseModel):
	title: str
	questions: list


@app.post("/gen_quiz", response_model=Gen_QuizResponse)
async def gen_quiz(req: Gen_QuizRequest):
	try:
		quiz = await generate_quiz_for_topic(
			req.pineconeID, req.topicName, req.difficulty, req.numQuestions
		)
		return JSONResponse(status_code=200, content=quiz)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
