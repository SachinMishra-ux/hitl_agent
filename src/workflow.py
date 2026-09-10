import logging
import uuid
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from src.state import PostState, WorkflowStatus
from src.nodes import (
    generate_draft_node,
    ask_for_feedback_node,
    decide_next,
    revise_draft_node,
    post_to_linkedin_node,
)
from src.checkpointer import (
    get_checkpointer,
    save_post_metadata,
    get_post_metadata,
    get_all_posts_metadata,
)

logger = logging.getLogger(__name__)

_graph_instance = None


def build_workflow_graph() -> StateGraph:
    """
    Builds and compiles the Human-in-the-Loop StateGraph with SQLite checkpointing.
    """
    builder = StateGraph(PostState)

    # 1. Add nodes
    builder.add_node("generate_draft", generate_draft_node)
    builder.add_node("ask_for_feedback", ask_for_feedback_node)
    builder.add_node("revise_draft", revise_draft_node)
    builder.add_node("post_to_linkedin", post_to_linkedin_node)

    # 2. Add edges
    builder.add_edge(START, "generate_draft")
    builder.add_edge("generate_draft", "ask_for_feedback")

    # 3. Conditional routing from ask_for_feedback
    builder.add_conditional_edges(
        "ask_for_feedback",
        decide_next,
        {
            "post_to_linkedin": "post_to_linkedin",
            "revise_draft": "revise_draft",
        },
    )

    # 4. Loop from revise_draft back to ask_for_feedback
    builder.add_edge("revise_draft", "ask_for_feedback")

    # 5. Finish after posting to LinkedIn
    builder.add_edge("post_to_linkedin", END)

    checkpointer = get_checkpointer()
    compiled_graph = builder.compile(checkpointer=checkpointer)
    logger.info("Compiled HITL StateGraph with persistent SQLite checkpointer.")
    return compiled_graph


def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_workflow_graph()
    return _graph_instance


def start_post_workflow(
    topic: str,
    key_points: str = "",
    tone: str = "professional yet engaging",
    audience: str = "industry professionals on LinkedIn",
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Initiates a new post generation workflow.
    Executes initial draft generation, dispatches notification, and pauses at human review.
    """
    if not thread_id:
        thread_id = f"post_{uuid.uuid4().hex[:10]}"

    config = {"configurable": {"thread_id": thread_id}}
    graph = get_graph()

    initial_state: PostState = {
        "thread_id": thread_id,
        "info": {
            "topic": topic,
            "key_points": key_points,
            "tone": tone,
            "audience": audience,
        },
        "draft": "",
        "human_feedback": None,
        "approved": False,
        "final_post": None,
        "post_id": None,
        "post_url": None,
        "post_error": None,
        "history": [],
        "status": WorkflowStatus.DRAFTING.value,
    }

    logger.info(f"Starting workflow for thread {thread_id} with topic '{topic}'")
    # Invoke will run generate_draft, then ask_for_feedback (which triggers notification and interrupts)
    graph.invoke(initial_state, config=config)

    # Check state after interrupt
    snapshot = graph.get_state(config)
    values = snapshot.values or {}
    draft = values.get("draft", "")
    status = WorkflowStatus.WAITING_FOR_APPROVAL.value

    # Update metadata index
    save_post_metadata(
        thread_id=thread_id,
        topic=topic,
        status=status,
        draft=draft,
    )

    return {
        "thread_id": thread_id,
        "status": status,
        "topic": topic,
        "draft": draft,
        "history": values.get("history", []),
        "interrupts": [i.value for i in (getattr(snapshot, "interrupts", []) or [])],
    }


def resume_post_workflow(
    thread_id: str,
    approved: bool,
    feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resumes an interrupted workflow with human decision (approve or revise).
    Can be called hours, days, or weeks after the post was created.
    """
    config = {"configurable": {"thread_id": thread_id}}
    graph = get_graph()

    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise ValueError(f"No workflow state found for thread_id '{thread_id}'")

    interrupts = getattr(snapshot, "interrupts", None) or []
    if not interrupts:
        # Check if already finished
        values = snapshot.values
        if values.get("status") == WorkflowStatus.PUBLISHED.value:
            return {
                "thread_id": thread_id,
                "status": WorkflowStatus.PUBLISHED.value,
                "message": "Post is already published to LinkedIn.",
                "post_id": values.get("post_id"),
                "post_url": values.get("post_url"),
                "draft": values.get("final_post") or values.get("draft"),
            }
        raise ValueError(f"Workflow '{thread_id}' is not currently paused for human approval.")

    # Prepare resume payload
    resume_payload = {
        "approved": approved,
        "feedback": feedback if feedback else ("approved" if approved else None),
    }

    logger.info(f"Resuming thread {thread_id} with approved={approved}, feedback='{feedback}'")
    # Resume graph execution
    graph.invoke(Command(resume=resume_payload), config=config)

    # Retrieve updated snapshot
    updated_snapshot = graph.get_state(config)
    values = updated_snapshot.values or {}

    new_status = values.get("status", WorkflowStatus.WAITING_FOR_APPROVAL.value)
    current_draft = values.get("draft", "")
    post_id = values.get("post_id")
    post_url = values.get("post_url")
    error = values.get("post_error")
    topic = values.get("info", {}).get("topic", "LinkedIn Post")

    # Update metadata index
    save_post_metadata(
        thread_id=thread_id,
        topic=topic,
        status=new_status,
        draft=current_draft,
        post_id=post_id,
        post_url=post_url,
        error=error,
    )

    return {
        "thread_id": thread_id,
        "status": new_status,
        "approved": values.get("approved", False),
        "draft": current_draft,
        "post_id": post_id,
        "post_url": post_url,
        "post_error": error,
        "history": values.get("history", []),
        "interrupts": [i.value for i in (getattr(updated_snapshot, "interrupts", []) or [])],
    }


def get_post_details(thread_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches full post workflow state and history.
    """
    config = {"configurable": {"thread_id": thread_id}}
    graph = get_graph()
    snapshot = graph.get_state(config)

    if not snapshot or not snapshot.values:
        meta = get_post_metadata(thread_id)
        return meta

    values = dict(snapshot.values)
    values["thread_id"] = thread_id
    values["interrupts"] = [i.value for i in (getattr(snapshot, "interrupts", []) or [])]
    values["is_waiting_approval"] = len(values["interrupts"]) > 0
    return values


def list_posts() -> list:
    """
    Lists all posts from the metadata store.
    """
    return get_all_posts_metadata()
