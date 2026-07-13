# 🎓 AI Certificate Agent System

An automated system that watches workshop videos, transcribes them, and generates comprehensive study materials using AI.

## 🤖 Two-Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TWO-AGENT SYSTEM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AGENT 1: CONTENT WATCHER                                       │
│  ├── Downloads workshop videos (yt-dlp)                         │
│  ├── Extracts audio and transcribes (Groq Whisper)              │
│  └── Stores raw transcripts in PostgreSQL                       │
│                            │                                    │
│                            ▼                                    │
│  AGENT 2: CONTENT SUMMARIZER (RAG)                              │
│  ├── Reads transcripts from PostgreSQL                          │
│  ├── Generates embeddings for RAG search                        │
│  ├── Creates summaries using Ollama                             │
│  └── Builds study guides, cheat sheets, key concepts            │
│                            │                                    │
│                            ▼                                    │
│  OUTPUT: Study Materials Ready for You                          │
│  ├── study-guide.md (comprehensive notes)                       │
│  ├── cheat-sheet.md (quick reference)                           │
│  └── key-concepts.md (technical terms)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## ⚡ Quick Start

### 1. Start Infrastructure

```bash
cd certificate-tracker
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- n8n (port 5678)
- Ollama (port 11434)

### 2. Pull Ollama Models

```bash
# Pull LLM model
docker exec cert-tracker-ollama ollama pull llama3

# Pull embedding model
docker exec cert-tracker-ollama ollama pull nomic-embed-text
```

### 3. Get Free API Keys

- **Groq API**: https://console.groq.com (free tier: 14,400 req/day)
- **Telegram Bot**: @BotFather on Telegram

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 5. Access n8n

Open http://localhost:5678 and import the workflows from `workflows/` directory.

## 📋 Usage

### Process a Course

**Option A: Using n8n Webhook**

```bash
# Agent 1: Ingest course (transcribe videos)
curl -X POST http://localhost:5678/webhook/ingest-course \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/playlist?list=...", "provider": "YouTube"}'

# Agent 2: Generate study materials
curl -X POST http://localhost:5678/webhook/summarize-course \
  -H "Content-Type: application/json" \
  -d '{"courseName": "Course Title"}'
```

**Option B: Using Python Scripts**

```bash
# Agent 1: Transcribe course
python agents/agent1_content_watcher.py "https://youtube.com/playlist?list=..." \
  --provider YouTube \
  --groq-api-key YOUR_GROQ_KEY

# Agent 2: Generate materials
python agents/agent2_content_summarizer.py "Course Title" \
  --ollama-url http://localhost:11434
```

## 📁 Output Structure

```
output/
└── [Course Name]/
    ├── study-guide.md        # Comprehensive study notes
    ├── cheat-sheet.md        # Quick reference guide
    └── key-concepts.md       # Technical terms & definitions
```

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `workshop_transcripts` | Raw transcripts from Agent 1 |
| `chunk_embeddings` | Vector embeddings for RAG |
| `ai_summaries` | Generated summaries |
| `generated_materials` | Final study materials |
| `course_progress` | Tracking course status |

## ⏱️ Time Savings

| Task | Manual | With AI Agent | Savings |
|------|--------|---------------|---------|
| Watch 10hr course | 10 hours | 0 hours | 100% |
| Take notes | 3 hours | 0 hours | 100% |
| Create cheat sheet | 2 hours | 0 hours | 100% |
| Review for quiz | 1 hour | 30 min | 50% |
| **Total** | **16 hours** | **30 minutes** | **97%** |

## 🛠️ Tech Stack

- **n8n**: Workflow automation
- **PostgreSQL + pgvector**: Database + vector storage
- **Ollama**: Local LLM inference (llama3)
- **Groq Whisper**: Audio transcription
- **yt-dlp**: Video download
- **Telegram Bot**: Notifications

## 📚 Supported Platforms

- YouTube (videos/playlists)
- LinkedIn Learning
- Coursera
- Udemy
- Any yt-dlp supported URL

## 🔧 Configuration

See `config/config.yaml` for all available options.

## 📖 Documentation

- [workflow_plan.md](workflow_plan.md) - Detailed architecture plan
- [SETUP.md](docs/SETUP.md) - Installation guide
- [API.md](docs/API.md) - API documentation

## 🤝 Contributing

Contributions welcome! See CONTRIBUTING.md for guidelines.

## 📄 License

MIT License - see LICENSE for details.
