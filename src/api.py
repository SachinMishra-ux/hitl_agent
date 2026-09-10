import os
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.schemas import (
    PostCreateRequest,
    ReviewRequest,
    PostSummaryResponse,
    PostDetailResponse,
    HealthResponse,
)
from src.workflow import (
    start_post_workflow,
    resume_post_workflow,
    get_post_details,
    list_posts,
)
from src.notifier import notifier, notification_store
from src.linkedin import LinkedInPublisher

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Human-in-the-Loop Autonomous LinkedIn Publisher with LangGraph & Persistent Checkpointing",
    version="1.0.0",
)

# Template setup
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Web UI Routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    """
    Renders main dashboard UI.
    """
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/review/{thread_id}", response_class=HTMLResponse)
async def review_view(request: Request, thread_id: str):
    """
    Renders dedicated post review and approval page.
    """
    post = get_post_details(thread_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post thread '{thread_id}' not found")
    return templates.TemplateResponse(request=request, name="review.html", context={"post": post})


# ── REST API Endpoints ────────────────────────────────────────────────────────

@app.post("/api/posts", response_model=PostDetailResponse, status_code=201)
async def create_post_endpoint(req: PostCreateRequest):
    """
    Initiates a new post generation workflow.
    Generates initial draft, dispatches notification, and pauses for review.
    """
    try:
        result = start_post_workflow(
            topic=req.topic,
            key_points=req.key_points or "",
            tone=req.tone or "professional yet engaging",
            audience=req.audience or "industry professionals on LinkedIn",
        )
        return PostDetailResponse(
            thread_id=result["thread_id"],
            status=result["status"],
            draft=result["draft"],
            topic=result["topic"],
            approved=False,
            history=result.get("history", []),
            is_waiting_approval=True,
            interrupts=result.get("interrupts", []),
        )
    except Exception as e:
        logger.exception("Error initiating post generation")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts", response_model=List[PostSummaryResponse])
async def list_posts_endpoint():
    """
    Lists all posts with summary status and metadata.
    """
    posts = list_posts()
    return posts


@app.get("/api/posts/{thread_id}", response_model=PostDetailResponse)
async def get_post_endpoint(thread_id: str):
    """
    Retrieves full details, draft, history, and approval status for a specific post.
    """
    post = get_post_details(thread_id)
    if not post:
        raise HTTPException(status_code=404, detail=f"Post thread '{thread_id}' not found")

    return PostDetailResponse(
        thread_id=thread_id,
        status=post.get("status", "unknown"),
        draft=post.get("draft") or post.get("current_draft"),
        topic=post.get("info", {}).get("topic") or post.get("topic"),
        approved=post.get("approved", False),
        post_id=post.get("post_id"),
        post_url=post.get("post_url"),
        post_error=post.get("post_error") or post.get("error"),
        history=post.get("history", []),
        is_waiting_approval=post.get("is_waiting_approval", False),
        interrupts=post.get("interrupts", []),
    )


@app.post("/api/posts/{thread_id}/review", response_model=PostDetailResponse)
async def review_post_endpoint(thread_id: str, req: ReviewRequest):
    """
    Submits human reviewer decision:
    - approved=True: Resumes workflow, posts draft to LinkedIn, reaches END.
    - approved=False: Resumes workflow with feedback, revises draft, and pauses again for review.
    """
    try:
        result = resume_post_workflow(
            thread_id=thread_id,
            approved=req.approved,
            feedback=req.feedback,
        )
        return PostDetailResponse(
            thread_id=thread_id,
            status=result["status"],
            draft=result.get("draft"),
            approved=result.get("approved", False),
            post_id=result.get("post_id"),
            post_url=result.get("post_url"),
            post_error=result.get("post_error"),
            history=result.get("history", []),
            is_waiting_approval=result.get("status") == "waiting_for_approval",
            interrupts=result.get("interrupts", []),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error resuming post workflow {thread_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/{thread_id}/quick-approve")
async def quick_approve_endpoint(thread_id: str):
    """
    1-Click direct approval endpoint typically clicked from the notification email.
    Approves the draft and redirects to the review page showing published status.
    """
    try:
        resume_post_workflow(thread_id=thread_id, approved=True)
    except Exception as e:
        logger.warning(f"Quick approve note: {e}")
    return RedirectResponse(url=f"/review/{thread_id}", status_code=303)


@app.get("/api/notifications")
async def get_notifications_endpoint():
    """
    Returns dispatched notification logs (both sent via SMTP and recorded in-app).
    """
    return notification_store.get_all()


@app.post("/api/notifications/test-email")
async def send_test_email_endpoint():
    """
    Attempts to send a test email using configured SMTP settings.
    """
    result = notifier.send_test_email()
    return result


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check verifying LLM, LinkedIn connection, database status, and SMTP email setup.
    """
    linkedin = LinkedInPublisher()
    cred_check = linkedin.verify_credentials()
    linkedin_ok = cred_check.get("valid", False)

    db_ok = os.path.exists(settings.SQLITE_DB_PATH) or os.path.exists(settings.DATA_DIR)

    llm_provider = "Google Gemini" if settings.GOOGLE_API_KEY else ("Groq" if settings.GROQ_API_KEY else "OpenAI")

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        llm_provider=llm_provider,
        linkedin_author_urn=settings.LINKEDIN_AUTHOR_URN,
        linkedin_connected=linkedin_ok,
        database_ok=db_ok,
        smtp_configured=notifier.is_configured,
        notification_email=settings.NOTIFICATION_EMAIL,
    )
