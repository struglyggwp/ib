from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campaigns.models import Campaign
from .models import EmailTemplate
from .rendering import preview_html, substitute


class EmailTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="template-tester", password="test-password-123"
        )
        self.client.force_login(self.user)

    def test_template_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("email_template_list"))
        self.assertEqual(response.status_code, 302)

    def test_create_template(self):
        response = self.client.post(reverse("email_template_create"), {
            "name": "Учебное уведомление",
            "category": EmailTemplate.Category.AWARENESS,
            "tags": "обучение, безопасность, обучение",
            "subject": "Здравствуйте, {{ first_name }}",
            "html_body": "<p>Привет, {{ first_name }}</p>",
            "text_body": "Привет, {{ first_name }}",
            "description": "Тестовый шаблон",
            "status": EmailTemplate.Status.DRAFT,
        })
        self.assertEqual(response.status_code, 302)
        item = EmailTemplate.objects.get(name="Учебное уведомление")
        self.assertEqual(item.created_by, self.user)
        self.assertEqual(item.tags, "обучение, безопасность")

    def test_preview_substitutes_variables_and_strips_scripts(self):
        item = EmailTemplate.objects.create(
            name="Безопасный просмотр", subject="Привет, {{ first_name }}",
            html_body='<p onclick="alert(1)">Привет, {{ first_name }}</p><script>alert(2)</script>',
            created_by=self.user,
        )
        response = self.client.get(reverse("email_template_preview", args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Алексей")
        self.assertNotContains(response, "onclick=")
        self.assertNotContains(response, "<script>alert(2)</script>")

    def test_unknown_variables_are_not_evaluated(self):
        self.assertEqual(substitute("{{ unknown }}"), "{{ unknown }}")

    def test_delete_unlinks_campaign_without_deleting_campaign(self):
        item = EmailTemplate.objects.create(name="Для кампании", subject="Тема", text_body="Текст", created_by=self.user)
        campaign = Campaign.objects.create(name="Тестовая кампания", created_by=self.user, email_template=item)
        response = self.client.post(reverse("email_template_delete", args=[item.pk]))
        self.assertEqual(response.status_code, 302)
        campaign.refresh_from_db()
        self.assertIsNone(campaign.email_template)
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk).exists())

    def test_preview_html_sanitizes_javascript_urls(self):
        rendered = preview_html('<a href="javascript:alert(1)">ссылка</a><img src="x" onerror="alert(1)">')
        self.assertNotIn("javascript:", rendered)
        self.assertNotIn("onerror", rendered)

    def test_uploads_are_independent_and_published_material_is_inert(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fields = {"name": "Вводный курс", "category": "general", "subject": "Урок", "status": "active"}
        fields["email_file"] = SimpleUploadedFile("mail.html", b"<p>Message [[lesson]]</p>")
        fields["page_file"] = SimpleUploadedFile("lesson.html", b"<p>Lesson</p><form><input></form><img src='https://external.test/a'>")
        self.assertEqual(self.client.post(reverse("email_template_create"), fields).status_code, 302)
        item = EmailTemplate.objects.get()
        self.assertEqual(item.landing_html, "<p>Lesson</p>")
        fields.pop("email_file")
        fields["html_body"] = item.html_body
        fields["page_file"] = SimpleUploadedFile("new.html", b"<p>Second</p>")
        self.assertEqual(self.client.post(reverse("email_template_edit", args=[item.pk]), fields).status_code, 302)
        item.refresh_from_db()
        self.assertIn("Message [[lesson]]", item.html_body)
        self.client.logout()
        path = reverse("training_material", args=[item.pk])
        self.assertContains(self.client.get(path), "<p>Second</p>")
        self.assertEqual(self.client.post(path, {"test": "ignored"}).status_code, 405)
        item.status = "draft"
        item.save()
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_review_does_not_publish(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(reverse("email_template_create"), {
            "name": "Draft", "subject": "Materials", "category": "general", "status": "active",
            "review": "1", "email_file": SimpleUploadedFile("mail.html", b"<p>Email body</p>"),
            "page_file": SimpleUploadedFile("page.html", b"<p>Landing body</p>"),
        })
        self.assertContains(response, "<p>Landing body</p>")
        self.assertContains(response, "<p>Email body</p>")
        self.assertFalse(EmailTemplate.objects.exists())
