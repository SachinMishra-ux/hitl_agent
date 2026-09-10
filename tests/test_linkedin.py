import pytest
from unittest.mock import patch, MagicMock
from src.linkedin import LinkedInPublisher


def test_simulation_mode_publish():
    publisher = LinkedInPublisher(simulation_mode=True)
    result = publisher.publish_post("This is a test post about AI Agents.")
    assert result["success"] is True
    assert "post_id" in result
    assert "post_url" in result
    assert result.get("simulated") is True
    assert "linkedin.com/feed/update" in result["post_url"]


def test_missing_credentials():
    publisher = LinkedInPublisher(access_token="", author_urn="", simulation_mode=False)
    result = publisher.publish_post("Test post")
    assert result["success"] is False
    assert "Missing" in result["error"]


@patch("requests.post")
def test_mock_successful_post(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.headers = {"x-restli-id": "urn:li:share:123456789"}
    mock_resp.json.return_value = {"id": "urn:li:share:123456789"}
    mock_post.return_value = mock_resp

    publisher = LinkedInPublisher(
        access_token="test_token",
        author_urn="urn:li:person:123",
        simulation_mode=False,
    )
    result = publisher.publish_post("Draft test commentary")

    assert result["success"] is True
    assert result["post_id"] == "urn:li:share:123456789"
    assert "https://www.linkedin.com/feed/update/urn:li:share:123456789" in result["post_url"]


@patch("requests.post")
def test_mock_failed_post_error_handling(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"message": "Not enough permissions to post"}
    mock_post.return_value = mock_resp

    publisher = LinkedInPublisher(
        access_token="test_token",
        author_urn="urn:li:person:123",
        simulation_mode=False,
    )
    result = publisher.publish_post("Draft test commentary")

    assert result["success"] is False
    assert "LinkedIn API error (HTTP 403)" in result["error"]
