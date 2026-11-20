from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from campaigns.models import Campaign, CampaignParticipant, TrainingLink
from email_templates.models import EmailTemplate
from employees.models import Employee
from .models import SimulationDomain, CampaignDispatch, DeliveryRecord
from .policy import landing_url, validate_destination, validate_sender
from .rendering import render_email
from .service import prepare_dispatch, stop_dispatch
from .tasks import claim_next_batch, send_one


TEST_ENV = {
    "SMTP_HOST": "mailpit", "SMTP_PORT": "1025", "SMTP_USE_STARTTLS": "0", "SMTP_USE_SSL": "0",
    "SMTP_FROM_EMAIL": "training@training.test", "SMTP_CAMPAIGN_ENABLED": "1",
    "SMTP_ALLOWED_RECIPIENT_DOMAINS": "training.test", "SMTP_MAX_PER_CAMPAIGN": "100", "SMTP_MAX_PER_MINUTE": "10",
}


class DeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("deladmin", "admin@training.test", "SecurePasswordForTests!123")
        cls.employee = Employee.objects.create(first_name="Светлана", last_name="Климова", email="s@training.test")
        cls.template = EmailTemplate.objects.create(name="Учебное письмо", subject="Добрый день, {{first_name}}", text_body="Пройдите учебное упражнение.", status="active", created_by=cls.admin)
        cls.campaign = Campaign.objects.create(name="Тест доставки", email_template=cls.template, status="approved", created_by=cls.admin)
        cls.participant = CampaignParticipant.objects.create(campaign=cls.campaign, employee=cls.employee)
        cls.domain = SimulationDomain.objects.create(domain="training.test", created_by=cls.admin, verified_at=timezone.now(), sandbox_only=True)

    @patch.dict("os.environ", TEST_ENV)
    def test_prepares_snapshots_links_and_status(self):
        obj = prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)
        self.assertEqual(obj.records.count(), 1)
        self.assertEqual(obj.records.first().recipient_email, "s@training.test")
        self.assertTrue(TrainingLink.objects.filter(participant=self.participant).exists())
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, Campaign.Status.RUNNING)
        with self.assertRaises(ValidationError):
            prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)

    @patch.dict("os.environ", TEST_ENV)
    def test_no_send_on_draft_campaign(self):
        self.campaign.status = Campaign.Status.DRAFT
        self.campaign.save()
        with self.assertRaises(ValidationError):
            prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)
        self.assertFalse(CampaignDispatch.objects.exists())

    @patch.dict("os.environ", {**TEST_ENV, "SMTP_CAMPAIGN_ENABLED": "0"})
    def test_explicit_feature_switch_required(self):
        with self.assertRaises(ValidationError):
            prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)

    @patch.dict("os.environ", {**TEST_ENV, "SMTP_ALLOWED_RECIPIENT_DOMAINS": "other.test"})
    def test_refuses_unapproved_recipient_domain(self):
        with self.assertRaises(ValidationError):
            prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)

    @patch.dict("os.environ", TEST_ENV)
    def test_renders_personal_text_without_active_html(self):
        self.template.html_body = '<p>{{ first_name }}</p><script>evil()</script><a href="https://external.test">external</a>'
        url = "https://training.test/learn/0000/"
        subject, text, html = render_email(self.template, self.employee, url)
        self.assertIn("Светлана", subject)
        self.assertIn(url, text)
        self.assertNotIn("<script", html)
        self.assertNotIn("href=\"https://external.test\"", html)
        self.assertIn('href="' + url + '"', html)

    @patch.dict("os.environ", TEST_ENV)
    def test_claim_and_stop(self):
        dispatch = prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)
        ids, active = claim_next_batch(dispatch.pk)
        self.assertTrue(active)
        self.assertEqual(len(ids), 1)
        stop_dispatch(self.campaign.pk, self.admin)
        dispatch.refresh_from_db()
        self.assertEqual(dispatch.state, CampaignDispatch.State.STOPPED)
        ids, active = claim_next_batch(dispatch.pk)
        self.assertFalse(active)
        self.assertFalse(ids)

    @patch.dict("os.environ", TEST_ENV)
    @patch("delivery.tasks._smtp_connect")
    def test_smtp_acceptance_is_not_delivery(self, mocked_connect):
        dispatch = prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)
        ids, _ = claim_next_batch(dispatch.pk)
        smtp = mocked_connect.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        send_one(ids[0])
        row = DeliveryRecord.objects.get(pk=ids[0])
        self.assertEqual(row.status, DeliveryRecord.State.ACCEPTED)
        self.assertIsNotNone(row.smtp_accepted_at)
        msg = smtp.send_message.call_args[0][0]
        self.assertIn("/material/", msg.get_body(preferencelist=("plain",)).get_content())
        self.assertEqual(msg["X-Security-Awareness-Training"], "yes")

    @patch.dict("os.environ", TEST_ENV)
    @patch("delivery.tasks._smtp_connect")
    def test_smtp_timeout_is_not_auto_retried(self, mocked_connect):
        dispatch = prepare_dispatch(self.campaign.pk, self.domain.pk, self.admin)
        ids, _ = claim_next_batch(dispatch.pk)
        mocked_connect.side_effect = TimeoutError("test")
        send_one(ids[0])
        record = DeliveryRecord.objects.get(pk=ids[0])
        self.assertEqual(record.status, DeliveryRecord.State.FAILED)
        self.assertEqual(record.error_code, "TimeoutError")
        self.assertEqual(DeliveryRecord.objects.filter(status=DeliveryRecord.State.PENDING).count(), 0)

    def test_dispatch_report_requires_permission(self):
        visitor = get_user_model().objects.create_user("visitor-del", password="VerySafePassword!123")
        self.client.force_login(visitor)
        self.assertEqual(self.client.get(reverse("delivery_dispatch", args=[self.campaign.pk])).status_code, 403)

    @patch.dict("os.environ", TEST_ENV)
    def test_old_domain_verification_url_no_longer_changes_db(self):
        dom = SimulationDomain.objects.create(domain="demo.test", created_by=self.admin)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("delivery_domain_verify", args=[dom.pk]))
        self.assertEqual(response.status_code, 302)
        dom.refresh_from_db()
        self.assertIsNone(dom.verified_at)

    @patch.dict("os.environ", {
        **TEST_ENV, "SMTP_HOST": "zimbra.internal.test", "SMTP_FROM_EMAIL": "sender@internal.test",
        "SMTP_USERNAME": "sender@internal.test",
    })
    def test_authenticated_zimbra_sender_does_not_need_dns_txt(self):
        domain = SimulationDomain.objects.create(domain="internal.test", created_by=self.admin)
        self.assertEqual(validate_sender(domain), "sender@internal.test")

    @patch.dict("os.environ", {
        **TEST_ENV, "SMTP_HOST": "zimbra.internal.test", "SMTP_FROM_EMAIL": "boss@internal.test",
        "SMTP_USERNAME": "other@internal.test",
    })
    def test_unmatched_zimbra_sender_rejected(self):
        domain = SimulationDomain.objects.create(domain="internal.test", created_by=self.admin)
        with self.assertRaises(ValidationError):
            validate_sender(domain)

    @patch.dict("os.environ", {**TEST_ENV, "SMTP_HOST": "smtp.example.org"})
    def test_sandbox_cannot_go_to_zimbra(self):
        with self.assertRaises(ValidationError):
            validate_sender(self.domain)

    @patch.dict("os.environ", TEST_ENV)
    def test_csv_export_and_formula_safety(self):
        self.employee.first_name = "=1+1"
        self.employee.save(update_fields=["first_name"])
        self.client.force_login(self.admin)
        response = self.client.get(reverse("campaign_export_csv", args=[self.campaign.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=1+1", response.content.decode("utf-8-sig"))
