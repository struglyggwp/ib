import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.utils import timezone

from campaigns.models import Campaign
from .models import CampaignDispatch, DeliveryRecord, SimulationDomain
from .policy import sandbox_mode, limits, allowed_recipient_domains
from .service import stop_dispatch, check_dispatch


@login_required
@require_GET
def domains(request):
    messages.info(request, "Домен отправителя берётся из SMTP_FROM_EMAIL автоматически. DNS TXT больше не требуется.")
    return redirect("campaign_list")


@login_required
@require_http_methods(["GET", "POST"])
def domain_create(request):
    return redirect("campaign_list")


@login_required
@require_POST
def domain_verify(request, pk):
    # Old links must not unexpectedly trigger a DNS verification lookup.
    return redirect("campaign_list")


@login_required
@permission_required("delivery.view_campaigndispatch", raise_exception=True)
@permission_required("campaigns.view_campaign", raise_exception=True)
@require_GET
def dispatch_detail(request, campaign_id):
    campaign = get_object_or_404(Campaign.objects.select_related("email_template"), pk=campaign_id)
    try:
        dispatch = CampaignDispatch.objects.select_related("domain").get(campaign=campaign)
    except CampaignDispatch.DoesNotExist:
        dispatch = None
    domains_qs = SimulationDomain.objects.filter(active=True)
    rows = []
    issues = []
    if dispatch:
        rows = dispatch.records.select_related("participant__employee")[:300]
    else:
        if domains_qs.exists():
            issues, _ = check_dispatch(campaign, domains_qs.first())
    counts = (dispatch.records.values("status").annotate(n=Count("pk")) if dispatch else [])
    return render(request, "delivery/dispatch.html", {
        "campaign": campaign, "dispatch": dispatch, "domains": domains_qs, "issues": issues,
        "rows": rows, "counts": counts, "audits": dispatch.audit.select_related("actor")[:15] if dispatch else [],
        "max_campaign": limits()[0], "allowed_domains": sorted(allowed_recipient_domains()),
        "enabled": os.environ.get("SMTP_CAMPAIGN_ENABLED", "0") == "1",
    })


@login_required
@permission_required("delivery.stop_dispatch", raise_exception=True)
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_POST
def dispatch_stop(request, campaign_id):
    try:
        stop_dispatch(campaign_id, request.user)
        messages.success(request, "Очередь остановлена. Уже принятые SMTP письма отозвать нельзя.")
    except CampaignDispatch.DoesNotExist:
        messages.error(request, "Рассылка не найдена.")
    return redirect("delivery_dispatch", campaign_id=campaign_id)
