"""One click to start an existing campaign, atomically creating the SMTP queue."""
import os

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from delivery.models import CampaignDispatch, SimulationDomain
from delivery.policy import sandbox_mode, template_sender, approved_addresses
from delivery.service import prepare_dispatch
from .models import Campaign


@transaction.atomic
def launch_campaign(campaign_id, actor):
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    current = CampaignDispatch.objects.filter(campaign_id=campaign_id).first()
    if current:
        return current, False
    if campaign.status in (Campaign.Status.COMPLETED, Campaign.Status.CANCELLED):
        raise ValidationError("Завершённую или отменённую кампанию нельзя запускать повторно.")

    sender = template_sender(campaign.email_template)
    if sender.count("@") != 1 or not sender.rsplit("@", 1)[-1]:
        raise ValidationError("Настройте SMTP_FROM_EMAIL в .env.")
    if not os.environ.get("SMTP_HOST", "").strip():
        raise ValidationError("Настройте SMTP_HOST в .env.")
    domain_name = sender.rsplit("@", 1)[-1]
    if sandbox_mode() and not domain_name.endswith(".test"):
        raise ValidationError("При использовании Mailpit отправитель должен иметь домен .test.")
    if not sandbox_mode() and sender not in approved_addresses():
        raise ValidationError("Разрешите адрес в Zimbra и SMTP_APPROVED_ALIASES.")

    domain, _ = SimulationDomain.objects.get_or_create(
        domain=domain_name,
        defaults={"created_by": actor, "sandbox_only": sandbox_mode()},
    )
    if not domain.active:
        raise ValidationError("Отправитель отключён администратором.")

    # Status is an internal detail, not a separate approval step in the interface.
    campaign.status = Campaign.Status.APPROVED
    campaign.save(update_fields=["status", "updated_at"])
    dispatch = prepare_dispatch(campaign_id, domain.pk, actor)
    return dispatch, True
