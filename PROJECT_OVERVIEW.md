# AI-Driven Personalized VR Teaching System
### An Intelligent Multi-Agent Backend for Immersive STEM Education

> **Version:** 2.0.0 | **Target Audience:** Class 10 Students (Age ~15) | **Domain:** EdTech × Artificial Intelligence × Virtual Reality

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Problem Statement](#2-problem-statement)
3. [Objectives](#3-objectives)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Multi-Agent System Design](#6-multi-agent-system-design)
7. [Key Innovation — The ReAct Loop](#7-key-innovation--the-react-loop)
8. [Novelty vs. Existing Approaches](#8-novelty-vs-existing-approaches)
9. [Complete System Flow](#9-complete-system-flow)
10. [API Design](#10-api-design)
11. [Database Design](#11-database-design)
12. [VR Integration](#12-vr-integration)
13. [Deployment](#13-deployment)
14. [Future Scope](#14-future-scope)
15. [Conclusion](#15-conclusion)

---

## 1. Abstract

This project is an **AI-powered, multi-agent backend system** that delivers fully personalized STEM education to Class 10 students inside a **Virtual Reality environment**. The system uses a coordinated team of **7 specialized AI agents**, each responsible for a distinct pedagogical function — from diagnosing a student's knowledge gaps, to selecting the best analogy for explanation, to autonomously generating the actual **Unity C# code** that runs the VR lesson.

The backend is built with **FastAPI** and powered by **Anthropic Claude (Sonnet)** as the LLM. It communicates with a **Unity VR application** in real time via Server-Sent Events (SSE), streaming lesson content, interactive scripts, and personalized assessments. The database is hosted on **Supabase (PostgreSQL)**, and content knowledge is stored in **Pinecone**, a vector database for semantic search.

The core novelty is the application of the **agentAR-inspired ReAct (Reason + Act) loop** — an autonomous cycle where one agent thinks, generates, validates, reviews, and patches Unity C# MonoBehaviour scripts without any human intervention, closing the loop between AI reasoning and live game engine execution.

---

## 2. Problem Statement

### The Limitations of Traditional Education

- **One-size-fits-all teaching** ignores individual learning paces, styles, and knowledge gaps.
- Students who fall behind rarely receive targeted remediation; those who are ahead are never challenged further.
- Abstract STEM concepts (projectile motion, atomic structure, coordinate geometry) are difficult to visualize and understand through textbooks alone.
- Teacher-student ratios in Indian classrooms make truly personalized instruction nearly impossible at scale.

### The Gap in Existing EdTech Solutions

- Existing e-learning platforms (Khan Academy, BYJU'S, etc.) offer **static, pre-recorded content** — there is no real-time adaptation to what a student is struggling with right now.
- VR education tools exist but are **content-fixed** — the lesson does not change based on who is learning.
- AI tutors exist but lack **VR immersion**, making them less engaging for the target demographic.
- No existing system **autonomously generates the VR lesson code** at runtime — every current system requires human developers to pre-author every scene and interaction.

### Our Answer

A backend that **knows the student**, **decides what to teach**, **generates how to teach it in VR**, and **writes the VR code itself** — all in real time, all personalized, all autonomous.

---

## 3. Objectives

| # | Objective | How It Is Achieved |
|---|---|---|
| 1 | Assess each student's baseline knowledge before teaching | Agent A generates and evaluates personalized diagnostic questions |
| 2 | Build and continuously update a dynamic learner profile | Agent B tracks topic mastery, learning style, and misconceptions in Supabase |
| 3 | Automatically decide what topic to teach next | Agent C uses a prerequisite-aware curriculum sequencing algorithm |
| 4 | Adapt the teaching style to each student's preferences | Agent D selects analogies (sports / gaming / daily life) and generates a tailored lesson |
| 5 | Generate Unity C# scripts for the VR lesson at runtime | Agent E runs an autonomous ReAct loop to write, validate, and patch C# code |
| 6 | Design the VR scene layout and 3D asset placement | Agent G builds scene plans with exact 3D coordinates for every prefab |
| 7 | Evaluate student performance and provide remediation | Agent F generates exams, grades them, and produces a per-misconception remediation plan |

---

## 4. System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UNITY VR CLIENT                             │
│  (Renders scenes, runs C# scripts, sends compiler feedback)         │
└──────────────────────┬──────────────────────────────────────────────┘
                       │  HTTP + Server-Sent Events (SSE)
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND (Port 8080)                     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AGENT ORCHESTRATOR                        │   │
│  │  (Coordinates all 7 agents, manages SSE streaming)           │   │
│  └──────┬────────┬────────┬────────┬────────┬────────┬─────────┘   │
│         │        │        │        │        │        │             │
│    Agent A   Agent B  Agent C  Agent D  Agent E  Agent F  Agent G  │
│  (Assess) (Profile)(Curriculum)(Pedagogy)(VR Code)(Exam) (Scene)   │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │  Supabase    │   │   Pinecone   │   │  Anthropic Claude    │   │
│  │ (PostgreSQL) │   │  (Vectors)   │   │  (claude-sonnet-4-6) │   │
│  └──────────────┘   └──────────────┘   └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Design Philosophy

- **Separation of Concerns:** Each agent has exactly one responsibility. No agent does another agent's job.
- **Streaming First:** All major operations are streamed via SSE so Unity gets real-time progress updates rather than waiting for a monolithic response.
- **Autonomous Code Generation:** The system does not serve pre-written scripts — it writes new C# code from scratch for every lesson, every student, every time.
- **Feedback Loops:** Unity can report compiler errors back to the backend, which patches the scripts and re-serves them — a self-healing code generation pipeline.

---

## 5. Technology Stack

### Backend & Runtime

| Technology | Role | Why It Was Chosen |
|---|---|---|
| **Python 3.12** | Primary language | Rich ecosystem for AI/ML, async support |
| **FastAPI** | REST API framework | Async-first, automatic OpenAPI docs, SSE support |
| **Uvicorn** | ASGI server | High-performance async server for FastAPI |
| **Pydantic v2** | Data validation & models | Strict typing for all API contracts with Unity |

### Artificial Intelligence

| Technology | Role | Why It Was Chosen |
|---|---|---|
| **Anthropic Claude Sonnet 4** | Primary LLM for all 7 agents | Excellent instruction-following, long context (200K tokens), superior at structured JSON output and code generation |
| **LangChain (Anthropic)** | LLM integration layer | Simplifies prompt construction and model invocation |
| **Azure OpenAI GPT-4.1** | Legacy RAG system (backward compat.) | Pre-existing integration retained for older features |
| **Azure OpenAI Embeddings** | `text-embedding-3-large` for PDF content | High-quality semantic embeddings for content retrieval |

### Databases & Storage

| Technology | Role | Why It Was Chosen |
|---|---|---|
| **Supabase (PostgreSQL)** | Student profiles, assessments, progress | Relational integrity for structured learner data; real-time capabilities |
| **Pinecone** | Vector store for PDF educational content | Sub-millisecond semantic similarity search; supports metadata filtering by class and subject |

### PDF & Content Processing

| Technology | Role |
|---|---|
| **pypdf** | Extracting text from uploaded/linked educational PDFs |
| **httpx** | Async HTTP client for fetching PDFs from remote URLs |

### Communication & Streaming

| Technology | Role |
|---|---|
| **Server-Sent Events (SSE)** | Real-time one-way streaming from backend to Unity/frontend |
| **StreamingResponse (FastAPI)** | Serves SSE as `text/event-stream` content type |

### DevOps & Deployment

| Technology | Role |
|---|---|
| **Docker** | Containerization (Python 3.11-slim image) |
| **Google Cloud Run** | Serverless deployment target (port 8080, env-var driven) |
| **python-dotenv** | Environment variable management for API keys |

---

## 6. Multi-Agent System Design

The system employs **7 specialized AI agents**, all inheriting from a common `BaseAgent` class. Each agent is instantiated once at server startup by the **Agent Orchestrator** and called in a coordinated sequence.

### Base Agent (Foundation Layer)

Every agent shares these core capabilities:
- A dedicated **Claude Sonnet 4 instance** (8192 max output tokens)
- A **5-strategy JSON parser** — handles code fences, trailing commas, bare objects, malformed output — ensuring reliable structured responses from the LLM
- A structured **prompt builder** that formats task description, context, and expected output format consistently
- Both synchronous and streaming LLM invocation methods

---

### Agent A — Assessment Agent

| Attribute | Detail |
|---|---|
| **Role** | Evaluates students through intelligently crafted questions |
| **Input** | Student ID, subject, topic, assessment stage |
| **Output** | 8–25 questions (MCQ / descriptive / numerical) with VR visual context metadata |
| **Key Capability** | Each question includes a `vr_visual_context` object — a scene, objects, and analogy — so the VR environment knows exactly what to render alongside the question |
| **Evaluation** | MCQs graded deterministically (letter matching); descriptive answers graded by LLM using a rubric |
| **Misconception Detection** | LLM analyzes wrong answers to identify the root conceptual error — not just "wrong", but *why* |
| **Assessment Stages** | `initial` (onboarding diagnostic), `mid_lesson` (formative), `post_lesson` (summative) |

---

### Agent B — Learner Profile Agent

| Attribute | Detail |
|---|---|
| **Role** | Maintains a living, continuously updated model of the student |
| **Input** | Assessment results, student ID |
| **Output** | Updated `LearnerProfile` stored in Supabase |
| **Mastery Tracking** | Weighted score averaging: 30% old score + 70% new score — prevents wild swings from single poor performance |
| **Learning Style Inference** | After 3+ assessments, LLM analyzes patterns and infers learning style (`visual`, `kinesthetic`, `auditory`, `formula-first`, `intuition-first`); updated in DB only if confidence > 60% |
| **Topic Categorization** | Automatically moves topics between `weak_topics` and `strong_topics` lists based on mastery score |

---

### Agent C — Curriculum Agent

| Attribute | Detail |
|---|---|
| **Role** | Decides what to teach next based on the student's current state |
| **Input** | Learner profile, subject, completed topics |
| **Output** | `CurriculumPlan` — ordered topic list with time estimates |
| **Sequencing Algorithm** | Three-priority system: (1) Reinforce weak topics whose prerequisites are met, (2) Introduce new topics where prerequisites are satisfied, (3) Improve topics at "developing" level. Final selection adjudicated by LLM |
| **Subjects Covered** | Physics (6 topics: Motion → Kinematics → Projectile → Laws → Gravitation → Work/Energy), Chemistry (4 topics), Maths (5 topics) |
| **Smart Skipping** | Mastered topics are assigned 0 additional time and skipped in the plan |

---

### Agent D — Pedagogy Agent

| Attribute | Detail |
|---|---|
| **Role** | Decides *how* to teach — teaching approach, analogies, visualization strategy |
| **Input** | Topic, learner profile (learning style, preferred analogies) |
| **Output** | `PedagogyPlan` + full lesson content (intro, subtopic sections, summary) |
| **Analogy Bank** | Hardcoded knowledge base of subject/topic → analogy mappings across 3 categories: **Sports** (cricket, football, basketball), **Daily Life** (bus, shopping, cooking), **Gaming** (Angry Birds, racing game, video game maps) |
| **Approach Selection** | `intuition-first` (build understanding through analogy before formula) vs. `formula-first` (derive formula, then apply) — chosen based on student profile |
| **Lesson Generation** | Uses N+2 separate LLM calls (one intro, one per subtopic, one summary) to avoid token truncation in long lessons |

---

### Agent E — VR Instruction Agent (The Star Agent)

| Attribute | Detail |
|---|---|
| **Role** | Autonomously generates Unity C# MonoBehaviour scripts that run the VR lesson |
| **Input** | Pedagogy plan, scene asset bindings from Agent G, learner profile |
| **Output** | `UnityScriptPackage` — 6 complete, validated, pedagogically reviewed C# scripts |
| **Mechanism** | **agentAR-inspired ReAct Loop** (explained in detail in Section 7) |
| **Script Types Generated** | `SessionManager`, `IntroductionController`, `DemonstrationController`, `InteractionController`, `AssessmentController`, `SummaryController` |
| **Self-Patching** | If Unity compilation fails, the agent receives the error and patches the script automatically via the `/vr/script-feedback` endpoint |

---

### Agent F — Evaluation Agent

| Attribute | Detail |
|---|---|
| **Role** | Comprehensive exam generation and detailed feedback |
| **Input** | Student ID, subject, number of questions |
| **Output** | Full exam → graded result → remediation plan |
| **Exam Composition** | 60% MCQ + 25% Descriptive + 15% Numerical — automatically balanced |
| **Personalization** | Questions are skewed toward the student's `weak_topics` from their profile |
| **Remediation** | For every identified misconception: explains *why* it's wrong, gives the correct understanding, provides a memory analogy, and suggests a practice activity |

---

### Agent G — Scene Builder Agent

| Attribute | Detail |
|---|---|
| **Role** | Designs the VR environment — scenes, asset placement, transitions |
| **Input** | Subject, topic, analogy category |
| **Output** | `FullScenePlan` — primary + secondary scene descriptions, asset manifests with 3D coordinates, scene transitions, opening commands |
| **Scene Knowledge Base** | Maps every topic to specific environments: Projectile Motion → Cricket Ground + Physics Lab; Gravitation → Space + Outdoor Field; Number Systems → Stadium + Math Room; and 8+ more |
| **3D Asset Placement** | Places assets in a shallow arc at `z=3.0`, marks the first 3 as interactive for student engagement |
| **Asset Bindings** | Returns a prefab map (`{asset_id: "Assets/Prefabs/{Subject}/{asset_id}.prefab"}`) that Agent E uses to wire `[SerializeField]` references in C# |
| **Transitions** | LLM writes bridge narration + selects visual effect (`portal`, `fade_black`, `dissolve`, etc.) between scene changes |

---

### Agent Orchestrator (Coordinator)

The `AgentOrchestrator` is the single point of coordination. It:
- Instantiates all 7 agents once at server startup
- Defines the **exact sequence** in which agents are called for each workflow
- Exposes both synchronous (for simple queries) and **streaming async generators** (for teaching sessions) to `main.py`
- Converts agent outputs into SSE-formatted event streams for Unity

---

## 7. Key Innovation — The ReAct Loop

### What is ReAct?

**ReAct** (Reason + Act) is an AI agent pattern where the agent alternates between *thinking* about what to do next and *acting* on that thought — and then *observing* the result before thinking again. It is inspired by the paper **"ReAct: Synergizing Reasoning and Acting in Language Models"** and implemented here in the style of **agentAR** for code generation.

### How Agent E Uses It

Agent E runs an autonomous loop of up to **20 iterations** to generate all 6 Unity C# scripts:

```
┌──────────────────────────────────────────────────────────────┐
│                     ReAct Loop (Agent E)                     │
│                                                              │
│  ┌─────────┐     ┌─────────┐     ┌──────────┐              │
│  │  THINK  │────▶│   ACT   │────▶│ OBSERVE  │              │
│  │         │     │         │     │ (Syntax) │              │
│  │LLM picks│     │LLM      │     │          │              │
│  │next     │     │streams  │     │7 regex   │              │
│  │script   │     │C# tokens│     │checks    │◀─── patch ◀─┐│
│  └─────────┘     └─────────┘     └──────────┘             ││
│       ▲                               │ pass               ││
│       │                               ▼                    ││
│       │                        ┌──────────┐               ││
│       │                        │ OBSERVE  │               ││
│       └────────────────────────│(Pedagogy)│───patch───────┘│
│          next script            │          │                │
│                                 │LLM scores│                │
│                                 │  0–10    │                │
│                                 └──────────┘                │
│                                      │ score ≥ 7            │
│                                      ▼                      │
│                              Script Accepted                 │
└──────────────────────────────────────────────────────────────┘
```

### Step-by-Step Breakdown

| Step | Agent Action | Technology Used |
|---|---|---|
| **THINK** | LLM decides which of the 6 scripts to generate next based on what is already done | Claude Sonnet 4 |
| **ACT** | LLM generates the C# MonoBehaviour script token by token (streamed to Unity in real time) | Claude Sonnet 4 (streaming) |
| **OBSERVE — Syntax** | Regex engine checks 7 rules: `using UnityEngine` present, inherits `MonoBehaviour`, balanced braces `{}`, `Start()`/`Update()` present, no `Thread.Sleep`, null checks on `GetComponent`, `[SerializeField]` for assets | Pure Python regex — no LLM |
| **OBSERVE — Pedagogy** | LLM reads the script and scores it 0–10 across 5 pedagogical criteria: clarity, engagement, curriculum alignment, difficulty appropriateness, VR interaction quality | Claude Sonnet 4 |
| **PATCH (if needed)** | If syntax fails OR pedagogy score < 7, the agent streams a corrected version of the script, then re-observes | Claude Sonnet 4 (streaming) |
| **ASSEMBLE** | All 6 scripts are bundled into a `UnityScriptPackage`, sorted by execution order, with the entry point identified | Python |

### Why This Matters

Before this system, every VR lesson required a **human developer** to write C# scripts for every topic and every student. This system eliminates that bottleneck entirely. A new student with a unique learning profile can receive a custom-built, fully functional VR lesson in minutes — with zero human authoring.

---

## 8. Novelty vs. Existing Approaches

### Comparison with Existing Systems

| Feature | Traditional E-Learning (Khan Academy, BYJU'S) | AI Tutors (ChatGPT, Khanmigo) | Static VR Education | **This System** |
|---|---|---|---|---|
| Personalized content | Pre-recorded, not adaptive | Adaptive text responses | Fixed, pre-authored | **Fully adaptive per student** |
| VR immersion | No | No | Yes (fixed) | **Yes (dynamic, generated)** |
| Automatic curriculum sequencing | No | Limited | No | **Yes (prerequisite-aware)** |
| Runtime code generation for VR | No | No | No | **Yes (6 C# scripts per lesson)** |
| Misconception-level remediation | No | Partial | No | **Yes (per-concept plans)** |
| Student learner profile | Basic (watch history) | Session-only | No | **Persistent, multi-dimensional** |
| Self-healing code pipeline | N/A | N/A | N/A | **Yes (Unity feedback loop)** |
| Multi-agent coordination | No | No | No | **7 specialized agents** |

### Key Research Contributions

1. **Applying agentAR/ReAct to Runtime VR Code Generation** — The use of a self-correcting LLM loop to autonomously write, validate, and patch game engine scripts at runtime is a novel application not found in existing educational technology systems.

2. **Analogy-Driven VR Scene Design** — The system maps student learning preferences (sports/gaming/daily life) to specific VR environments and 3D assets, creating emotionally resonant, personalized learning environments rather than generic classrooms.

3. **Closed-Loop Compiler Feedback** — Unity reports compilation errors back to the AI backend, which patches the code and re-serves it — creating a self-healing pipeline between AI code generation and a live game engine.

4. **Multi-Dimensional Learner Modelling** — The learner profile tracks not just topic scores but learning style, preferred analogies, misconceptions, study time, and assessment history — enabling hyper-personalized decisions at every stage.

---

## 9. Complete System Flow

### Flow 1: Student Onboarding

```
1. POST /students
   └── Creates student record in Supabase
   └── Initializes LearnerProfile with default values

2. POST /onboarding/start
   └── Agent A generates 20–25 diagnostic MCQ questions for the topic
   └── Each question includes VR scene/object metadata
   └── Questions streamed to Unity via SSE

3. POST /onboarding/submit  (student answers submitted)
   └── Agent A evaluates answers → computes mastery level
   └── Agent A identifies misconceptions from wrong answers
   └── Agent B updates LearnerProfile: topic scores, weak/strong topics
   └── Agent C generates personalized learning path
   └── Result streamed back: learning path + mastery breakdown
```

### Flow 2: Teaching Session (The Core Flow)

```
POST /teach/content  ──────────────────────────────────────────────────
│
├─ SSE: "profile"    ← Agent B loads learner profile from Supabase
│
├─ SSE: "curriculum" ← Agent C identifies topic, subtopics, prerequisites
│                       Decides next topic using 3-priority algorithm
│
├─ SSE: "pedagogy"   ← Agent D selects analogy (sports/gaming/daily life)
│                       Generates PedagogyPlan (approach, visualizations)
│
├─ SSE: "section" ×N ← Agent D generates lesson content:
│                       - 1 intro paragraph
│                       - 1 section per subtopic (N LLM calls)
│                       - 1 summary + practice questions
│
├─ SSE: "scene"      ← Agent G builds FullScenePlan:
│                       - Primary + secondary scene descriptions
│                       - 3D asset manifest with exact positions
│                       - Scene transitions with narration
│                       - Asset bindings prefab map for Agent E
│
└─ ReAct Loop ×6 scripts (Agent E):
    ├─ SSE: "csharp_thinking"        ← Agent decides next script
    ├─ SSE: "csharp_script_start"    ← C# generation begins
    ├─ SSE: "csharp_script_token" ×N ← Token-by-token streaming to Unity
    ├─ SSE: "csharp_review"          ← Pedagogy score reported
    ├─ SSE: "csharp_patch_*"         ← (if score < 7 or syntax fails)
    └─ SSE: "csharp_script_complete" ← Script ready, Unity writes .cs file
    
    → SSE: "scripts_complete" ← All 6 scripts done
    → SSE: "complete"         ← Session generation finished
```

### Flow 3: Unity Execution & Compiler Feedback

```
Unity Engine
├── Writes received .cs files to Assets/Scripts/
├── Triggers compilation
├── If compilation succeeds:
│   └── Attaches MonoBehaviours to GameObjects
│   └── SessionManager.Start() launches the VR lesson
└── If compilation fails:
    └── POST /vr/script-feedback  (error message + script name)
        └── Agent E receives the error
        └── LLM patches the specific script
        └── Patched script returned to Unity
        └── Unity re-compiles
```

### Flow 4: Assessment & Exam

```
POST /assessments/diagnostic  → Agent A generates mid/post lesson questions
POST /assessments/submit      → Agent A evaluates → Agent B updates profile
                                Agent A identifies new misconceptions
                                Agent F generates remediation plan per misconception

POST /exams/generate          → Agent F creates comprehensive exam
                                (60% MCQ + 25% Descriptive + 15% Numerical)
POST /exams/submit            → Agent F grades exam → full feedback report
                                → Mastery level updated in Supabase
```

---

## 10. API Design

The backend exposes **25 HTTP endpoints** organized into 8 functional groups. All major endpoints return **Server-Sent Events (SSE)** streams for real-time communication with Unity.

### Endpoint Groups

| Group | Endpoints | Purpose |
|---|---|---|
| **Students** | `POST /students`, `GET /students/{id}`, `GET /students/{id}/recommendations` | Student creation and profile retrieval |
| **Onboarding** | `POST /onboarding/start`, `POST /onboarding/submit` | Initial diagnostic assessment flow |
| **Teaching** | `POST /teach/start`, `POST /teach/content` | Full lesson generation with C# scripts |
| **Assessments** | `POST /assessments/diagnostic`, `POST /assessments/submit` | Formative and summative assessments |
| **Exams** | `POST /exams/generate`, `POST /exams/submit` | Comprehensive exam generation and grading |
| **VR Scripts** | `POST /vr/script-feedback` | Unity compiler error feedback for self-patching |
| **Curriculum** | `GET /curriculum/{subject}`, `GET /curriculum/{id}/{subject}/path` | Syllabus and personalized learning path |
| **Content** | `POST /content/ingest/url`, `/file`, `/upload`, `POST /content/search` | PDF ingestion into Pinecone and semantic search |

### SSE Event Types

Every streaming response emits structured JSON events of these types:

| Event Type | Meaning |
|---|---|
| `progress` | Intermediate step update (e.g., "Loading learner profile...") |
| `result` | Final result payload (complete data object) |
| `csharp_script_token` | A single token of C# code being streamed in real time |
| `csharp_script_complete` | One full script has been generated and validated |
| `section` | A lesson section (intro/subtopic/summary) has been generated |
| `error` | An error occurred; includes message |
| `done` | Stream is finished |

---

## 11. Database Design

The relational database (PostgreSQL via Supabase) stores all persistent student data.

### Schema Overview

| Table | Primary Key | Purpose |
|---|---|---|
| `classes` | `class_id` | Grade levels 1–12 |
| `subjects` | `subject_id` | Subjects per class (Physics, Chemistry, Maths for Class 10) |
| `syllabus_topics` | `topic_id` | Topics with subtopics and prerequisites stored as JSONB |
| `users` | `student_id` | Student records linked to a class |
| `learner_profiles` | `student_id` | Learning style, preferences, topic knowledge (JSONB blob) |
| `assessments` | `assessment_id` | Every assessment attempt with scores and misconceptions |
| `topic_progress` | `(student_id, subject_id, topic_code)` | Fine-grained mastery tracking per topic |
| `misconceptions` | `misconception_id` | Individual conceptual errors with resolution tracking |
| `vr_sessions` | `session_id` | VR session metadata (start time, steps, status) |
| `exams` | `exam_id` | Full exam records with questions, responses, grades as JSONB |

### Mastery Level System

All topic mastery is tracked using a 4-level system:

| Level | Score Range | Meaning |
|---|---|---|
| `weak` | 0–40% | Student has not understood the concept |
| `developing` | 40–70% | Partial understanding; needs reinforcement |
| `proficient` | 70–85% | Good understanding; ready to advance |
| `mastered` | 85–100% | Full command; can be skipped in curriculum |

---

## 12. VR Integration

### How the Backend Talks to Unity

All communication from the backend to Unity is via **Server-Sent Events (SSE)**. Unity opens a persistent HTTP connection and listens to the event stream. The event stream carries:

- **Lesson text content** — Introduction, subtopic explanations, summary
- **Scene commands** — Which scene to load, where to place which assets in 3D space
- **Avatar commands** — Avatar character, action, and timing (e.g., `POINT` at an object for 3 seconds)
- **Voice commands** — Text-to-speech content with emotion (`encouraging`, `excited`, `calm`) and pace (`slow`, `normal`, `fast`)
- **C# script tokens** — Individual characters of Unity C# code, streamed live as the LLM generates them

### The Unity Contract Models

The backend defines strict typed contracts (Pydantic models) that Unity must consume:

| Contract | Contents |
|---|---|
| `VRInstruction` | Complete step packet: scene + avatar + voice + visual + interaction + assessment commands |
| `SceneCommand` | Scene type (9 options), asset manifest, lighting, skybox |
| `AvatarAction` | One of 13 action types (WALK, POINT, GESTURE, DEMONSTRATE, etc.), target object, duration |
| `VoiceCommand` | TTS text, emotion, pace, delay before speaking |
| `VisualCommand` | Object to animate, motion type, physics parameters, show vectors/labels toggles |
| `InteractionCommand` | One of 8 interaction types, target object, input mode, correct answer |
| `AssessmentCommand` | Question text, options, correct answer, explanation, time limit |
| `UnityScriptPackage` | List of `CSharpScript` objects with filename, content, script type, step order |

### 9 Available VR Scene Types

| Scene | Use Case |
|---|---|
| `classroom` | Default / fallback |
| `cricket_ground` | Projectile motion, velocity, angles |
| `physics_lab` | Experiments, demonstrations |
| `chemistry_lab` | Atomic structure, chemical reactions |
| `math_room` | Equations, geometry, polynomials |
| `outdoor_field` | Gravitation, forces, real-world physics |
| `space` | Gravitation, orbital mechanics |
| `playground` | Newton's laws, friction, momentum |
| `stadium` | Number systems, fractions, large numbers |

### Self-Healing Code Pipeline

```
Agent E generates C# script
        │
        ▼
Unity writes .cs to Assets/Scripts/
        │
        ▼
Unity compiles the script
        │
   ┌────┴────┐
 Error     Success
   │          │
   ▼          ▼
POST /vr/   MonoBehaviour
script-     attached to
feedback    GameObject
   │
   ▼
Agent E reads error,
patches script (LLM)
   │
   ▼
Patched script returned
   │
   ▼
Unity re-compiles
```

---

## 13. Deployment

| Component | Technology | Details |
|---|---|---|
| **Containerization** | Docker | Python 3.11-slim base image; all dependencies installed at build time |
| **Server** | Uvicorn | `uvicorn main:app --host 0.0.0.0 --port 8080` |
| **Target Platform** | Google Cloud Run | Serverless, auto-scaling; PORT environment variable driven |
| **Environment** | `.env` file / Cloud Secrets | All API keys (Anthropic, Supabase, Pinecone, Azure) injected at runtime |
| **API Documentation** | FastAPI AutoDocs | Available at `/docs` (Swagger UI) and `/redoc` |
| **CORS** | Open (`*`) | Allows Unity WebGL and any frontend to connect during development |

---

## 14. Future Scope

| Enhancement | Description |
|---|---|
| **Multi-Class Support** | Currently focused on Class 10. Database schema supports Classes 1–12; expanding to all grades requires only adding syllabus topics and analogy banks. |
| **Voice Input from Students** | Integrate speech-to-text so students can answer questions verbally in VR instead of through UI panels. |
| **More Subjects** | Add Biology, History, and Geography with subject-specific scene types and analogy banks. |
| **Real-Time Collaboration** | Multi-student VR sessions where students can work together on problems, with the AI orchestrating group dynamics. |
| **Parent/Teacher Dashboard** | A web UI showing every student's learning profile, progress charts, mastery levels, and misconception history. |
| **On-Device AI** | Explore running smaller LLMs locally (on the VR headset) to reduce latency and enable offline learning. |
| **Adaptive Difficulty in Real Time** | Adjust the complexity of ongoing VR interactions mid-lesson based on the student's response patterns, not just between lessons. |
| **Emotional Recognition** | Use VR headset sensors (heart rate, gaze tracking, controller grip) to detect frustration or disengagement and have the agent respond empathetically. |
| **Assessment Fraud Detection** | Analyze response timing patterns to detect guessing or copy-paste behavior in online assessments. |

---

## 15. Conclusion

This project demonstrates that **Artificial Intelligence and Virtual Reality can be combined to fundamentally transform how students learn**. Rather than delivering pre-packaged lessons, this system *creates* the lesson — content, code, and environment — fresh for each student, based on who they are and what they need.

### What Makes This System Stand Out

- **7 specialized AI agents** collaborate to cover every aspect of the educational pipeline — from diagnosis to delivery to evaluation.
- **Runtime C# code generation** via the agentAR-inspired ReAct loop eliminates the need for human VR developers to author lessons in advance.
- **Streaming architecture** ensures the VR experience feels responsive and live, not like waiting for a server to process.
- **A self-healing feedback loop** between Unity and the AI backend ensures that even if generated code has compiler errors, the system corrects itself without human intervention.
- **Deep personalization** — every student gets a different analogy, a different scene, a different learning path, and a different assessment — based on their individual profile.

The result is a system that acts as a **personalized AI teacher, curriculum designer, lesson author, and VR developer** — all rolled into one autonomous backend.

---

*Document generated for academic evaluation purposes.*  
*System Version: 2.0.0 | Backend: FastAPI + Anthropic Claude Sonnet 4 | VR Client: Unity Engine*
