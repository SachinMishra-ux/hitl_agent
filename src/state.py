from enum import Enum
from typing import TypedDict, Optional, List, Dict, Any


class WorkflowStatus(str, Enum):
    DRAFTING = "drafting"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    REVISING = "revising"
    PUBLISHED = "published"
    ERROR = "error"


class RevisionHistoryItem(TypedDict, total=False):
    revision: int
    draft: str
    feedback: Optional[str]
    timestamp: str


class PostState(TypedDict, total=False):
    thread_id: str
    info: Dict[str, Any]
    draft: str
    human_feedback: Optional[str]
    approved: bool
    final_post: Optional[str]
    post_id: Optional[str]
    post_url: Optional[str]
    post_error: Optional[str]
    history: List[RevisionHistoryItem]
    status: str
