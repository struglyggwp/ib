from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from campaigns.models import Campaign, CampaignParticipant, TrainingLink
from email_templates.models import EmailTemplate

from .models import CampaignDispatch, DeliveryRecord, DispatchAudit, SimulationDomain
from .policy import campaign_enabled, landing_url, limits, template_sender, validate_destination, validate_sender


def check_dispatch(campaign, domain):
    issues = []
    if not campaign_enabled():
        issues.append("SMTP_CAMPAIGN_ENABLED=1 не задан. Рассылка отключена.")
    if campaign.status != Campaign.Status.APPROVED:
        issues.append("Кампания должна иметь статус «Согласована».")
    if not campaign.email_template_id or campaign.email_template.status != EmailTemplate.Status.ACTIVE:
        issues.append("Выберите активный шаблон письма.")
    else:
        if not (campaign.email_template.text_body.strip() or campaign.email_template.html_body.strip()):
            issues.append("Текст шаблона пуст.")
    try:
        validate_sender(domain, template_sender(campaign.email_template))
        landing_url(domain)
    except ValidationError as exc:
        issues.extend(exc.messages)
    max_campaign, _ = limits()
    audience = list(campaign.participants.select_related("employee").all())
    if not audience:
        issues.append("Добавьте участников кампании.")
    if len(audience) > max_campaign:
        issues.append(f"Допустимый максимум участников: {max_campaign}.")
    if any(not p.employee.is_active or not validate_destination(p.employee.email) for p in audience):
        issues.append("Есть неактивные участники либо адреса за пределами SMTP_ALLOWED_RECIPIENT_DOMAINS.")
    return issues, audience


@transaction.atomic
def prepare_dispatch(campaign_id, domain_id, actor):
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if CampaignDispatch.objects.filter(campaign=campaign).exists():
        raise ValidationError("Рассылка для этой кампании уже создана. Повторный запуск исключён.")
    domain = SimulationDomain.objects.select_for_update().get(pk=domain_id)
    issues, audience = check_dispatch(campaign, domain)
    if issues:
        raise ValidationError(issues)
    now = timezone.now()
    dispatch = CampaignDispatch.objects.create(
        campaign=campaign, domain=domain, sender=validate_sender(domain, template_sender(campaign.email_template)), landing_base_url=landing_url(domain),
        created_by=actor,
        material=campaign.email_template, template_subject=campaign.email_template.subject, template_text=campaign.email_template.text_body,
        template_html=campaign.email_template.html_body,
    )
    for participant in audience:
        link = TrainingLink.objects.filter(participant=participant).first()
        if link and (link.revoked or link.expires_at <= now):
            link.delete()
            link = None
        if link is None:
            TrainingLink.objects.create(participant=participant, created_by=actor, expires_at=now + timedelta(days=30))
        DeliveryRecord.objects.create(dispatch=dispatch, participant=participant, recipient_email=participant.employee.email)
    campaign.status = Campaign.Status.RUNNING
    campaign.save(update_fields=["status", "updated_at"])
    DispatchAudit.objects.create(dispatch=dispatch, actor=actor, action="approved_start", note=f"Участников: {len(audience)}")
    return dispatch


@transaction.atomic
def stop_dispatch(campaign_id, actor):
    dispatch = CampaignDispatch.objects.select_for_update().select_related("campaign").get(campaign_id=campaign_id)
    if dispatch.state == CampaignDispatch.State.STOPPED:
        return dispatch
    dispatch.state = CampaignDispatch.State.STOPPED
    dispatch.finished_at = timezone.now()
    dispatch.save(update_fields=["state", "finished_at"])
    DeliveryRecord.objects.filter(dispatch=dispatch, status=DeliveryRecord.State.PENDING).update(status=DeliveryRecord.State.BLOCKED, error_code="operator_stopped")
    Campaign.objects.filter(pk=campaign_id).update(status=Campaign.Status.CANCELLED)
    DispatchAudit.objects.create(dispatch=dispatch, actor=actor, action="operator_stopped")
    return dispatch
