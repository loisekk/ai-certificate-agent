# 🤖 AI Certificate Agent System - Workflow Plan

## Executive Summary

A two-agent AI system that automates certificate course completion:
- **Agent 1 (Content Watcher)**: Downloads and transcribes workshop videos
- **Agent 2 (Content Summarizer)**: Uses RAG to create study materials

**Result**: 10+ hours of video → 30 minutes of review → Certificate earned

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TWO-AGENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  AGENT 1: CONTENT WATCHER (Transcription Engine)         │ │
│  │  • Downloads workshop videos (yt-dlp)                    │ │
│  │  • Extracts audio and transcribes (Groq Whisper)        │ │
│  │  • Stores raw transcripts in PostgreSQL                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                            │                                    │
│                            ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  AGENT 2: CONTENT SUMMARIZER (RAG Engine)                │ │
│  │  • Reads all transcripts from PostgreSQL                 │ │
│  │  • Chunks content and generates embeddings              │ │
│  │  • Creates summaries using Ollama                        │ │
│  │  • Builds study guides, cheat sheets, key points        │ │
│  └───────────────────────────────────────────────────────────┘ │
│                            │                                    │
│                            ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  OUTPUT: Study Materials Ready for You                   │ │
│  │  • study-guide.md (comprehensive notes)                 │ │
│  │  • key-concepts.md (important terms)                    │ │
│  │  • cheat-sheet.md (quick reference)                     │ │
│  │  • quiz-answers.md (likely quiz answers)               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Infrastructure

| Component | Technology | Purpose | Cost |
|-----------|------------|---------|------|
| **Workflow Engine** | n8n (Docker) | Orchestrate automations | Free |
| **Database** | PostgreSQL + pgvector | Store transcripts + embeddings | Free |
| **LLM** | Ollama (local) | Generate summaries | Free |
| **Notifications** | Telegram Bot | Progress alerts | Free |

### Agent 1: Content Watcher

| Component | Technology | Purpose | Cost |
|-----------|------------|---------|------|
| **Video Downloader** | yt-dlp | Download workshop videos | Free |
| **Audio Extraction** | FFmpeg | Extract audio from video | Free |
| **Transcription** | Groq Whisper API | Convert audio to text | Free (14,400 req/day) |

### Agent 2: Content Summarizer

| Component | Technology | Purpose | Cost |
|-----------|------------|---------|------|
| **LLM** | Ollama (llama3) | Generate summaries | Free |
| **Embeddings** | Ollama (nomic-embed-text) | Create vector embeddings | Free |
| **RAG Framework** | LangChain | Retrieval-Augmented Generation | Free |
| **Vector Store** | PostgreSQL + pgvector | Store embeddings | Free |

---

## 📋 Agent 1: Content Watcher Pipeline

### Input
- Course URL (YouTube, LinkedIn Learning, Coursera)

### Pipeline Steps

```
1. FETCH COURSE INFO
   └── yt-dlp --dump-json {url}
   └── Extract: title, chapters, video URLs, duration

2. DOWNLOAD VIDEOS
   └── yt-dlp -x --audio-format mp3 {video_url}
   └── Store: /tmp/audio/{video_id}.mp3

3. TRANSCRIBE AUDIO
   ├── Check for existing subtitles (fastest)
   ├── Fallback: Groq Whisper API
   └── Split long audio (>25MB) into chunks

4. STORE TRANSCRIPTS
   └── PostgreSQL: workshop_transcripts table

5. NOTIFY PROGRESS
   └── Telegram: "Transcribed: {chapter} ({duration})"
```

### Output
- Raw transcripts stored in PostgreSQL
- Structured by course, chapter, and timestamp

---

## 📋 Agent 2: Content Summarizer Pipeline

### Input
- Transcripts from PostgreSQL

### Pipeline Steps

