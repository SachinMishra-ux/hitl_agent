# Human-in-the-Loop (HITL) LinkedIn Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-blue.svg)](https://github.com/langchain-ai/langgraph)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-ready **Human-in-the-Loop (HITL) Agent** for generating, reviewing, revising, and automatically publishing LinkedIn posts. Built with **LangGraph**, **Google Gemini**, **FastAPI**, **persistent SQLite checkpointing**, and **LinkedIn REST API (Version 202511)**.

---

## Key Capabilities

- **State Persistence Across Days/Weeks**: Uses `SqliteSaver` persistent checkpointing. A reviewer can take 1 hour, 3 days, or 7+ days to approve; the graph safely maintains its interrupt state on disk.
- **Asynchronous Human Review**: Automatically pauses at `ask_for_feedback` using LangGraph's native `interrupt()`.
- **Automated Notifications**: Dispatches an email notification to the reviewer with:
  - Draft content snippet.
  - Dedicated Review & Revision link (`/review/{thread_id}`).
  - 1-Click Quick Approve link (`/api/posts/{thread_id}/quick-approve`).
  - In-app Notification Center in the dashboard for local development and tracking.
- **Dynamic Revision Loops**: If the reviewer asks for changes, the agent rewrites the post incorporating the feedback and automatically enters a new review cycle.
- **Production LinkedIn Publishing**: Automatically posts to LinkedIn using the REST API (`https://api.linkedin.com/rest/posts`) once approved.
- **Full Web UI + REST API**: Includes an interactive dashboard with realistic LinkedIn feed previews and Swagger documentation (`/docs`).

---

## Architecture & Workflow

```mermaid
flowchart TD
    START([User Requests Post]) --> G[Generate Draft\n(Gemini 2.5 Flash)]
    G --> A[ask_for_feedback\n(Emits interrupt & sends notification)]
    A -.->|State persisted in SQLite| PAUSE[(PAUSE: Awaiting Human Review\n1-7+ Days)]
    PAUSE -->|Human submits review| C{Decision}
    C -->|Approved| P[Post to LinkedIn\nREST API]
    C -->|Feedback Provided| R[Revise Draft\n(Incorporates human feedback)]
    R --> A
    P --> END([Published on LinkedIn])
```

---

## Directory Structure

```
hitl_agent/
├── src/
│   ├── config.py            # Pydantic settings & env configuration
│   ├── state.py             # LangGraph state schema (PostState, History)
│   ├── llm.py               # Google Gemini (OpenAI-compatible) / Groq factory
│   ├── linkedin.py          # LinkedIn REST API client
│   ├── notifier.py          # Email & in-app notification service
│   ├── checkpointer.py      # SQLite checkpointer & metadata index
│   ├── nodes.py             # LangGraph nodes (generate, interrupt, revise, post)
│   ├── workflow.py          # Graph compilation and resume manager
│   ├── schemas.py           # Pydantic request/response models
│   ├── api.py               # FastAPI backend & routes
│   └── templates/           # Jinja2 HTML templates for Web UI
│       ├── base.html        # Modern Tailwind CSS layout
│       ├── index.html       # Post generator & approvals dashboard
│       └── review.html      # Dedicated review & feedback page
├── data/                    # Persistent storage for checkpoints (checkpoints.db)
├── tests/                   # Pytest automated test suite
├── .github/workflows/       # GitHub Actions AWS CI/CD pipeline
├── Dockerfile               # Production Docker container
├── docker-compose.yml       # Production docker-compose configuration
├── main.py                  # Application entrypoint
└── pyproject.toml           # Project dependencies
```

---

## Getting Started Locally

### 1. Prerequisites
- Python 3.12+
- Astral `uv` (recommended) or `pip`

### 2. Environment Variables
Create a `.env` file in the root directory:

```env
# LLM (Google Gemini)
GOOGLE_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-2.5-flash"

# LinkedIn REST API
LINKEDIN_ACCESS_TOKEN="your-oauth-access-token"
LINKEDIN_AUTHOR_URN="urn:li:person:your-urn-id"
LINKEDIN_API_VERSION="202511"

# App Settings
BASE_URL="http://localhost:8000"
NOTIFICATION_EMAIL="your-email@domain.com"

# Optional SMTP Settings (for real email delivery)
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
```

### 3. Install Dependencies & Run

```bash
# Install dependencies with uv
uv sync

# Run the FastAPI server
python main.py
```

Open your browser at:
- **Web UI Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Running Automated Tests

Run the full pytest suite:

```bash
uv run pytest -v
```

---

## API Reference

### `POST /api/posts`
Generates a new LinkedIn draft and dispatches notification:
```json
{
  "topic": "LangGraph in Enterprise",
  "key_points": "Human-in-the-loop, fault tolerance",
  "tone": "professional yet engaging",
  "audience": "AI engineers"
}
```

### `GET /api/posts`
Lists all posts, drafts, and approval statuses.

### `GET /api/posts/{thread_id}`
Retrieves post state, revision history, and pending interrupts.

### `POST /api/posts/{thread_id}/review`
Submits human approval or revision request:
```json
// To request changes:
{
  "approved": false,
  "feedback": "Make the opening hook punchier."
}

// To approve and publish:
{
  "approved": true
}
```

### `GET /api/posts/{thread_id}/quick-approve`
1-click approval URL directly from email notification.

---

## Deployment to AWS

Refer to [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions on deploying via GitHub Actions to Amazon ECR and AWS EC2.
