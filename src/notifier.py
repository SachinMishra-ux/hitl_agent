import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class NotificationStore:
    """
    In-app storage for notifications, accessible via UI and API.
    """
    def __init__(self):
        self._notifications: List[Dict[str, Any]] = []

    def record(self, notification: Dict[str, Any]):
        self._notifications.insert(0, notification)
        # Keep maximum 100 notifications
        if len(self._notifications) > 100:
            self._notifications.pop()

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._notifications)

    def clear(self):
        self._notifications.clear()


notification_store = NotificationStore()


class EmailNotifier:
    """
    Email notification service for Human-in-the-Loop review requests.
    """

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_USE_TLS
        self.recipient_email = settings.NOTIFICATION_EMAIL
        self.sender_email = settings.SENDER_EMAIL or "no-reply@hitlagent.local"
        self.base_url = settings.BASE_URL.rstrip("/")

    def send_draft_ready_notification(
        self,
        thread_id: str,
        topic: str,
        draft: str,
        revision: int = 1,
    ) -> Dict[str, Any]:
        """
        Sends an email notification informing the user that a draft is ready for review.
        """
        review_url = f"{self.base_url}/review/{thread_id}"
        quick_approve_url = f"{self.base_url}/api/posts/{thread_id}/quick-approve"

        subject = f"LinkedIn Post Draft Ready for Review: {topic}"
        if revision > 1:
            subject = f"Revised LinkedIn Post Draft Ready (v{revision}): {topic}"

        # Standard notification text requested by user
        message_text = (
            "Your draft is ready. If you are okay with this, you can just approve "
            "or if you need any changes, you can just provide the changes."
        )

        plain_text = f"""Hello,

{message_text}

---
TOPIC: {topic}
REVISION: {revision}

DRAFT CONTENT:
{draft}
---

To Review, Edit, or Request Changes:
{review_url}

To 1-Click Quick Approve & Publish directly to LinkedIn:
{quick_approve_url}

Thank you,
HITL Agent System
"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px; }}
    .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .header {{ background: #0A66C2; color: #ffffff; padding: 24px; text-align: center; }}
    .content {{ padding: 24px; color: #1f2937; line-height: 1.6; }}
    .draft-box {{ background: #f9fafb; border: 1px solid #e5e7eb; border-left: 4px solid #0A66C2; padding: 16px; border-radius: 6px; margin: 20px 0; white-space: pre-wrap; font-size: 15px; color: #111827; }}
    .actions {{ display: flex; gap: 12px; margin: 28px 0 12px; }}
    .btn {{ display: inline-block; padding: 12px 24px; font-weight: 600; text-decoration: none; border-radius: 6px; text-align: center; font-size: 14px; }}
    .btn-primary {{ background: #0A66C2; color: #ffffff !important; }}
    .btn-secondary {{ background: #10B981; color: #ffffff !important; }}
    .footer {{ background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h2 style="margin:0;">HITL LinkedIn Agent</h2>
      <p style="margin:4px 0 0; opacity:0.9; font-size:14px;">Human Approval Requested</p>
    </div>
    <div class="content">
      <p style="font-size: 16px; font-weight: 500; color: #111827;">
        Your draft is ready. If you are okay with this, you can just approve or if you need any changes, you can just provide the changes.
      </p>
      
      <p><strong>Topic:</strong> {topic}<br><strong>Version:</strong> Revision #{revision}</p>
      
      <div class="draft-box">{draft}</div>

      <div class="actions">
        <a href="{review_url}" class="btn btn-primary" style="margin-right: 10px;">Review & Provide Feedback</a>
        <a href="{quick_approve_url}" class="btn btn-secondary">1-Click Approve & Post</a>
      </div>
      <p style="font-size: 12px; color: #6b7280; margin-top: 16px;">
        You can approve this at any time (today, tomorrow, or in 7 days). Your draft is safely saved.
      </p>
    </div>
    <div class="footer">
      Thread ID: <code>{thread_id}</code> &bull; HITL Agent Automated Notification
    </div>
  </div>
</body>
</html>"""

        notification_record = {
            "id": f"notif_{int(datetime.now().timestamp())}_{thread_id[:6]}",
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "message": message_text,
            "topic": topic,
            "revision": revision,
            "recipient": self.recipient_email,
            "review_url": review_url,
            "quick_approve_url": quick_approve_url,
            "draft_snippet": draft[:150] + "..." if len(draft) > 150 else draft,
            "sent_via_smtp": False,
        }

        # Attempt to send real email if SMTP credentials are provided
        if self.smtp_host and self.smtp_user and self.smtp_password and self.recipient_email:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = self.recipient_email

                part1 = MIMEText(plain_text, "plain")
                part2 = MIMEText(html_content, "html")
                msg.attach(part1)
                msg.attach(part2)

                logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.sender_email, [self.recipient_email], msg.as_string())
                server.quit()

                notification_record["sent_via_smtp"] = True
                logger.info(f"Email successfully sent to {self.recipient_email}")
            except Exception as e:
                logger.warning(f"Failed to send email via SMTP: {e}. Notification recorded in in-app store.")
                notification_record["smtp_error"] = str(e)
        else:
            logger.info(
                f"[NOTIFICATION LOG] Draft ready for review (Thread: {thread_id}). "
                f"Review URL: {review_url} | Quick Approve: {quick_approve_url}"
            )

        # Store in notification center
        notification_store.record(notification_record)
        return notification_record


notifier = EmailNotifier()
