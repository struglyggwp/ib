from django.db import models


class Department(models.Model):
    name = models.CharField("Название подразделения", max_length=160, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "подразделение"
        verbose_name_plural = "подразделения"

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField("Должность", max_length=160, unique=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "должность"
        verbose_name_plural = "должности"

    def __str__(self):
        return self.name


class Employee(models.Model):
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100)
    middle_name = models.CharField("Отчество", max_length=100, blank=True)
    email = models.EmailField("Корпоративная почта", unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees", verbose_name="Подразделение", null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="employees", verbose_name="Должность", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "email"]
        verbose_name = "сотрудник"
        verbose_name_plural = "сотрудники"
        indexes = [models.Index(fields=["last_name", "first_name"], name="employees_e_last_na_6bdf16_idx"), models.Index(fields=["is_active"], name="employees_e_is_acti_5c7a2f_idx")]

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.email})"
