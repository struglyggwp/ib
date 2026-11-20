from django.conf import settings
from django.db import models


class EmailTemplate(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "Общие"
        SECURITY = "security", "Информационная безопасность"
        AWARENESS = "awareness", "Обучение и осведомлённость"
        POLICY = "policy", "Политики и регламенты"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Активный"
        ARCHIVED = "archived", "Архивный"

    name = models.CharField("Название", max_length=160)
    category = models.CharField("Категория", max_length=24, choices=Category.choices, default=Category.GENERAL)
    tags = models.CharField("Теги", max_length=500, blank=True, help_text="Через запятую")
    subject = models.CharField("Тема письма", max_length=250)
    html_body = models.TextField("HTML-версия", blank=True)
    landing_html = models.TextField("HTML учебной страницы", blank=True)
    sender = models.ForeignKey("SenderAddress", verbose_name="Корпоративный отправитель", blank=True, null=True, on_delete=models.PROTECT)
    text_body = models.TextField("Текстовая версия", blank=True)
    description = models.TextField("Внутреннее описание", blank=True)
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Создал", related_name="email_templates")
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]
        verbose_name = "шаблон письма"
        verbose_name_plural = "шаблоны писем"
        indexes = [
            models.Index(fields=["status", "category"], name="email_tpl_status_cat_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


class SenderDomain(models.Model):
    name = models.CharField("Домен отправителя", max_length=253, unique=True)

    def clean(self):
        from django.core.validators import validate_email
        self.name = self.name.strip().lower()
        validate_email("training@" + self.name)

    def __str__(self):
        return self.name


class SenderAddress(models.Model):
    local = models.CharField("Часть адреса до @", max_length=64)
    domain = models.ForeignKey(SenderDomain, on_delete=models.PROTECT, verbose_name="Домен")

    class Meta:
        unique_together = ("local", "domain")
        verbose_name = "адрес отправителя"
        verbose_name_plural = "адреса отправителя"

    def clean(self):
        from django.core.validators import validate_email
        if self.domain_id:
            validate_email(str(self))

    def __str__(self):
        return f"{self.local}@{self.domain}"
