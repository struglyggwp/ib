from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0001_initial"),
        ("email_templates", "0001_initial"),
    ]
    operations = [
        migrations.AlterField(
            model_name="campaign",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Создана"),
        ),
        migrations.AlterField(
            model_name="campaign",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="Изменена"),
        ),
        migrations.AlterField(
            model_name="safeevent",
            name="occurred_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Время"),
        ),
        migrations.AddField(
            model_name="campaign",
            name="email_template",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="campaigns", to="email_templates.emailtemplate", verbose_name="Шаблон письма"),
        ),
    ]
