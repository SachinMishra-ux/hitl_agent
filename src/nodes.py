import logging
from datetime import datetime
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from src.state import PostState, WorkflowStatus, RevisionHistoryItem
from src.llm import get_llm
from src.linkedin import LinkedInPublisher
from src.notifier import notifier

logger = logging.getLogger(__name__)


def generate_draft_node(state: PostState) -> Dict[str, Any]:
    """
    Node 1: Generates initial LinkedIn post draft based on topic, key points, tone, and audience.
    """
    info = state.get("info", {})
    topic = info.get("topic", "General Innovation")
    key_points = info.get("key_points", "")
    tone = info.get("tone", "professional yet engaging")
    audience = info.get("audience", "industry professionals on LinkedIn")

    prompt = f"""You are an expert LinkedIn ghostwriter. Create an engaging LinkedIn post based on the following:
Topic: {topic}
Key Points: {key_points}
Tone: {tone}
Target Audience: {audience}

Instructions:
1. Hook the reader in the first 1-2 lines.
2. Structure with clean paragraph breaks and bullet points for readability.
3. Keep it concise (150-250 words).
4. End with a conversational question or call-to-action to spark discussion.
5. Include 3-5 relevant hashtags at the bottom.
6. Output ONLY the post commentary text without conversational preamble."""

    logger.info(f"Generating initial LinkedIn draft for topic: '{topic}'")
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    draft = response.content.strip()

    history = state.get("history") or []
    history_item: RevisionHistoryItem = {
        "revision": len(history) + 1,
        "draft": draft,
        "feedback": None,
        "timestamp": datetime.now().isoformat(),
    }
    history.append(history_item)

    logger.info(f"Initial draft generated successfully ({len(draft)} chars)")
    return {
        "draft": draft,
        "approved": False,
        "history": history,
        "status": WorkflowStatus.WAITING_FOR_APPROVAL.value,
    }


def ask_for_feedback_node(state: PostState) -> Dict[str, Any]:
    """
    Node 2: Interrupts workflow for human review and dispatches notification.
    """
    draft = state.get("draft", "")
    topic = state.get("info", {}).get("topic", "LinkedIn Post")
    thread_id = state.get("thread_id", "default_thread")
    history = state.get("history") or []
    revision_number = len(history)

    logger.info(f"Triggering human review interrupt for thread {thread_id} (Revision {revision_number})")

    # Send notification (Email + In-App Notification Center)
    notifier.send_draft_ready_notification(
        thread_id=thread_id,
        topic=topic,
        draft=draft,
        revision=revision_number,
    )

    # Interrupt graph execution — resumes when user submits approval or feedback
    interrupt_payload = {
        "message": (
            "Your draft is ready. If you are okay with this, you can just approve "
            "or if you need any changes, you can just provide the changes."
        ),
        "draft": draft,
        "revision": revision_number,
    }
    human_response = interrupt(interrupt_payload)

    # Process resume response
    # Can be a string ("approve", "approved", or feedback text) or dict ({"approved": bool, "feedback": str})
    approved = False
    feedback = None

    if isinstance(human_response, dict):
        approved = bool(human_response.get("approved", False))
        feedback = human_response.get("feedback")
        # If user passed text in feedback saying 'approve', also treat as approved
        if feedback and feedback.strip().lower() in ["approve", "approved", "ok", "looks good"]:
            approved = True
    elif isinstance(human_response, str):
        cleaned = human_response.strip().lower()
        if cleaned in ["approve", "approved", "ok", "yes", "looks good"]:
            approved = True
            feedback = None
        else:
            approved = False
            feedback = human_response.strip()

    logger.info(f"Human response received: approved={approved}, feedback='{feedback}'")

    # Update history item with feedback if given
    if history and feedback:
        history[-1]["feedback"] = feedback

    return {
        "human_feedback": feedback,
        "approved": approved,
        "history": history,
        "status": (
            WorkflowStatus.PUBLISHED.value if approved else WorkflowStatus.REVISING.value
        ),
    }


def decide_next(state: PostState) -> str:
    """
    Conditional edge: routes to 'post_to_linkedin' if approved, else 'revise_draft'.
    """
    if state.get("approved", False):
        logger.info("Decision: Human approved. Routing to post_to_linkedin.")
        return "post_to_linkedin"
    else:
        logger.info("Decision: Changes requested. Routing to revise_draft.")
        return "revise_draft"


def revise_draft_node(state: PostState) -> Dict[str, Any]:
    """
    Node 3: Revises draft incorporating human reviewer feedback.
    """
    current_draft = state.get("draft", "")
    feedback = state.get("human_feedback", "Please refine the post.")
    info = state.get("info", {})
    topic = info.get("topic", "")
    tone = info.get("tone", "professional yet engaging")

    prompt = f"""You are an expert LinkedIn ghostwriter revising a draft according to client feedback.

Topic: {topic}
Tone: {tone}

CURRENT DRAFT:
\"\"\"
{current_draft}
\"\"\"

REVIEWER FEEDBACK:
\"\"\"
{feedback}
\"\"\"

Instructions:
1. Carefully address every point in the reviewer's feedback.
2. Maintain high LinkedIn readability, strong hook, and conversational tone.
3. Keep relevant hashtags.
4. Output ONLY the revised post text without conversational remarks."""

    logger.info("Generating revised draft based on feedback...")
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)])
    new_draft = response.content.strip()

    history = state.get("history") or []
    history_item: RevisionHistoryItem = {
        "revision": len(history) + 1,
        "draft": new_draft,
        "feedback": None,
        "timestamp": datetime.now().isoformat(),
    }
    history.append(history_item)

    logger.info(f"Revised draft created (Revision #{len(history)})")
    return {
        "draft": new_draft,
        "approved": False,
        "history": history,
        "status": WorkflowStatus.WAITING_FOR_APPROVAL.value,
    }


def post_to_linkedin_node(state: PostState) -> Dict[str, Any]:
    """
    Node 4: Publishes approved draft to LinkedIn via REST API.
    """
    draft = state.get("draft", "")
    logger.info("Publishing approved post to LinkedIn...")

    publisher = LinkedInPublisher()
    result = publisher.publish_post(draft)

    if result.get("success"):
        post_id = result.get("post_id")
        post_url = result.get("post_url")
        logger.info(f"Successfully published post! ID: {post_id}, URL: {post_url}")
        return {
            "final_post": draft,
            "post_id": post_id,
            "post_url": post_url,
            "post_error": None,
            "status": WorkflowStatus.PUBLISHED.value,
            "approved": True,
        }
    else:
        err = result.get("error", "Unknown error publishing to LinkedIn")
        logger.error(f"Failed to publish to LinkedIn: {err}")
        return {
            "final_post": draft,
            "post_error": err,
            "status": WorkflowStatus.ERROR.value,
            "approved": True,
        }
