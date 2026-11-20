"""Обычные учебные приглашения через аутентифицированный SMTP."""

from email.message import EmailMessage
from email.utils import formatdate
import os
from pathlib import Path
import smtplib
import ssl

from settings import ORIGIN, normalize_address


HOST = os.environ.get("PORTAL_SMTP_HOST", "").strip()
PORT = int(os.environ.get("PORTAL_SMTP_PORT", "587"))
SENDER = normalize_address(os.environ.get("PORTAL_SMTP_USER", ""))
PASSWORD_FILE = os.environ.get("PORTAL_SMTP_PASSWORD_FILE", "")
PASSWORD = Path(PASSWORD_FILE).read_text().strip() if PASSWORD_FILE else os.environ.get("PORTAL_SMTP_PASSWORD", "")
CA = os.environ.get("PORTAL_SMTP_CA", "") or None
CONFIGURED = bool(HOST and SENDER and PASSWORD)
SUBJECT = "Практика ИБ — учебное приглашение"


def info():
    return {"configured": CONFIGURED, "sender": SENDER, "portal": ORIGIN}


def send_invitation(address, message_id):
    recipient = normalize_address(address)
    if not CONFIGURED or not recipient:
        return "rejected"
    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = recipient
    message["Subject"] = SUBJECT
    message["Date"] = formatdate()
    message["Message-ID"] = message_id
    message.set_content(
        "Вам назначено упражнение по информационной безопасности.\n\n"
        f"Откройте внутренний учебный портал: {ORIGIN}/\n"
        "Войдите с учётной записью самого учебного портала. "
        "Если вам нужны данные для входа, обратитесь к администратору портала.\n"
    )

    client = None
    submitting = False
    try:
        context = ssl.create_default_context(cafile=CA)
        client = smtplib.SMTP(HOST, PORT, timeout=6)
        client.starttls(context=context)
        client.login(SENDER, PASSWORD)
        submitting = True
        client.send_message(message, from_addr=SENDER, to_addrs=[recipient])
        return "accepted"
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPResponseException, smtplib.SMTPNotSupportedError):
        return "rejected"
    except (smtplib.SMTPException, OSError):
        return "unknown" if submitting else "rejected"
    finally:
        if client is not None:
            client.close()
