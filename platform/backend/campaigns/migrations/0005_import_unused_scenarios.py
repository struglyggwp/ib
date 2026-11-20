from django.db import migrations


def import_unused_scenarios(apps, schema_editor):
    Scenario = apps.get_model("scenarios", "Scenario")
    Campaign = apps.get_model("campaigns", "Campaign")
    Participant = apps.get_model("campaigns", "CampaignParticipant")
    Employee = apps.get_model("employees", "Employee")
    for scenario in Scenario.objects.all().iterator():
        # A scenario with a linked campaign is already represented in the new workflow.
        if Campaign.objects.filter(scenario_id=scenario.pk).exists():
            continue
        campaign = Campaign.objects.create(
            name=scenario.name, description=scenario.description,
            status="draft", email_template_id=scenario.email_template_id,
            scenario_id=scenario.pk, scenario_version=scenario.version,
            created_by_id=scenario.created_by_id,
        )
        ids = set(scenario.employees.filter(is_active=True).values_list("pk", flat=True))
        department_ids = list(scenario.departments.values_list("pk", flat=True))
        if department_ids:
            ids.update(Employee.objects.filter(is_active=True, department_id__in=department_ids).values_list("pk", flat=True))
        Participant.objects.bulk_create([
            Participant(campaign_id=campaign.pk, employee_id=pk) for pk in ids
        ], batch_size=500, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0004_training_links_and_participant_events"), ("scenarios", "0001_initial")]
    operations = [migrations.RunPython(import_unused_scenarios, migrations.RunPython.noop)]
