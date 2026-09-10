import logging
import re
from typing import Dict, Any, Optional
import requests
from src.config import settings

logger = logging.getLogger(__name__)


class LinkedInPublisher:
    """
    LinkedIn REST API Client for publishing text posts and validating credentials.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        author_urn: Optional[str] = None,
        api_version: Optional[str] = None,
        simulation_mode: Optional[bool] = None,
    ):
        self.access_token = access_token if access_token is not None else settings.LINKEDIN_ACCESS_TOKEN
        self.author_urn = author_urn if author_urn is not None else settings.LINKEDIN_AUTHOR_URN
        self.api_version = api_version if api_version is not None else settings.LINKEDIN_API_VERSION
        self.simulation_mode = (
            simulation_mode
            if simulation_mode is not None
            else settings.LINKEDIN_SIMULATION_MODE
        )

    def verify_credentials(self) -> Dict[str, Any]:
        """
        Validates the LinkedIn access token by querying the userinfo endpoint.
        Returns profile info on success or error details on failure.
        """
        if not self.access_token:
            return {"valid": False, "error": "Missing LINKEDIN_ACCESS_TOKEN in environment"}

        url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "valid": True,
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "sub": data.get("sub"),
                    "author_urn": self.author_urn,
                }
            else:
                return {
                    "valid": False,
                    "status_code": resp.status_code,
                    "error": resp.text,
                }
        except Exception as e:
            return {"valid": False, "error": f"Connection error: {str(e)}"}

    def publish_post(self, commentary: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Publishes a post commentary to LinkedIn using the REST API.
        """
        if self.simulation_mode or dry_run:
            logger.info("Simulation mode active: Simulating LinkedIn post publication.")
            fake_id = "urn:li:share:simulated_" + re.sub(r"[^a-zA-Z0-9]", "", commentary[:16])
            return {
                "success": True,
                "post_id": fake_id,
                "post_url": f"https://www.linkedin.com/feed/update/{fake_id}",
                "simulated": True,
            }

        if not self.access_token:
            err = "Missing LINKEDIN_ACCESS_TOKEN in environment."
            logger.error(err)
            return {"success": False, "error": err}

        if not self.author_urn:
            err = "Missing LINKEDIN_AUTHOR_URN in environment."
            logger.error(err)
            return {"success": False, "error": err}

        url = "https://api.linkedin.com/rest/posts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "LinkedIn-Version": self.api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        body = {
            "author": self.author_urn,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            logger.info(f"Publishing post to LinkedIn API (Version: {self.api_version})...")
            resp = requests.post(url, headers=headers, json=body, timeout=20)
            logger.info(f"LinkedIn API Response Status: {resp.status_code}")

            if 200 <= resp.status_code < 300:
                post_id = resp.headers.get("x-restli-id")
                if not post_id and resp.text:
                    try:
                        data = resp.json()
                        post_id = data.get("id") or data.get("URN")
                    except Exception:
                        pass

                post_id = post_id or "published"
                post_url = f"https://www.linkedin.com/feed/update/{post_id}" if "urn:li:" in post_id else "https://www.linkedin.com/feed/"

                return {
                    "success": True,
                    "post_id": post_id,
                    "post_url": post_url,
                    "status_code": resp.status_code,
                }
            else:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get("message") or str(error_data)
                except Exception:
                    error_msg = resp.text

                err = f"LinkedIn API error (HTTP {resp.status_code}): {error_msg}"
                logger.error(err)
                return {"success": False, "error": err, "status_code": resp.status_code}

        except Exception as e:
            err = f"Exception occurred while calling LinkedIn API: {str(e)}"
            logger.error(err)
            return {"success": False, "error": err}
