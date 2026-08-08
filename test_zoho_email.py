"""
Standalone Zoho SMTP Test

Run:

python test_zoho_email.py recipient@example.com
"""

import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from jinja2 import Template

# ==========================
# Zoho SMTP Configuration
# ==========================

ZOHO_EMAIL = "info@wenyfour.com"
ZOHO_APP_PASSWORD = "qanKaxhH5M2H"

SMTP_SERVER = "smtp.zoho.com"
SMTP_PORT = 465  # SSL


def send_test_email(to_email):
    msg = MIMEMultipart()
    msg["From"] = ZOHO_EMAIL
    msg["To"] = to_email
    msg["Subject"] = "Zoho SMTP Test - Wenyfour"

    body = """
Hello,

This is a test email from Zoho SMTP.
 
If you received this message, your SMTP configuration is working correctly.

Regards,
Nazeef
"""

    msg.attach(MIMEText(body, "plain"))

    try:
        print(f"Connecting to {SMTP_SERVER}:{SMTP_PORT}...")

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.set_debuglevel(1)  # Shows SMTP communication
            server.login(ZOHO_EMAIL, ZOHO_APP_PASSWORD)
            server.send_message(msg)

        print(f"\n✅ Email sent successfully to {to_email}")

    except smtplib.SMTPAuthenticationError as e:
        print("\n❌ Authentication failed.")
        print(e)

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage:")
        print("python test_zoho_email.py recipient@example.com")
        sys.exit(1)

    recipient = sys.argv[1]

    send_test_email(recipient)