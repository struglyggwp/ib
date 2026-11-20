from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Department, Employee, Position


class EmployeeCatalogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-password-123")
        self.client.force_login(self.user)

    def test_employee_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("employee_list"))
        self.assertEqual(response.status_code, 302)

    def test_create_employee(self):
        response = self.client.post(reverse("employee_create"), {
            "first_name": "Иван", "last_name": "Иванов", "middle_name": "Иванович",
            "email": "ivanov@example.test", "department": "", "position": "", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(email="ivanov@example.test").exists())

    def test_employee_email_is_unique(self):
        Employee.objects.create(first_name="Иван", last_name="Иванов", email="same@example.test")
        response = self.client.post(reverse("employee_create"), {
            "first_name": "Пётр", "last_name": "Петров", "email": "same@example.test",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Employee.objects.filter(email="same@example.test").count(), 1)

    def test_search_by_email(self):
        Employee.objects.create(first_name="Иван", last_name="Иванов", email="ivanov@example.test")
        response = self.client.get(reverse("employee_list"), {"q": "ivanov@"})
        self.assertContains(response, "ivanov@example.test")

    def test_department_and_position_relationships(self):
        department = Department.objects.create(name="ИТ")
        position = Position.objects.create(name="Инженер")
        employee = Employee.objects.create(first_name="Анна", last_name="Смирнова", email="anna@example.test", department=department, position=position)
        self.assertEqual(employee.department.name, "ИТ")
        self.assertEqual(employee.position.name, "Инженер")
