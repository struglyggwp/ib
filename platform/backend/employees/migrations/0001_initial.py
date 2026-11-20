from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="Department", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=160, unique=True, verbose_name="Название подразделения")),
            ("description", models.TextField(blank=True, verbose_name="Описание")),
            ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
            ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
        ], options={"verbose_name": "подразделение", "verbose_name_plural": "подразделения", "ordering": ["name"]}),
        migrations.CreateModel(name="Position", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=160, unique=True, verbose_name="Должность")),
            ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
        ], options={"verbose_name": "должность", "verbose_name_plural": "должности", "ordering": ["name"]}),
        migrations.CreateModel(name="Employee", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("first_name", models.CharField(max_length=100, verbose_name="Имя")),
            ("last_name", models.CharField(max_length=100, verbose_name="Фамилия")),
            ("middle_name", models.CharField(blank=True, max_length=100, verbose_name="Отчество")),
            ("email", models.EmailField(max_length=254, unique=True, verbose_name="Корпоративная почта")),
            ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
            ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")),
            ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменён")),
            ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="employees.department", verbose_name="Подразделение")),
            ("position", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="employees", to="employees.position", verbose_name="Должность")),
        ], options={"verbose_name": "сотрудник", "verbose_name_plural": "сотрудники", "ordering": ["last_name", "first_name", "email"]}),
        migrations.AddIndex(model_name="employee", index=models.Index(fields=["last_name", "first_name"], name="employees_e_last_na_6bdf16_idx")),
        migrations.AddIndex(model_name="employee", index=models.Index(fields=["is_active"], name="employees_e_is_acti_5c7a2f_idx")),
    ]
