from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0005_import_unused_scenarios")]

    operations = [
        migrations.AlterField(
            model_name="participantevent",
            name="kind",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("link_visited", "Учебная ссылка открыта"),
                    ("email_open_signal", "Загрузка изображения из письма"),
                    ("training_completed", "Упражнение завершено"),
                ],
            ),
        ),
    ]
