import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("status", models.CharField(choices=[("draft","Черновик"),("approved","Согласована"),("running","Выполняется"),("completed","Завершена"),("cancelled","Отменена")], default="draft", max_length=20, verbose_name="Статус")),
                ("starts_at", models.DateTimeField(blank=True, null=True, verbose_name="Начало")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
            ],
            options={"verbose_name":"учебная кампания","verbose_name_plural":"учебные кампании","ordering":["-created_at"]},
        ),
        migrations.CreateModel(
            name="SafeEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("page_view","Просмотр учебной страницы"),("form_submitted","Отправка учебной формы")], max_length=32, verbose_name="Тип события")),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("source", models.CharField(default="unknown", max_length=32, verbose_name="Источник")),
                ("confidence", models.PositiveSmallIntegerField(default=50, verbose_name="Достоверность, %")),
                ("deduplication_key", models.CharField(blank=True, db_index=True, max_length=64)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="campaigns.campaign")),
            ],
            options={"verbose_name":"безопасное событие","verbose_name_plural":"безопасные события","ordering":["-occurred_at"]},
        ),
    ]
