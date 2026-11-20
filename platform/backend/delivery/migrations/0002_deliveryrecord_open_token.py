"""Roll out unique tracking tokens safely for existing DeliveryRecord rows."""
import uuid
from django.db import migrations, models


def populate_open_tokens(apps, schema_editor):
    records = apps.get_model("delivery", "DeliveryRecord")
    alias = schema_editor.connection.alias
    for pk in records.objects.using(alias).filter(open_token__isnull=True).values_list("pk", flat=True).iterator(chunk_size=1000):
        records.objects.using(alias).filter(pk=pk).update(open_token=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0001_initial"),
        ("campaigns", "0006_participantevent_email_open_signal"),
    ]
    operations = [
        migrations.AddField(
            model_name="deliveryrecord",
            name="open_token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_open_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="deliveryrecord",
            name="open_token",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
