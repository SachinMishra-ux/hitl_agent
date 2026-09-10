from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PostCreateRequest(BaseModel):
    topic: str = Field(..., description="Topic of the LinkedIn post", json_schema_extra={"example": "AI Agents in Enterprise Workflows"})
    key_points: Optional[str] = Field(
        "",
        description="Key ideas or talking points to emphasize",
        json_schema_extra={"example": "human-in-the-loop, autonomy with guardrails, compliance, ROI"},
    )
    tone: Optional[str] = Field(
        "professional yet engaging",
        description="Tone of voice",
        json_schema_extra={"example": "thought-provoking and visionary"},
    )
    audience: Optional[str] = Field(
        "industry professionals on LinkedIn",
        description="Target audience",
        json_schema_extra={"example": "CTOs, Engineering Leaders, AI Practitioners"},
    )


class ReviewRequest(BaseModel):
    approved: bool = Field(..., description="True to approve and publish to LinkedIn; False to request revisions")
    feedback: Optional[str] = Field(
        None,
        description="Specific revision instructions or feedback when approved is False",
        json_schema_extra={"example": "Make the opening hook punchier and shorten the middle paragraph."},
    )


class PostSummaryResponse(BaseModel):
    thread_id: str
    topic: str
    status: str
    current_draft: Optional[str] = None
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PostDetailResponse(BaseModel):
    thread_id: str
    status: str
    draft: Optional[str] = None
    topic: Optional[str] = None
    approved: Optional[bool] = False
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    post_error: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []
    is_waiting_approval: Optional[bool] = False
    interrupts: Optional[List[Any]] = []


class HealthResponse(BaseModel):
    status: str
    app_name: str
    llm_provider: str
    linkedin_author_urn: Optional[str]
    linkedin_connected: bool
    database_ok: bool
    smtp_configured: bool = False
    notification_email: Optional[str] = None