```
1. LOAD TRANSCRIPTS
   └── Query PostgreSQL for course transcripts

2. CHUNK CONTENT
   ├── Split into 2000-char chunks
   ├── Add 200-char overlap
   └── Tag with metadata (chapter, timestamp)

3. GENERATE EMBEDDINGS
   ├── Model: Ollama nomic-embed-text
   ├── Input: Each chunk
   ├── Output: Vector embeddings (768 dimensions)
   └── Store: PostgreSQL pgvector column

4. GENERATE SUMMARIES
   ├── LLM: Ollama llama3
   ├── Per chapter: "Summarize this content..."
   └── Store: PostgreSQL ai_summaries table

5. GENERATE STUDY GUIDE
   ├── Combine all chapter summaries
   ├── LLM: "Create comprehensive study guide..."
   └── Output: study-guide.md

6. EXTRACT KEY CONCEPTS
   ├── LLM: "Extract technical terms..."
   └── Output: key-concepts.md

7. GENERATE CHEAT SHEET
   ├── LLM: "Create quick reference..."
   └── Output: cheat-sheet.md

8. RAG QUERY INTERFACE
   ├── User asks question
   ├── Embed question → Search similar chunks
   └── LLM: Generate answer with context
```

### Output
- study-guide.md (comprehensive notes)
- key-concepts.md (technical terms)
- cheat-sheet.md (quick reference)
- quiz-answers.md (predicted answers)
- Searchable knowledge base

---

## 🗄️ Database Schema

### PostgreSQL Tables

```sql
-- Workshop Transcripts (Agent 1 writes)
CREATE TABLE workshop_transcripts (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255),
    provider VARCHAR(100),
    chapter_title VARCHAR(255),
    transcript TEXT,
    duration_minutes INT,
    video_url VARCHAR(500),
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunk Embeddings (Agent 2 writes)
CREATE TABLE chunk_embeddings (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255),
    chapter VARCHAR(255),
    content TEXT,
    embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Summaries (Agent 2 writes)
CREATE TABLE ai_summaries (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255),
    summary_type VARCHAR(50),
    summary_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Course Progress
CREATE TABLE course_progress (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255),
    provider VARCHAR(100),
    status VARCHAR(20),
    videos_total INT,
    videos_completed INT,
    hours_total DECIMAL(5,2),
    hours_completed DECIMAL(5,2),
    study_guide_ready BOOLEAN DEFAULT FALSE,
    start_date DATE,
    end_date DATE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## ⏱️ Implementation Timeline

| Phase | Duration | Tasks | Deliverable |
|-------|----------|-------|-------------|
| **Phase 1** | Day 1 | Create documentation | workflow_plan.md |
| **Phase 2** | Day 1 | Setup infrastructure | docker-compose.yml, setup-database.sql |
| **Phase 3** | Day 2 | Build Agent 1 | agent1_content_watcher.py |
| **Phase 4** | Day 3 | Build Agent 2 | agent2_content_summarizer.py |
| **Phase 5** | Day 4 | Create n8n workflows | course-ingestion.json, content-summarizer.json |
| **Phase 6** | Day 5 | Test with one course | End-to-end test |
| **Phase 7** | Week 2-4 | Process 10+ courses | Study materials ready |
| **Phase 8** | Week 5-8 | Review & earn certs | 10+ certificates |

---

## 🎯 Expected Outcomes

| Metric | Target |
|--------|--------|
| Time per course | 30 min (vs 10 hours watching) |
| Courses processed | 20+ |
| Study guides generated | 20+ |
| Certificates earned | 15+ |
| Total time saved | 150+ hours |

---

## 📁 File Structure

```
certificate-tracker/
├── workflow_plan.md              # This file
├── docker-compose.yml            # Infrastructure
├── setup-database.sql            # PostgreSQL schema
├── .env.example                  # Environment config
├── requirements.txt              # Python dependencies
│
├── agents/
│   ├── agent1_content_watcher.py     # Video transcriber
│   └── agent2_content_summarizer.py  # RAG summarizer
│
├── workflows/
│   ├── course-ingestion.json         # n8n: Agent 1
│   └── content-summarizer.json       # n8n: Agent 2
│
├── scripts/
│   └── export-materials.py           # Export utilities
│
├── config/
│   ├── config.yaml                   # Main config
│   └── prompts.yaml                  # AI prompts
│
├── output/                           # Generated materials
│   └── [course-name]/
│       ├── study-guide.md
│       ├── key-concepts.md
│       └── cheat-sheet.md
│
└── docs/
    ├── SETUP.md                      # Installation guide
    └── API.md                        # API documentation
```

---

**Last Updated**: July 2026
**Repository**: https://github.com/loisekk/n8n-workflows
