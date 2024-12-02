import smtplib
import requests
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for error messages
CARRIER_URL_ERROR = "Carrier URL is required."
TOKEN_ERROR = "Token is required."


class CarrierClient:
    """
    Handles interactions with the Carrier API, including downloading reports and managing authentication.
    """

    def __init__(self, base_url: str, token: str):
        """
        Initializes the CarrierClient.

        :param base_url: Base URL of the Carrier API
        :param token: API token for authentication
        """
        if not base_url:
            raise ValueError(CARRIER_URL_ERROR)
        if not token:
            raise ValueError(TOKEN_ERROR)
        self.base_url = base_url
        self.token = token

    def get_headers(self) -> Dict[str, str]:
        """
        Returns headers for authenticated API requests.

        :return: Dictionary of headers
        """
        return {'Authorization': f'Bearer {self.token}'}

    def fetch_tickets(self, project_id: str, board_id: str) -> List[Dict[str, Any]]:
        """
        Fetches tickets from the Carrier API.

        :param project_id: Project ID
        :param board_id: Board ID
        :return: List of tickets
        """
        issues_url = f"{self.base_url}/api/v1/issues/issues/{project_id}?board_id={board_id}&limit=100"
        response = requests.get(issues_url, headers=self.get_headers())
        response.raise_for_status()
        return response.json().get("rows", [])

    def fetch_audit_logs(self, project_id: str, auditable_ids: List[int], days: int = 5) -> List[Dict[str, Any]]:
        """
        Fetches audit logs for the given project ID and filters logs for the last `days` days.

        :param project_id: Project ID
        :param auditable_ids: List of auditable IDs
        :param days: Number of days to look back for audit logs
        :return: List of audit logs
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            recent_logs = []
            for auditable_id in auditable_ids:
                related_entities = json.dumps({"auditable_type": "Issue", "auditable_id": auditable_id})
                audit_logs_url = f"{self.base_url}/api/v1/audit_logs/logs/{project_id}?auditable_type=Issue&auditable_id={auditable_id}&related_entities={related_entities}&offset=0&limit=100"
                response = requests.get(audit_logs_url, headers=self.get_headers())
                response.raise_for_status()
                logs = response.json().get("rows", [])
                recent_logs.extend(
                    [log for log in logs if datetime.strptime(log["created_at"], "%Y-%m-%dT%H:%M:%S.%f") >= start_date])
            logger.info(f"Fetched {len(recent_logs)} audit logs for the last {days} days.")
            return recent_logs
        except requests.RequestException as e:
            logger.error(f"Failed to fetch audit logs: {e}")
            return []


class EmailNotifier:
    """
    Handles email notifications for processed reports.
    """

    def __init__(self, smtp_settings: Dict[str, Any]):
        """
        Initializes the email notifier.

        :param smtp_settings: Dictionary containing SMTP configuration
        """
        self.smtp_settings = smtp_settings
        required_keys = ["smtp_host", "smtp_port", "smtp_sender", "smtp_user", "smtp_password", "smtp_email_recipients"]
        if not all(key in smtp_settings for key in required_keys):
            raise ValueError("Missing required SMTP settings")

    def send_email(self, subject: str, body: str) -> None:
        """
        Sends an email with the given subject and body.

        :param subject: Email subject
        :param body: Email body
        """
        logger.info(f"Sending email with subject: {subject}")
        try:
            with smtplib.SMTP_SSL(self.smtp_settings["smtp_host"], self.smtp_settings["smtp_port"]) as server:
                server.login(self.smtp_settings["smtp_user"], self.smtp_settings["smtp_password"])
                msg = MIMEMultipart()
                msg['From'] = self.smtp_settings["smtp_sender"]
                msg['To'] = ", ".join(self.smtp_settings["smtp_email_recipients"])
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'html'))
                server.sendmail(self.smtp_settings["smtp_sender"], self.smtp_settings["smtp_email_recipients"],
                                msg.as_string())
                logger.info("Email sent successfully")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")


def categorize_tickets(tickets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    tickets_summary = {
        "open": [],
        "blocked": [],
        "in_progress": [],
        "in_review": [],
        "done": []
    }

    risks = []

    for ticket in tickets:
        if ticket["type"] == "Risk":
            risks.append(ticket)
        else:
            status = ticket["status"]
            if status in tickets_summary:
                tickets_summary[status].append(ticket)

    # Sort tickets within each status category by their start_date
    for status, tickets_list in tickets_summary.items():
        tickets_summary[status] = sorted(tickets_list, key=lambda x: x.get("start_date", ""))

    return tickets_summary, risks


def get_recent_done_tickets(audit_logs: List[Dict[str, Any]], tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recent_done_tickets = []
    for log in audit_logs:
        if log["action"] == "update" and log["changes"] and log["changes"].get("status", {}).get("new_value") == "DONE":
            ticket_id = log["auditable_id"]
            ticket = next((t for t in tickets if t["id"] == ticket_id), None)
            if ticket:
                # Convert completion date to human-readable format
                completion_date = datetime.strptime(log["created_at"], "%Y-%m-%dT%H:%M:%S.%f").strftime(
                    "%Y-%m-%d %H:%M:%S")
                ticket["completion_date"] = completion_date
                recent_done_tickets.append(ticket)
    return recent_done_tickets


def lambda_handler(event, context):
    try:
        token = event.get("token")
        base_url = event.get("base_url")
        project_id = event.get("project_id")
        host = event.get("host")
        port = event.get("port")
        user = event.get("user")
        password = event.get("passwd")
        sender = event.get("sender")
        board_id = event.get("board_id")
        recipients = event.get("recipients").split(",")

        carrier_client = CarrierClient(base_url, token)
        tickets = carrier_client.fetch_tickets(project_id, board_id)
        tickets_summary, risks = categorize_tickets(tickets)

        # Extract auditable IDs from tickets
        auditable_ids = [ticket["id"] for ticket in tickets]

        # Fetch audit logs and get recently completed tickets
        audit_logs = carrier_client.fetch_audit_logs(project_id, auditable_ids)
        recent_done_tickets = get_recent_done_tickets(audit_logs, tickets)

        # Extract engagement information from the first ticket
        engagement = tickets[0]["engagement"] if tickets else {"name": "N/A"}

        # Get current date and time
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        env = Environment(loader=FileSystemLoader('./template/'))
        template = env.get_template("board_summary.html")
        email_body = template.render(tickets_summary=tickets_summary, risks=risks, engagement=engagement,
                                     current_date=current_date, recent_done_tickets=recent_done_tickets)

        smtp_settings = {
            "smtp_host": host,
            "smtp_port": port,
            "smtp_sender": sender,
            "smtp_user": user,
            "smtp_password": password,
            "smtp_email_recipients": recipients
        }

        email_notifier = EmailNotifier(smtp_settings)
        email_notifier.send_email("Project Status Update", email_body)

    except Exception as e:
        logger.error("An error occurred", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }
    return {
        'statusCode': 200,
        'body': json.dumps('Email has been sent')
    }


def handler_local(event: Dict[str, Any] = {}, context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Local handler for processing reports and sending email notifications.
    This function is intended for local debugging.

    :param event: Dictionary containing event data
    :param context: AWS Lambda context (optional)
    :return: Response dictionary
    """
    logger.info("[INFO] Starting local handler")
    try:
        base_url = event.get("base_url", "https://api.example.com")
        token = event.get("token", "your_token_here")
        project_id = event.get("project_id", "your_project_id_here")
        board_id = event.get("board_id", "your_board_id_here")
        host = event.get("host", "smtp.example.com")
        port = event.get("port", 465)
        user = event.get("user", "your_user_here")
        password = event.get("passwd", "your_password_here")
        sender = event.get("sender", "sender@example.com")
        recipients = event.get("recipients", "recipient@example.com").split(",")

        carrier_client = CarrierClient(base_url, token)
        tickets = carrier_client.fetch_tickets(project_id, board_id)
        tickets_summary, risks = categorize_tickets(tickets)

        # Extract auditable IDs from tickets
        auditable_ids = [ticket["id"] for ticket in tickets]

        # Fetch audit logs and get recently completed tickets
        audit_logs = carrier_client.fetch_audit_logs(project_id, auditable_ids)
        recent_done_tickets = get_recent_done_tickets(audit_logs, tickets)

        # Extract engagement information from the first ticket
        engagement = tickets[0]["engagement"] if tickets else {"name": "N/A"}

        # Get current date and time
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        env = Environment(loader=FileSystemLoader('./template/'))
        template = env.get_template("board_summary.html")
        email_body = template.render(tickets_summary=tickets_summary, risks=risks, engagement=engagement,
                                     current_date=current_date, recent_done_tickets=recent_done_tickets)

        smtp_settings = {
            "smtp_host": host,
            "smtp_port": port,
            "smtp_sender": sender,
            "smtp_user": user,
            "smtp_password": password,
            "smtp_email_recipients": recipients
        }

        email_notifier = EmailNotifier(smtp_settings)
        email_notifier.send_email("Project Status Update", email_body)

    except Exception as e:
        logger.error("An error occurred", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }
    return {
        'statusCode': 200,
        'body': json.dumps('Email has been sent')
    }


# # TO DEBUG
# if __name__ == "__main__":
#     handler_local()
