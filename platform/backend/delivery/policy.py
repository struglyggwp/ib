"""Outbound policy: denies by default; never uses a caller-supplied recipient address."""
import os
from urllib.parse import urlparse

from django.core.exceptions import ValidationError


def allowed_recipient_domains():
    return {x.strip().lower().lstrip("@") for x in os.environ.get("SMTP_ALLOWED_RECIPIENT_DOMAINS", "").split(",") if x.strip()}


def campaign_enabled():
    return os.environ.get("SMTP_CAMPAIGN_ENABLED", "0") == "1"


def sandbox_mode():
    return os.environ.get("SMTP_HOST", "").lower().strip() == "mailpit"


def validate_destination(email):
    domain = email.rsplit("@", 1)[-1].strip().lower()
    allowed = allowed_recipient_domains()
    return bool(allowed and domain in allowed and email.count("@") == 1 and not any(c.isspace() for c in email))


def internally_authorized_sender(domain_name, sender):
    """SMTP login must be identical to the configured From address.

    DNS ownership probes are neither required nor performed. This does NOT
    authorize unauthenticated impersonation of an arbitrary third-party address.
    """
    username = os.environ.get("SMTP_USERNAME", "").strip().lower()
    return bool(not sandbox_mode() and username and sender.lower() in approved_addresses()
                and sender.lower().endswith("@" + domain_name.lower()))


def sender_domain_authorized(domain, sender=None):
    sender = sender or os.environ.get("SMTP_FROM_EMAIL", "").strip().lower()
    if not domain.active or sender.count("@") != 1:
        return False
    if sandbox_mode():
        return domain.domain.endswith(".test") and sender.endswith("@" + domain.domain.lower())
    return internally_authorized_sender(domain.domain, sender)


def validate_sender(domain, sender=None):
    sender = sender or os.environ.get("SMTP_FROM_EMAIL", "").strip().lower()
    if not sender or sender.count("@") != 1 or sender.rsplit("@", 1)[-1] != domain.domain.lower():
        raise ValidationError("SMTP_FROM_EMAIL должен совпадать с доменом отправителя.")
    if not sender_domain_authorized(domain, sender):
        raise ValidationError("Для Zimbra укажите SMTP_USERNAME равным SMTP_FROM_EMAIL; для Mailpit используйте адрес в зоне .test.")
    if domain.sandbox_only and not sandbox_mode():
        raise ValidationError("Тестовый домен Mailpit не используется через Zimbra.")
    return sender


def landing_url(domain):
    if sandbox_mode() and domain.domain.endswith(".test"):
        base = os.environ.get("SIMULATION_LOCAL_BASE_URL", "http://127.0.0.1:8080").strip().rstrip("/")
        parsed = urlparse(base)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValidationError("SIMULATION_LOCAL_BASE_URL допускает только адрес localhost/127.0.0.1.")
        return base
    base = os.environ.get("SIMULATION_PUBLIC_BASE_URL", "").strip().rstrip("/")
    parsed = urlparse(base)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("Некорректный порт учебной ссылки.") from exc
    allowed_hosts = {host.strip().lower() for host in os.environ.get("SIMULATION_ALLOWED_LINK_HOSTS", "").split(",") if host.strip()}
    # Explicitly configured recipient-facing HTTPS URL. Sender identity and landing host are independent.
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        raise ValidationError("Для SMTP требуется HTTPS-ссылка на порту 443 (SIMULATION_PUBLIC_BASE_URL).")
    if not parsed.hostname or parsed.hostname.lower() not in allowed_hosts or parsed.path or parsed.query or parsed.fragment:
        raise ValidationError("Укажите хост ссылки в SIMULATION_ALLOWED_LINK_HOSTS и настройте внутренний DNS.")
    return base


def limits():
    try:
        max_campaign = min(250, max(1, int(os.environ.get("SMTP_MAX_PER_CAMPAIGN", "100"))))
        per_minute = min(10, max(1, int(os.environ.get("SMTP_MAX_PER_MINUTE", "10"))))
    except ValueError as exc:
        raise ValidationError("Некорректные ограничения отправки в .env") from exc
    return max_campaign, per_minute


def template_sender(template):
    if template and template.sender_id:
        return str(template.sender).lower()
    return os.environ.get("SMTP_FROM_EMAIL", "").strip().lower()


def approved_addresses():
    values = os.environ.get("SMTP_APPROVED_ALIASES", "").split(",")
    values.append(os.environ.get("SMTP_USERNAME", ""))
    return {v.strip().lower() for v in values if v.strip()}
