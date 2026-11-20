"""At-most-once SMTP hand-off per participant. Ambiguous SENDING rows require human review."""
from datetime import timedelta
import os
from email.message import EmailMessage
from types import SimpleNamespace

from celery import shared_task
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.views import _smtp_connect
from .models import CampaignDispatch, DeliveryRecord, DispatchAudit, DispatchThrottle
from .policy import campaign_enabled, limits, validate_destination, validate_sender
from .rendering import render_email, render_material_email


def claim_next_batch(dispatch_id):
    """Global cross-worker limit, sealed by a PostgreSQL singleton row lock."""
    with transaction.atomic():
        DispatchThrottle.objects.select_for_update().get(pk=1)
        dispatch = CampaignDispatch.objects.select_for_update().select_related("campaign", "domain").get(pk=dispatch_id)
        if dispatch.state not in (CampaignDispatch.State.QUEUED, CampaignDispatch.State.RUNNING):
            return [], False
        if not campaign_enabled() or dispatch.campaign.status != Campaign.Status.RUNNING or not dispatch.domain.active:
            dispatch.state = CampaignDispatch.State.STOPPED
            dispatch.finished_at = timezone.now()
            dispatch.save(update_fields=["state", "finished_at"])
            DeliveryRecord.objects.filter(dispatch=dispatch, status=DeliveryRecord.State.PENDING).update(status=DeliveryRecord.State.BLOCKED, error_code="policy_disabled")
            Campaign.objects.filter(pk=dispatch.campaign_id).update(status=Campaign.Status.CANCELLED)
            DispatchAudit.objects.create(dispatch=dispatch, action="policy_stopped")
            return [], False
        try:
            if validate_sender(dispatch.domain, dispatch.sender) != dispatch.sender:
                raise ValidationError("SMTP_FROM_EMAIL изменён")
        except ValidationError:
            dispatch.state = CampaignDispatch.State.STOPPED
            dispatch.finished_at = timezone.now()
            dispatch.save(update_fields=["state", "finished_at"])
            Campaign.objects.filter(pk=dispatch.campaign_id).update(status=Campaign.Status.CANCELLED)
            DispatchAudit.objects.create(dispatch=dispatch, action="policy_stopped", note="Отправитель или домен изменён")
            return [], False
        _, per_minute = limits()
        since = timezone.now() - timedelta(seconds=60)
        global_claims = DeliveryRecord.objects.filter(attempted_at__gte=since).count()
        n = max(0, min(10, per_minute - global_claims))
        ids = list(DeliveryRecord.objects.filter(dispatch=dispatch, status=DeliveryRecord.State.PENDING).values_list("pk", flat=True).order_by("pk")[:n])
        now = timezone.now()
        if ids:
            DeliveryRecord.objects.filter(pk__in=ids, status=DeliveryRecord.State.PENDING).update(status=DeliveryRecord.State.SENDING, attempted_at=now)
            dispatch.state = CampaignDispatch.State.RUNNING
            if dispatch.started_at is None:
                dispatch.started_at = now
            dispatch.save(update_fields=["state", "started_at"])
        return ids, True


def send_one(record_id):
    record = DeliveryRecord.objects.select_related("dispatch__domain", "participant__employee__department", "participant__employee__position", "participant__training_link").get(pk=record_id)
    dispatch = record.dispatch
    # Between claiming and SMTP there is a short window; recheck stop, policy, and active employee.
    if (record.status != DeliveryRecord.State.SENDING or dispatch.state != CampaignDispatch.State.RUNNING
            or dispatch.campaign.status != Campaign.Status.RUNNING or not campaign_enabled()
            or not dispatch.domain.active or not record.participant.employee.is_active
            or record.participant.employee.email.lower() != record.recipient_email.lower()
            or not validate_destination(record.recipient_email)):
        DeliveryRecord.objects.filter(pk=record.pk, status=DeliveryRecord.State.SENDING).update(status=DeliveryRecord.State.BLOCKED, error_code="policy_changed")
        return
    if dispatch.material_id:
        url = dispatch.landing_base_url.rstrip("/") + reverse("training_material", args=[dispatch.material_id])
        template = SimpleNamespace(subject=dispatch.template_subject, text_body=dispatch.template_text, html_body=dispatch.template_html)
        subject, text, html_body = render_material_email(template, record.participant.employee, url)
    else:
        link = record.participant.training_link
        if link.revoked or link.expires_at <= timezone.now():
            DeliveryRecord.objects.filter(pk=record.pk).update(status=DeliveryRecord.State.BLOCKED, error_code="link_revoked")
            return
        url = dispatch.landing_base_url.rstrip("/") + reverse("training_visit", args=[link.token])
        template = SimpleNamespace(subject=dispatch.template_subject, text_body=dispatch.template_text, html_body=dispatch.template_html)
        # Disable per deployment by setting SMTP_OPEN_TRACKING_ENABLED=0.
        open_pixel_url = None
        if os.environ.get("SMTP_OPEN_TRACKING_ENABLED", "1") == "1":
            open_pixel_url = dispatch.landing_base_url.rstrip("/") + reverse("email_open_pixel", args=[record.open_token])
        subject, text, html_body = render_email(template, record.participant.employee, url, open_pixel_url=open_pixel_url)
    message = EmailMessage()
    message["From"] = dispatch.sender
    message["To"] = record.recipient_email
    message["Subject"] = subject
    message["Message-ID"] = f"<{record.message_id}@{dispatch.domain.domain}>"
    message["X-Security-Awareness-Training"] = "yes"
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")
    try:
        with _smtp_connect() as smtp:
            refused = smtp.send_message(message)
            if refused:
                raise ValueError("SMTP_RECIPIENT_REFUSED")
    except Exception as exc:
        # Not automatically retried: network timeouts can occur AFTER SMTP acceptance.
        DeliveryRecord.objects.filter(pk=record.pk, status=DeliveryRecord.State.SENDING).update(status=DeliveryRecord.State.FAILED, error_code=type(exc).__name__[:100])
    else:
        DeliveryRecord.objects.filter(pk=record.pk, status=DeliveryRecord.State.SENDING).update(status=DeliveryRecord.State.ACCEPTED, smtp_accepted_at=timezone.now())


@shared_task(bind=True, name="delivery.dispatch_campaign", ignore_result=True)
def dispatch_campaign(self, dispatch_id):
    ids, active = claim_next_batch(dispatch_id)
    if not active:
        return
    for record_id in ids:
        send_one(record_id)
    with transaction.atomic():
        dispatch = CampaignDispatch.objects.select_for_update().get(pk=dispatch_id)
        if dispatch.state not in (CampaignDispatch.State.QUEUED, CampaignDispatch.State.RUNNING):
            return
        if not DeliveryRecord.objects.filter(dispatch=dispatch, status=DeliveryRecord.State.PENDING).exists():
            dispatch.state = CampaignDispatch.State.FINISHED
            dispatch.finished_at = timezone.now()
            dispatch.save(update_fields=["state", "finished_at"])
            DispatchAudit.objects.create(dispatch=dispatch, action="smtp_finished", note="SMTP-очередь обработана; доставка в ящик не подтверждается")
            return
    # Delay bounds throughput and prevents hammering SMTP with one giant task.
    dispatch_campaign.apply_async(args=[str(dispatch_id)], countdown=60)
