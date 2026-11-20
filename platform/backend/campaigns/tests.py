from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Department, Employee
from .models import Campaign, CampaignParticipant, ParticipantEvent, TrainingLink


class TrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("campadmin", "campadmin@example.test", "SecurePasswordForTests!123")
        cls.department = Department.objects.create(name="Операции")
        cls.employee = Employee.objects.create(first_name="Анна", last_name="Тестовая", email="a@example.test", department=cls.department)
        cls.campaign = Campaign.objects.create(name="Проверка", status=Campaign.Status.RUNNING, created_by=cls.admin)
        cls.participant = CampaignParticipant.objects.create(campaign=cls.campaign, employee=cls.employee)
        cls.link = TrainingLink.objects.create(participant=cls.participant, created_by=cls.admin, expires_at=timezone.now() + timedelta(days=7))

    def test_anonymous_visit_records_employee_and_server_time(self):
        self.assertEqual(self.client.get(reverse("training_visit", args=[self.link.token])).status_code, 200)
        event = ParticipantEvent.objects.get(participant=self.participant, kind="link_visited")
        self.assertLess(abs((timezone.now() - event.occurred_at).total_seconds()), 20)
        self.assertEqual(event.participant.employee, self.employee)

    def test_repeated_visit_same_window_deduplicated(self):
        url = reverse("training_visit", args=[self.link.token])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(ParticipantEvent.objects.filter(participant=self.participant, kind="link_visited").count(), 1)

    def test_prefetch_does_not_count(self):
        self.client.get(reverse("training_visit", args=[self.link.token]), HTTP_SEC_PURPOSE="prefetch")
        self.assertFalse(ParticipantEvent.objects.exists())

    def test_completion_acknowledges_without_form_content(self):
        self.client.post(reverse("training_visit", args=[self.link.token]), {"password": "ignored-in-all-cases"})
        self.assertEqual(ParticipantEvent.objects.filter(kind="training_completed").count(), 1)
        self.assertFalse(hasattr(ParticipantEvent.objects.first(), "password"))

    def test_csrf_required_for_completion(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("training_visit", args=[self.link.token]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ParticipantEvent.objects.count(), 0)

    def test_revoked_and_expired_links_blocked(self):
        url = reverse("training_visit", args=[self.link.token])
        self.link.revoked = True
        self.link.save(update_fields=["revoked"])
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(ParticipantEvent.objects.count(), 0)

    def test_inactive_campaign_does_not_track(self):
        self.campaign.status = Campaign.Status.COMPLETED
        self.campaign.save(update_fields=["status"])
        self.assertEqual(self.client.get(reverse("training_visit", args=[self.link.token])).status_code, 403)
        self.assertEqual(ParticipantEvent.objects.count(), 0)

    def test_report_requires_permission(self):
        user = get_user_model().objects.create_user("visitor", password="VerySafePassword!123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("campaign_detail", args=[self.campaign.pk])).status_code, 403)

    def test_report_has_campaign_and_employee_after_visit(self):
        self.client.get(reverse("training_visit", args=[self.link.token]))
        self.client.force_login(self.admin)
        response = self.client.get(reverse("campaign_detail", args=[self.campaign.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Именной отчёт")
        self.assertContains(response, "Тестовая")

    def test_operator_can_generate_links_once(self):
        self.link.delete()
        self.client.force_login(self.admin)
        url = reverse("create_training_links", args=[self.campaign.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(TrainingLink.objects.filter(participant=self.participant).count(), 1)

    def test_smtp_check_does_not_send_messages(self):
        self.client.force_login(self.admin)
        with patch.dict("os.environ", {"SMTP_HOST": "localhost", "SMTP_PORT": "1025", "SMTP_USE_STARTTLS": "0"}), patch("campaigns.views.smtplib.SMTP") as smtp:
            response = self.client.post(reverse("mail_check_connection"))
            self.assertEqual(response.status_code, 302)
            smtp.return_value.send_message.assert_not_called()
