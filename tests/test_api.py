import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from src.api import app
from src.state import WorkflowStatus

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "database_ok" in data


@patch("src.llm.ChatOpenAI.invoke")
def test_create_and_review_post_api(mock_llm):
    mock_llm.side_effect = [
        AIMessage(content="Generated Draft: Enterprise AI Agents with Human in the Loop #AI"),
        AIMessage(content="Revised Draft: Enterprise AI Agents with Human in the Loop (V2) #AI"),
    ]

    with patch("src.nodes.LinkedInPublisher.publish_post") as mock_publish:
        mock_publish.return_value = {
            "success": True,
            "post_id": "urn:li:share:api_test_12345",
            "post_url": "https://www.linkedin.com/feed/update/urn:li:share:api_test_12345",
        }

        # 1. Create post
        payload = {
            "topic": "API Testing for HITL Agent",
            "key_points": "fastapi, automated testing, quality assurance",
            "tone": "professional yet engaging",
            "audience": "software engineers",
        }
        create_res = client.post("/api/posts", json=payload)
        assert create_res.status_code == 201
        created_data = create_res.json()
        thread_id = created_data["thread_id"]
        assert created_data["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value
        assert "Generated Draft" in created_data["draft"]
        assert created_data["is_waiting_approval"] is True

        # 2. Get post details
        get_res = client.get(f"/api/posts/{thread_id}")
        assert get_res.status_code == 200
        assert get_res.json()["thread_id"] == thread_id

        # 3. Request revision
        review_payload = {
            "approved": False,
            "feedback": "Add an example of FastAPI in action.",
        }
        rev_res = client.post(f"/api/posts/{thread_id}/review", json=review_payload)
        assert rev_res.status_code == 200
        rev_data = rev_res.json()
        assert rev_data["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value
        assert "Revised Draft" in rev_data["draft"]

        # 4. Approve post
        approve_payload = {"approved": True}
        app_res = client.post(f"/api/posts/{thread_id}/review", json=approve_payload)
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["status"] == WorkflowStatus.PUBLISHED.value
        assert app_data["post_id"] == "urn:li:share:api_test_12345"


def test_ui_templates():
    # Test dashboard render
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert "Autonomous Content Generation with Human Oversight" in home_res.text

    # Test notifications endpoint
    notif_res = client.get("/api/notifications")
    assert notif_res.status_code == 200
    assert isinstance(notif_res.json(), list)

    # Test test-email endpoint when unconfigured
    test_mail_res = client.post("/api/notifications/test-email")
    assert test_mail_res.status_code == 200
    assert test_mail_res.json()["success"] is False  # Fails gracefully when SMTP is not configured

