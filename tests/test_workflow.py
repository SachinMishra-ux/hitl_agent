import uuid
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage

from src.workflow import (
    start_post_workflow,
    resume_post_workflow,
    get_post_details,
)
from src.state import WorkflowStatus


@patch("src.llm.ChatOpenAI.invoke")
def test_full_hitl_workflow_lifecycle(mock_llm):
    # Mock LLM generation and revision
    mock_llm.side_effect = [
        AIMessage(content="Draft 1: Exploring Human-in-the-loop AI Agents in Enterprise #AI #Tech"),
        AIMessage(content="Draft 2 (Revised): Hook: The Future of Agentic Automation is HITL. #Innovation"),
    ]

    # Patch LinkedIn publisher to avoid live posting during test
    with patch("src.nodes.LinkedInPublisher.publish_post") as mock_publish:
        mock_publish.return_value = {
            "success": True,
            "post_id": "urn:li:share:test_987654",
            "post_url": "https://www.linkedin.com/feed/update/urn:li:share:test_987654",
        }

        test_thread = f"test_thread_{uuid.uuid4().hex[:8]}"

        # Step 1: Start workflow
        res1 = start_post_workflow(
            topic="HITL Agent Automation",
            key_points="reliability, human guardrails, enterprise deployment",
            thread_id=test_thread,
        )

        assert res1["thread_id"] == test_thread
        assert res1["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value
        assert "Draft 1" in res1["draft"]
        assert len(res1["interrupts"]) > 0

        # Step 2: Request revisions (approved=False with feedback)
        res2 = resume_post_workflow(
            thread_id=test_thread,
            approved=False,
            feedback="Make the opening hook stronger and mention guardrails explicitly.",
        )

        assert res2["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value
        assert "Draft 2 (Revised)" in res2["draft"]
        assert len(res2["history"]) == 2
        assert len(res2["interrupts"]) > 0

        # Step 3: Approve draft (approved=True)
        res3 = resume_post_workflow(
            thread_id=test_thread,
            approved=True,
        )

        assert res3["status"] == WorkflowStatus.PUBLISHED.value
        assert res3["approved"] is True
        assert res3["post_id"] == "urn:li:share:test_987654"
        assert "linkedin.com/feed/update" in res3["post_url"]

        # Step 4: Verify persistence - retrieve post details from SQLite checkpointer
        details = get_post_details(test_thread)
        assert details is not None
        assert details["status"] == WorkflowStatus.PUBLISHED.value
        assert details["post_id"] == "urn:li:share:test_987654"
