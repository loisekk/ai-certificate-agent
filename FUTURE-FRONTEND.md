# Future Frontend Plans

## Modern Web Interface (Coming Soon)

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FUTURE WEB INTERFACE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Frontend (React/Next.js)                                       │
│  ├── Course Input Form                                          │
│  ├── Progress Dashboard                                         │
│  ├── Generated Materials Viewer                                 │
│  └── Download .md Files                                        │
│                                                                 │
│  Backend (FastAPI/Express)                                      │
│  ├── API Endpoints                                              │
│  ├── WebSocket for real-time progress                          │
│  ├── File serving for .md downloads                            │
│  └── Authentication                                            │
│                                                                 │
│  Agents (Background Workers)                                    │
│  ├── SubtitleWatcher (extracts subtitles)                      │
│  ├── ContentSummarizer (generates study materials)             │
│  └── NotificationService (sends alerts)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Features

| Feature | Description |
|---------|-------------|
| **Course Input** | Paste YouTube/LinkedIn/Coursera URL |
| **Real-time Progress** | WebSocket updates on processing status |
| **Materials Viewer** | View study-guide, cheat-sheet, key-concepts |
| **Download .md** | One-click download of all materials |
| **Course Library** | Browse previously processed courses |
| **Search** | Full-text search across all materials |

### UI Components

```
┌─────────────────────────────────────────────────────────────┐
│  🎓 AI Certificate Agent                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Enter Course URL                                   │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │ https://youtube.com/playlist?list=...       │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  │  [Process Course]                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Processing: Stanford CS229 ML                      │   │
│  │  ████████████████░░░░ 80%                          │   │
│  │  Videos: 17/21 | Words: 185,000 | Time: 1:30      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Generated Materials                               │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐        │   │
│  │  │ 📖 Study  │ │ 📋 Cheat  │ │ 💡 Key    │        │   │
│  │  │ Guide     │ │ Sheet     │ │ Concepts  │        │   │
│  │  │ [View]    │ │ [View]    │ │ [View]    │        │   │
│  │  │ [Download]│ │ [Download]│ │ [Download]│        │   │
│  │  └───────────┘ └───────────┘ └───────────┘        │   │
│  │                                                     │   │
│  │  [📥 Download All as ZIP]                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Course Library                                     │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │ Stanford CS229 ML          │ 21 videos │ ✅ │   │   │
│  │  │ Google AI Essentials       │ 10 videos │ ✅ │   │   │
│  │  │ LinkedIn Gen AI            │ 6 videos  │ ⏳ │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React/Next.js | User interface |
| UI Components | shadcn/ui | Beautiful components |
| State Management | Zustand | Lightweight state |
| Backend API | FastAPI | REST API |
| Real-time | WebSocket | Progress updates |
| Database | PostgreSQL | Store courses/materials |
| File Storage | Local/S3 | Store .md files |
| Queue | Redis/Bull | Background jobs |

### API Endpoints

```yaml
# Course Management
POST /api/courses              # Start processing
GET  /api/courses              # List all courses
GET  /api/courses/{id}         # Get course details
DELETE /api/courses/{id}       # Delete course

# Materials
GET  /api/courses/{id}/materials           # Get all materials
GET  /api/courses/{id}/materials/study     # Get study guide
GET  /api/courses/{id}/materials/cheat     # Get cheat sheet
GET  /api/courses/{id}/materials/concepts  # Get key concepts
GET  /api/courses/{id}/download            # Download ZIP

# Progress
GET  /api/courses/{id}/progress    # Get progress
WS   /ws/progress/{id}            # Real-time updates
```

### Development Roadmap

| Phase | Timeline | Features |
|-------|----------|----------|
| **Phase 1** | Week 1-2 | Basic UI, course input, progress display |
| **Phase 2** | Week 3-4 | Materials viewer, download functionality |
| **Phase 3** | Week 5-6 | Course library, search, authentication |
| **Phase 4** | Week 7-8 | Polish, deployment, mobile responsive |

### Design Principles

1. **Clean & Modern** - shadcn/ui components, dark mode
2. **Fast** - Optimistic updates, skeleton loading
3. **Responsive** - Works on desktop and mobile
4. **Accessible** - WCAG 2.1 compliant
5. **Beautiful** - Professional design, not generic

---

**Status**: Planned
**Estimated Start**: After core agents are stable
**Stack**: React + FastAPI + PostgreSQL
