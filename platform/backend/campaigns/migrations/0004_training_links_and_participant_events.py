import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0003_campaign_scenario_and_participants"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="TrainingLink",
            fields=[
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(verbose_name="Действует до")),
                ("revoked", models.BooleanField(default=False)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_training_links", to=settings.AUTH_USER_MODEL)),
                ("participant", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="training_link", to="campaigns.campaignparticipant", verbose_name="Участник")),
            ],
            options={"verbose_name": "учебная ссылка", "verbose_name_plural": "учебные ссылки"},
        ),
        migrations.CreateModel(
            name="ParticipantEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("link_visited", "Учебная ссылка открыта"), ("training_completed", "Упражнение завершено")], max_length=24)),
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Время на сервере")),
                ("dedupe_slot", models.BigIntegerField(verbose_name="Пятиминутный интервал")),
                ("participant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="training_events", to="campaigns.campaignparticipant")),
            ],
            options={"verbose_name": "событие участника", "verbose_name_plural": "события участников", "ordering": ["-occurred_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="participantevent",
            constraint=models.UniqueConstraint(fields=("participant", "kind", "dedupe_slot"), name="unique_participant_event_slot"),
        ),
        migrations.AddIndex(
            model_name="participantevent",
            index=models.Index(fields=["kind", "-occurred_at"], name="part_event_kind_time_idx"),
        ),
    ]
