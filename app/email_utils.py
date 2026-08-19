from pathlib import Path
from jinja2 import Template
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _render_template(filename: str, **context) -> str:
    template_str = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    return Template(template_str).render(**context)


def send_email(to_email: str, subject: str, template_name: str, **context):
    html_body = _render_template(template_name, **context)

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.ZOHO_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=20) as server:
        server.login(settings.ZOHO_EMAIL, settings.ZOHO_APP_PASSWORD)
        server.send_message(msg)


def send_confirmation_email(to_email: str, name: str, link: str):
    send_email(
        to_email=to_email,
        subject="Verify your Wenyfour email address",
        template_name="confirmemailtemplate.html",
        name=name,
        link=link,
    )


def send_password_reset_email(to_email: str, name: str, link: str):
    send_email(
        to_email=to_email,
        subject="Reset your Wenyfour password",
        template_name="forgotpasswordtemplate.html",
        name=name,
        link=link,
    )


