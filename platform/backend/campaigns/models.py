import uuid
from django.conf import settings
from django.db import models

class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        APPROVED = "approved", "Согласована"
        RUNNING = "running", "Выполняется"
        COMPLETED = "completed", "Завершена"
        CANCELLED = "cancelled", "Отменена"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField("Начало", null=True, blank=True)
    email_template = models.ForeignKey("email_templates.EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns", verbose_name="Шаблон письма")
    scenario = models.ForeignKey("scenarios.Scenario", verbose_name="Сценарий", null=True, blank=True, on_delete=models.PROTECT, related_name="campaigns")
    scenario_version = models.PositiveIntegerField("Ревизия сценария", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Создал")
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Изменена", auto_now=True)
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "учебная кампания"
        verbose_name_plural = "учебные кампании"
    def __str__(self):
        return self.name

class SafeEvent(models.Model):
    class Kind(models.TextChoices):
        PAGE_VIEW = "page_view", "Просмотр учебной страницы"
        FORM_SUBMITTED = "form_submitted", "Отправка учебной формы"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField("Тип события", max_length=32, choices=Kind.choices)
    occurred_at = models.DateTimeField("Время", auto_now_add=True)
    source = models.CharField("Источник", max_length=32, default="unknown")
    confidence = models.PositiveSmallIntegerField("Достоверность, %", default=50)
    deduplication_key = models.CharField(max_length=64, blank=True, db_index=True)
    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "безопасное событие"
        verbose_name_plural = "безопасные события"


class CampaignParticipant(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="participants", verbose_name="Кампания")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="campaign_participations", verbose_name="Сотрудник")
    added_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "участник кампании"
        verbose_name_plural = "участники кампаний"
        constraints = [models.UniqueConstraint(fields=["campaign", "employee"], name="unique_campaign_employee")]

    def __str__(self):
        return f"{self.campaign}: {self.employee}"


class TrainingLink(models.Model):
    """One opaque, revocable link per campaign participant; not proof of physical identity."""
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.OneToOneField(CampaignParticipant, on_delete=models.CASCADE, related_name="training_link", verbose_name="Участник")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_training_links")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("Действует до")
    revoked = models.BooleanField(default=False)

    class Meta:
        verbose_name = "учебная ссылка"
        verbose_name_plural = "учебные ссылки"


class ParticipantEvent(models.Model):
    class Kind(models.TextChoices):
        LINK_VISITED = "link_visited", "Учебная ссылка открыта"
        EMAIL_OPEN_SIGNAL = "email_open_signal", "Загрузка изображения из письма"
        TRAINING_COMPLETED = "training_completed", "Упражнение завершено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(CampaignParticipant, on_delete=models.CASCADE, related_name="training_events")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    occurred_at = models.DateTimeField("Время на сервере", auto_now_add=True, db_index=True)
    dedupe_slot = models.BigIntegerField("Пятиминутный интервал")
    # No credentials, raw form input, IP addresses or user-agent identifiers are stored.

    class Meta:
        ordering = ["-occurred_at", "-id"]
        verbose_name = "событие участника"
        verbose_name_plural = "события участников"
        constraints = [models.UniqueConstraint(fields=["participant", "kind", "dedupe_slot"], name="unique_participant_event_slot")]
        indexes = [models.Index(fields=["kind", "-occurred_at"], name="part_event_kind_time_idx")]
