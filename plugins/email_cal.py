"""
JARVIS Plugin: Email & Calendar
"""

import os
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from core.plugin_base import JarvisPlugin


class EmailPlugin(JarvisPlugin):
    NAME        = "email"
    CATEGORY    = "email_cal"
    DESCRIPTION = "Read/send emails via IMAP/SMTP. Configure in .env"
    ACTIONS     = [
        "read_email", "check_email", "inbox",
        "send_email", "send",
        "check_calendar", "list_events", "calendar",
    ]

    ACTIONS_PROMPT = """
EMAIL ACTIONS (category: "email_cal"):
  read_email  params: {"count":5,"folder":"INBOX"}
  send_email  params: {"to":"...","subject":"...","body":"..."}
  check_calendar  params: {}"""

    def handle(self, action: str, params: dict) -> str:
        if action in ("read_email", "check_email", "inbox"):
            return self._read_emails(params)
        elif action in ("send_email", "send"):
            return self._send_email(params)
        elif action in ("check_calendar", "list_events", "calendar"):
            return self._calendar_info()
        return f"Unknown email action: '{action}'"

    def _config(self):
        return {
            "email":       os.getenv("EMAIL_ADDRESS", ""),
            "password":    os.getenv("EMAIL_PASSWORD", ""),
            "imap_server": os.getenv("IMAP_SERVER", "imap.gmail.com"),
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port":   int(os.getenv("SMTP_PORT", "587")),
        }

    def _not_configured(self):
        return (
            "  📧 Email not configured.\n\n"
            "  Add to your .env file:\n"
            "    EMAIL_ADDRESS=your@gmail.com\n"
            "    EMAIL_PASSWORD=your_app_password\n\n"
            "  For Gmail, use an App Password:\n"
            "    myaccount.google.com → Security → App Passwords"
        )

    def _decode_str(self, s):
        if not s: return ""
        decoded, enc = decode_header(s)[0]
        if isinstance(decoded, bytes):
            return decoded.decode(enc or "utf-8", errors="ignore")
        return decoded

    def _read_emails(self, params: dict) -> str:
        cfg = self._config()
        if not cfg["email"] or not cfg["password"]:
            return self._not_configured()
        count  = int(params.get("count", 5))
        folder = params.get("folder", "INBOX")
        try:
            mail = imaplib.IMAP4_SSL(cfg["imap_server"])
            mail.login(cfg["email"], cfg["password"])
            mail.select(folder)
            _, data = mail.search(None, "ALL")
            ids    = data[0].split()[-count:]
            sep    = "  " + "─" * 48
            result = f"  📬 {folder} — Last {len(ids)} email(s):\n{sep}\n"
            for eid in reversed(ids):
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                result += (f"  From:    {self._decode_str(msg.get('From',''))}\n"
                           f"  Subject: {self._decode_str(msg.get('Subject','(none)'))}\n"
                           f"  Date:    {msg.get('Date','')}\n{sep}\n")
            mail.logout()
            return result
        except Exception as e:
            return f"  ⚠️  Could not read emails:\n     {e}"

    def _send_email(self, params: dict) -> str:
        cfg = self._config()
        if not cfg["email"] or not cfg["password"]:
            return self._not_configured()
        to      = params.get("to", params.get("recipient", "")).strip()
        subject = params.get("subject", "(no subject)").strip()
        body    = params.get("body", params.get("message", params.get("content", ""))).strip()
        if not to:   return "No recipient specified."
        if not body: return "No email body specified."
        try:
            msg            = MIMEMultipart()
            msg["From"]    = cfg["email"]
            msg["To"]      = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            server = smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"])
            server.starttls()
            server.login(cfg["email"], cfg["password"])
            server.sendmail(cfg["email"], to, msg.as_string())
            server.quit()
            return (f"  ✉️  Email sent!\n"
                    f"     To:      {to}\n"
                    f"     Subject: {subject}")
        except Exception as e:
            return f"  ⚠️  Failed to send email:\n     {e}"

    def _calendar_info(self) -> str:
        return (
            "  📅 Google Calendar is not yet connected.\n\n"
            "  To enable:\n"
            "    1. console.cloud.google.com → Enable Calendar API\n"
            "    2. Download credentials.json → place in jarvis/ folder\n"
            "    3. pip install google-api-python-client google-auth"
        )
