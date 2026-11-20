from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="EmailTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="Название")),
                ("category", models.CharField(choices=[("general", "Общие"), ("security", "Информационная безопасность"), ("awareness", "Обучение и осведомлённость"), ("policy", "Политики и регламенты"), ("other", "Другое")], default="general", max_length=24, verbose_name="Категория")),
                ("tags", models.CharField(blank=True, help_text="Через запятую", max_length=500, verbose_name="Теги")),
                ("subject", models.CharField(max_length=250, verbose_name="Тема письма")),
                ("html_body", models.TextField(blank=True, verbose_name="HTML-версия")),
                ("text_body", models.TextField(blank=True, verbose_name="Текстовая версия")),
                ("description", models.TextField(blank=True, verbose_name="Внутреннее описание")),
                ("status", models.CharField(choices=[("draft", "Черновик"), ("active", "Активный"), ("archived", "Архивный")], default="draft", max_length=16, verbose_name="Статус")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="email_templates", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменён")),
            ],
            options={"verbose_name": "шаблон письма", "verbose_name_plural": "шаблоны писем", "ordering": ["-updated_at", "name"]},
        ),
        migrations.AddIndex(
            model_name="emailtemplate",
            index=models.Index(fields=["status", "category"], name="email_tpl_status_cat_idx"),
        ),
    ]
