"""Single campaign workflow: create, pick employees, click Start, see the report."""
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignParticipant
from delivery.models import CampaignDispatch, SimulationDomain
from email_templates.models import EmailTemplate
from employees.models import Department, Employee

TEST_ENV = {
    "SMTP_HOST": "mailpit", "SMTP_PORT": "1025", "SMTP_USE_STARTTLS": "0", "SMTP_USE_SSL": "0",
    "SMTP_FROM_EMAIL": "training@training.test", "SMTP_CAMPAIGN_ENABLED": "1",
    "SMTP_ALLOWED_RECIPIENT_DOMAINS": "training.test", "SMTP_MAX_PER_CAMPAIGN": "100", "SMTP_MAX_PER_MINUTE": "10",
    "SIMULATION_LOCAL_BASE_URL": "http://127.0.0.1:8080",
}


class OneClickCampaignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("one-click", "one@click.test", "RandomPassword!12345")
        cls.department = Department.objects.create(name="Тестовое подразделение")
        cls.first = Employee.objects.create(first_name="Вера", last_name="Одна", email="vera@training.test", department=cls.department)
        cls.second = Employee.objects.create(first_name="Иван", last_name="Два", email="ivan@training.test", department=cls.department)
        cls.template = EmailTemplate.objects.create(name="Учебное письмо", subject="Проверка", text_body="Учебное письмо.", status="active", created_by=cls.user)

    def test_create_campaign_snapshots_selected_department(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("campaign_create"), {
            "name": "Новая кампания", "description": "", "email_template": str(self.template.pk),
            "departments": [self.department.pk], "employees": [self.first.pk],
        })
        self.assertEqual(response.status_code, 302)
        campaign = Campaign.objects.get(name="Новая кампания")
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)
        self.assertEqual(campaign.participants.count(), 2)

    @patch.dict("os.environ", TEST_ENV)
    def test_one_click_creates_dispatch_and_only_one_dispatch(self):
        self.client.force_login(self.user)
        campaign = Campaign.objects.create(name="Отправка", email_template=self.template, created_by=self.user)
        CampaignParticipant.objects.create(campaign=campaign, employee=self.first)
        url = reverse("campaign_start", args=[campaign.pk])
        with self.captureOnCommitCallbacks(execute=False):
            result = self.client.post(url)
        self.assertEqual(result.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.RUNNING)
        self.assertEqual(CampaignDispatch.objects.filter(campaign=campaign).count(), 1)
        self.assertTrue(SimulationDomain.objects.filter(domain="training.test").exists())
        self.assertEqual(campaign.dispatch.records.count(), 1)
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(url)
        self.assertEqual(CampaignDispatch.objects.filter(campaign=campaign).count(), 1)

    @patch.dict("os.environ", TEST_ENV)
    def test_missing_template_leaves_campaign_as_draft(self):
        self.client.force_login(self.user)
        campaign = Campaign.objects.create(name="Черновик", created_by=self.user)
        CampaignParticipant.objects.create(campaign=campaign, employee=self.first)
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(reverse("campaign_start", args=[campaign.pk]))
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)
        self.assertFalse(CampaignDispatch.objects.filter(campaign=campaign).exists())

    def test_no_scenarios_in_nav_or_dashboard(self):
        self.client.force_login(self.user)
        homepage = self.client.get(reverse("dashboard"))
        self.assertEqual(homepage.status_code, 200)
        self.assertNotContains(homepage, 'href="/scenarios/"')
        self.assertRedirects(self.client.get("/scenarios/"), reverse("campaign_list"))

    @patch.dict("os.environ", TEST_ENV)
    def test_non_admin_cannot_start_send(self):
        ordinary = get_user_model().objects.create_user("no-start", password="OtherPassword!123")
        campaign = Campaign.objects.create(name="Без полномочий", email_template=self.template, created_by=self.user)
        CampaignParticipant.objects.create(campaign=campaign, employee=self.first)
        self.client.force_login(ordinary)
        self.assertEqual(self.client.post(reverse("campaign_start", args=[campaign.pk])).status_code, 403)
        self.assertFalse(CampaignDispatch.objects.filter(campaign=campaign).exists())
