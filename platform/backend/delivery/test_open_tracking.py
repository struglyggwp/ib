"""Regression checks for v0.18 email-image load signals (not confirmed reading)."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from campaigns.models import Campaign, CampaignParticipant, ParticipantEvent, TrainingLink
from email_templates.models import EmailTemplate
from employees.models import Employee
from delivery.models import CampaignDispatch, DeliveryRecord, SimulationDomain
from delivery.rendering import render_email
from delivery.tasks import send_one


class OpenTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            "openadmin", "admin@training.test", "SecurePasswordForTests!123"
        )
        cls.employee = Employee.objects.create(
            first_name="Иван", last_name="Петров", email="ivan@training.test"
        )
        cls.template = EmailTemplate.objects.create(
            name="Тестовое HTML письмо", subject="Тест", text_body="Учебная проверка",
            html_body="<p>Учебная проверка</p>", status="active", created_by=cls.admin,
        )
        cls.campaign = Campaign.objects.create(
            name="Открытие письма", email_template=cls.template,
            status=Campaign.Status.RUNNING, created_by=cls.admin,
        )
        cls.participant = CampaignParticipant.objects.create(
            campaign=cls.campaign, employee=cls.employee
        )
        cls.domain = SimulationDomain.objects.create(
            domain="training.test", created_by=cls.admin,
            verified_at=timezone.now(), sandbox_only=True,
        )
        cls.dispatch = CampaignDispatch.objects.create(
            campaign=cls.campaign, domain=cls.domain, sender="training@training.test",
            landing_base_url="http://127.0.0.1:8080",
            template_subject=cls.template.subject, template_text=cls.template.text_body,
            template_html=cls.template.html_body, created_by=cls.admin,
        )
        cls.delivery = DeliveryRecord.objects.create(
            dispatch=cls.dispatch, participant=cls.participant,
            recipient_email=cls.employee.email, status=DeliveryRecord.State.ACCEPTED,
            smtp_accepted_at=timezone.now(),
        )
        cls.link = TrainingLink.objects.create(
            participant=cls.participant, created_by=cls.admin,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def pixel_url(self):
        return reverse("email_open_pixel", args=[self.delivery.open_token])

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_get_returns_gif_and_records_server_timestamp(self):
        res = self.client.get(self.pixel_url())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/gif")
        self.assertTrue(res.content.startswith(b"GIF89a"))
        self.assertIn("no-store", res["Cache-Control"])
        event = ParticipantEvent.objects.get(kind=ParticipantEvent.Kind.EMAIL_OPEN_SIGNAL)
        self.assertEqual(event.participant, self.participant)
        self.assertLess(abs((timezone.now() - event.occurred_at).total_seconds()), 30)

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_repeat_get_in_same_window_is_one_record(self):
        self.client.get(self.pixel_url())
        self.client.get(self.pixel_url())
        self.assertEqual(ParticipantEvent.objects.filter(kind="email_open_signal").count(), 1)

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_unknown_token_returns_same_image_without_event(self):
        real = self.client.get(self.pixel_url())
        fake = self.client.get(reverse("email_open_pixel", args=[uuid.uuid4()]))
        self.assertEqual(real.content, fake.content)
        self.assertEqual(fake.status_code, 200)
        self.assertEqual(ParticipantEvent.objects.filter(kind="email_open_signal").count(), 1)

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_pending_and_failed_deliveries_not_tracked(self):
        for status in (DeliveryRecord.State.PENDING, DeliveryRecord.State.FAILED):
            self.delivery.status = status
            self.delivery.save(update_fields=["status"])
            self.client.get(self.pixel_url())
        self.assertFalse(ParticipantEvent.objects.exists())

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_prefetch_and_revoked_link_not_tracked(self):
        self.client.get(self.pixel_url(), HTTP_SEC_PURPOSE="prefetch")
        self.assertFalse(ParticipantEvent.objects.exists())
        self.link.revoked = True
        self.link.save(update_fields=["revoked"])
        self.client.get(self.pixel_url())
        self.assertFalse(ParticipantEvent.objects.exists())

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "0"})
    def test_global_switch_stops_tracking_even_old_tokens(self):
        self.client.get(self.pixel_url())
        self.assertFalse(ParticipantEvent.objects.exists())

    def test_pixel_in_html_only_and_no_employee_id_in_url(self):
        url = "http://127.0.0.1:8080/learn/abcd/"
        pixel_url = "http://127.0.0.1:8080" + self.pixel_url()
        _, text, html = render_email(self.template, self.employee, url, open_pixel_url=pixel_url)
        self.assertIn(pixel_url, html)
        self.assertIn('<img src="', html)
        self.assertNotIn(pixel_url, text)
        self.assertNotIn(self.employee.email, pixel_url)

    @patch.dict("os.environ", {"SMTP_OPEN_TRACKING_ENABLED": "1"})
    def test_campaign_report_and_csv_show_open_signal(self):
        self.client.get(self.pixel_url())
        self.client.force_login(self.admin)
        res = self.client.get(reverse("campaign_detail", args=[self.campaign.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["opened"], 1)
        self.assertEqual(res.context["pct_opened"], 100)
        self.assertContains(res, "Сигнал открытия")
        csv = self.client.get(reverse("campaign_export_csv", args=[self.campaign.pk]))
        self.assertEqual(csv.status_code, 200)
        self.assertIn("Сигнал открытия письма", csv.content.decode("utf-8-sig"))

    def test_methods_not_get_are_rejected(self):
        res = self.client.post(self.pixel_url())
        self.assertEqual(res.status_code, 405)
        self.assertFalse(ParticipantEvent.objects.exists())

    @patch.dict("os.environ", {
        "SMTP_HOST": "mailpit", "SMTP_CAMPAIGN_ENABLED": "1",
        "SMTP_ALLOWED_RECIPIENT_DOMAINS": "training.test",
        "SMTP_FROM_EMAIL": "training@training.test",
        "SMTP_OPEN_TRACKING_ENABLED": "1",
    })
    @patch("delivery.tasks._smtp_connect")
    def test_send_one_includes_pixel_in_html_mail(self, mocked_connect):
        self.dispatch.state = CampaignDispatch.State.RUNNING
        self.dispatch.save(update_fields=["state"])
        self.delivery.status = DeliveryRecord.State.SENDING
        self.delivery.save(update_fields=["status"])
        mocked_connect.return_value.__enter__.return_value.send_message.return_value = {}

        send_one(self.delivery.pk)

        sent = mocked_connect.return_value.__enter__.return_value.send_message.call_args.args[0]
        html_body = sent.get_body(preferencelist=("html",)).get_content()
        plain_body = sent.get_body(preferencelist=("plain",)).get_content()
        self.assertIn(self.pixel_url(), html_body)
        self.assertNotIn(self.pixel_url(), plain_body)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryRecord.State.ACCEPTED)
