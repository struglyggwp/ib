import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Scenario(models.Model):
    class Category(models.TextChoices):
        PHISHING = "phishing", "Распознавание фишинга"
        SOCIAL = "social", "Социальная инженерия"
        POLICY = "policy", "Политики ИБ"
        GENERAL = "general", "Общая осведомлённость"

    class Difficulty(models.TextChoices):
        BASIC = "basic", "Начальный"
        MEDIUM = "medium", "Средний"
        ADVANCED = "advanced", "Продвинутый"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        READY = "ready", "Готов"
        ARCHIVED = "archived", "Архив"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)
    category = models.CharField("Категория", max_length=24, choices=Category.choices, default=Category.PHISHING)
    difficulty = models.CharField("Сложность", max_length=12, choices=Difficulty.choices, default=Difficulty.BASIC)
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.DRAFT)
    email_template = models.ForeignKey("email_templates.EmailTemplate", verbose_name="Шаблон письма", null=True, blank=True, on_delete=models.PROTECT, related_name="scenarios")
    departments = models.ManyToManyField("employees.Department", blank=True, related_name="scenarios", verbose_name="Подразделения")
    employees = models.ManyToManyField("employees.Employee", blank=True, related_name="scenarios", verbose_name="Отдельные сотрудники")
    version = models.PositiveIntegerField("Ревизия", default=1, validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Создал", on_delete=models.PROTECT, related_name="created_scenarios")
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]
        verbose_name = "учебный сценарий"
        verbose_name_plural = "учебные сценарии"
        indexes = [models.Index(fields=["status", "category"], name="scenario_status_cat_idx")]

    def __str__(self):
        return self.name


class ScenarioStep(models.Model):
    class Kind(models.TextChoices):
        PREPARE = "prepare", "Подготовка"
        PREVIEW = "preview", "Предварительный просмотр"
        SIMULATE = "simulate", "Учебная симуляция"
        TEACH = "teach", "Обратная связь и обучение"
        REVIEW = "review", "Подведение итогов"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="steps", verbose_name="Сценарий")
    position = models.PositiveIntegerField("Порядок", validators=[MinValueValidator(1)])
    kind = models.CharField("Тип шага", max_length=16, choices=Kind.choices)
    title = models.CharField("Название шага", max_length=160)
    instructions = models.TextField("Инструкция для оператора", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "этап сценария"
        verbose_name_plural = "этапы сценария"
        constraints = [models.UniqueConstraint(fields=["scenario", "position"], name="unique_scenario_step_position")]

    def __str__(self):
        return f"{self.position}. {self.title}"


class ScenarioRun(models.Model):
    class Outcome(models.TextChoices):
        PASSED = "passed", "Проверка пройдена"
        BLOCKED = "blocked", "Есть замечания"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="dry_runs", verbose_name="Сценарий")
    scenario_version = models.PositiveIntegerField("Ревизия сценария")
    outcome = models.CharField("Результат", max_length=12, choices=Outcome.choices)
    audience_count = models.PositiveIntegerField("Количество адресатов", default=0)
    checks = models.JSONField("Результаты проверок", default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="scenario_dry_runs")
    created_at = models.DateTimeField("Проверен", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "проверочный прогон"
        verbose_name_plural = "проверочные прогоны"


class ScenarioActivity(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Создан"
        EDITED = "edited", "Изменён"
        STEP_CHANGED = "step_changed", "Изменены этапы"
        READY = "ready", "Подготовлен"
        ARCHIVED = "archived", "Архивирован"
        RESTORED = "restored", "Восстановлен"
        DRY_RUN = "dry_run", "Проверочный прогон"
        CAMPAIGN_CREATED = "campaign_created", "Создана кампания"

    id = models.BigAutoField(primary_key=True)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="activity")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=Action.choices)
    description = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name = "действие со сценарием"
        verbose_name_plural = "история сценариев"
        indexes = [models.Index(fields=["scenario", "-at"], name="scenario_activity_idx")]
