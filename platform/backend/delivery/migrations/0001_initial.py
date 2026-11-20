import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import delivery.models


def create_throttle(apps, schema_editor):
    apps.get_model("delivery", "DispatchThrottle").objects.using(schema_editor.connection.alias).get_or_create(id=1)


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("campaigns", "0004_training_links_and_participant_events"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="DispatchThrottle", fields=[
            ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
        ]),
        migrations.CreateModel(name="SimulationDomain", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("domain", models.CharField(max_length=253, unique=True, verbose_name="Разрешённый учебный домен")),
            ("verification_code", models.CharField(default=delivery.models.verification_code, editable=False, max_length=40)),
            ("verified_at", models.DateTimeField(blank=True, null=True)),
            ("sandbox_only", models.BooleanField(default=False)),
            ("active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["domain"], "verbose_name": "учебный домен", "verbose_name_plural": "учебные домены"}),
        migrations.CreateModel(name="CampaignDispatch", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("sender", models.EmailField(max_length=254)),
            ("landing_base_url", models.URLField(max_length=300)),
            ("state", models.CharField(choices=[("queued", "В очереди"), ("running", "Отправка выполняется"), ("finished", "Передача SMTP завершена"), ("stopped", "Остановлена")], default="queued", max_length=12)),
            ("template_subject", models.CharField(max_length=250)),
            ("template_text", models.TextField(blank=True)),
            ("template_html", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("started_at", models.DateTimeField(blank=True, null=True)),
            ("finished_at", models.DateTimeField(blank=True, null=True)),
            ("campaign", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="dispatch", to="campaigns.campaign")),
            ("domain", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="delivery.simulationdomain")),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"verbose_name": "учебная рассылка", "verbose_name_plural": "учебные рассылки", "permissions": [("start_dispatch", "Запускать учебные рассылки"), ("stop_dispatch", "Останавливать учебные рассылки")]}),
        migrations.CreateModel(name="DeliveryRecord", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(choices=[("pending", "Ожидает"), ("sending", "Передача SMTP начата"), ("accepted", "Принято SMTP"), ("failed", "Ошибка отправки"), ("blocked", "Заблокировано правилами")], default="pending", max_length=12)),
            ("recipient_email", models.EmailField(max_length=254)),
            ("attempted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ("smtp_accepted_at", models.DateTimeField(blank=True, null=True)),
            ("error_code", models.CharField(blank=True, max_length=100)),
            ("message_id", models.UUIDField(default=uuid.uuid4, editable=False)),
            ("dispatch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to="delivery.campaigndispatch")),
            ("participant", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_record", to="campaigns.campaignparticipant")),
        ], options={"ordering": ["participant_id"], "verbose_name": "передача учебного письма", "verbose_name_plural": "передачи учебных писем"}),
        migrations.CreateModel(name="DispatchAudit", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(max_length=24)),
            ("note", models.CharField(blank=True, max_length=250)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("dispatch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit", to="delivery.campaigndispatch")),
        ], options={"ordering": ["-created_at", "-id"], "verbose_name": "аудит рассылки", "verbose_name_plural": "аудит рассылок"}),
        migrations.AddConstraint(model_name="deliveryrecord", constraint=models.UniqueConstraint(fields=("dispatch", "participant"), name="unique_dispatch_participant")),
        migrations.AddIndex(model_name="deliveryrecord", index=models.Index(fields=["status", "attempted_at"], name="delivery_status_attempt_idx")),
        migrations.RunPython(create_throttle, migrations.RunPython.noop),
    ]
