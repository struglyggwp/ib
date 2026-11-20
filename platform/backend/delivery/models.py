import secrets
import uuid

from django.conf import settings
from django.db import models


def verification_code():
    return secrets.token_hex(20)


class SimulationDomain(models.Model):
    """Verified organization-owned sender + training landing domain."""
    domain = models.CharField("Разрешённый учебный домен", max_length=253, unique=True)
    verification_code = models.CharField(max_length=40, default=verification_code, editable=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    sandbox_only = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]
        verbose_name = "учебный домен"
        verbose_name_plural = "учебные домены"

    def __str__(self):
        return self.domain


class CampaignDispatch(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "В очереди"
        RUNNING = "running", "Отправка выполняется"
        FINISHED = "finished", "Передача SMTP завершена"
        STOPPED = "stopped", "Остановлена"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField("campaigns.Campaign", on_delete=models.PROTECT, related_name="dispatch")
    domain = models.ForeignKey(SimulationDomain, on_delete=models.PROTECT)
    sender = models.EmailField(max_length=254)
    landing_base_url = models.URLField(max_length=300)
    state = models.CharField(max_length=12, choices=State.choices, default=State.QUEUED)
    material = models.ForeignKey("email_templates.EmailTemplate", null=True, on_delete=models.PROTECT)
    template_subject = models.CharField(max_length=250)
    template_text = models.TextField(blank=True)
    template_html = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "учебная рассылка"
        verbose_name_plural = "учебные рассылки"
        permissions = [("start_dispatch", "Запускать учебные рассылки"), ("stop_dispatch", "Останавливать учебные рассылки")]


class DeliveryRecord(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENDING = "sending", "Передача SMTP начата"
        ACCEPTED = "accepted", "Принято SMTP"
        FAILED = "failed", "Ошибка отправки"
        BLOCKED = "blocked", "Заблокировано правилами"

    dispatch = models.ForeignKey(CampaignDispatch, on_delete=models.PROTECT, related_name="records")
    participant = models.OneToOneField("campaigns.CampaignParticipant", on_delete=models.PROTECT, related_name="delivery_record")
    status = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    recipient_email = models.EmailField(max_length=254)
    attempted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    smtp_accepted_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    message_id = models.UUIDField(default=uuid.uuid4, editable=False)
    open_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["participant_id"]
        verbose_name = "передача учебного письма"
        verbose_name_plural = "передачи учебных писем"
        constraints = [models.UniqueConstraint(fields=["dispatch", "participant"], name="unique_dispatch_participant")]
        indexes = [models.Index(fields=["status", "attempted_at"], name="delivery_status_attempt_idx")]


class DispatchAudit(models.Model):
    dispatch = models.ForeignKey(CampaignDispatch, on_delete=models.PROTECT, related_name="audit")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=24)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "аудит рассылки"
        verbose_name_plural = "аудит рассылок"


class DispatchThrottle(models.Model):
    """Singleton row locked before reservations, for global cross-worker rate limit."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
