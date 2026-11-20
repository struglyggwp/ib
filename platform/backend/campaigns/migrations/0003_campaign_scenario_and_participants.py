from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0002_alter_safeevent_occurred_at_and_campaign_email_template"),
        ("scenarios", "0001_initial"),
        ("employees", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="campaign", name="scenario",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="campaigns", to="scenarios.scenario", verbose_name="Сценарий"),
        ),
        migrations.AddField(
            model_name="campaign", name="scenario_version",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Ревизия сценария"),
        ),
        migrations.CreateModel(
            name="CampaignParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="campaigns.campaign", verbose_name="Кампания")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="campaign_participations", to="employees.employee", verbose_name="Сотрудник")),
            ],
            options={"verbose_name": "участник кампании", "verbose_name_plural": "участники кампаний"},
        ),
        migrations.AddConstraint(
            model_name="campaignparticipant",
            constraint=models.UniqueConstraint(fields=("campaign", "employee"), name="unique_campaign_employee"),
        ),
    ]
