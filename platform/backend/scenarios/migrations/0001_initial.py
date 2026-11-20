import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("email_templates", "0001_initial"),
        ("employees", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="Scenario",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("category", models.CharField(choices=[("phishing", "Распознавание фишинга"), ("social", "Социальная инженерия"), ("policy", "Политики ИБ"), ("general", "Общая осведомлённость")], default="phishing", max_length=24, verbose_name="Категория")),
                ("difficulty", models.CharField(choices=[("basic", "Начальный"), ("medium", "Средний"), ("advanced", "Продвинутый")], default="basic", max_length=12, verbose_name="Сложность")),
                ("status", models.CharField(choices=[("draft", "Черновик"), ("ready", "Готов"), ("archived", "Архив")], default="draft", max_length=16, verbose_name="Статус")),
                ("version", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name="Ревизия")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_scenarios", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("email_template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="scenarios", to="email_templates.emailtemplate", verbose_name="Шаблон письма")),
                ("departments", models.ManyToManyField(blank=True, related_name="scenarios", to="employees.department", verbose_name="Подразделения")),
                ("employees", models.ManyToManyField(blank=True, related_name="scenarios", to="employees.employee", verbose_name="Отдельные сотрудники")),
            ],
            options={"verbose_name": "учебный сценарий", "verbose_name_plural": "учебные сценарии", "ordering": ["-updated_at", "name"]},
        ),
        migrations.CreateModel(
            name="ScenarioStep",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("position", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name="Порядок")),
                ("kind", models.CharField(choices=[("prepare", "Подготовка"), ("preview", "Предварительный просмотр"), ("simulate", "Учебная симуляция"), ("teach", "Обратная связь и обучение"), ("review", "Подведение итогов")], max_length=16, verbose_name="Тип шага")),
                ("title", models.CharField(max_length=160, verbose_name="Название шага")),
                ("instructions", models.TextField(blank=True, verbose_name="Инструкция для оператора")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="scenarios.scenario", verbose_name="Сценарий")),
            ],
            options={"verbose_name": "этап сценария", "verbose_name_plural": "этапы сценария", "ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="ScenarioRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scenario_version", models.PositiveIntegerField(verbose_name="Ревизия сценария")),
                ("outcome", models.CharField(choices=[("passed", "Проверка пройдена"), ("blocked", "Есть замечания")], max_length=12, verbose_name="Результат")),
                ("audience_count", models.PositiveIntegerField(default=0, verbose_name="Количество адресатов")),
                ("checks", models.JSONField(default=dict, verbose_name="Результаты проверок")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Проверен")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scenario_dry_runs", to=settings.AUTH_USER_MODEL)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dry_runs", to="scenarios.scenario", verbose_name="Сценарий")),
            ],
            options={"verbose_name": "проверочный прогон", "verbose_name_plural": "проверочные прогоны", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ScenarioActivity",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("created", "Создан"), ("edited", "Изменён"), ("step_changed", "Изменены этапы"), ("ready", "Подготовлен"), ("archived", "Архивирован"), ("restored", "Восстановлен"), ("dry_run", "Проверочный прогон"), ("campaign_created", "Создана кампания")], max_length=20)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="activity", to="scenarios.scenario")),
            ],
            options={"verbose_name": "действие со сценарием", "verbose_name_plural": "история сценариев", "ordering": ["-at", "-id"]},
        ),
        migrations.AddIndex(model_name="scenario", index=models.Index(fields=["status", "category"], name="scenario_status_cat_idx")),
        migrations.AddConstraint(model_name="scenariostep", constraint=models.UniqueConstraint(fields=("scenario", "position"), name="unique_scenario_step_position")),
        migrations.AddIndex(model_name="scenarioactivity", index=models.Index(fields=["scenario", "-at"], name="scenario_activity_idx")),
    ]
