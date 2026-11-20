import os
import csv
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import CampaignForm
from .launch import launch_campaign
from delivery.models import CampaignDispatch
from .models import Campaign, CampaignParticipant, ParticipantEvent, SafeEvent, TrainingLink


@login_required
@permission_required("campaigns.view_campaign", raise_exception=True)
def campaign_list(request):
    qs = Campaign.objects.annotate(legacy_count=Count("events", distinct=True), tracked_count=Count("participants__training_events", distinct=True)).annotate(event_count=F("legacy_count") + F("tracked_count"))
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if status in Campaign.Status.values:
        qs = qs.filter(status=status)
    return render(request, "campaigns/list.html", {
        "campaigns": qs, "query": query, "selected_status": status,
        "statuses": Campaign.Status.choices,
    })


def _save_audience(campaign, form):
    selected_ids = form.audience_ids()
    current_ids = set(campaign.participants.values_list("employee_id", flat=True))
    removed_ids = current_ids - selected_ids
    if removed_ids:
        CampaignParticipant.objects.filter(campaign=campaign, employee_id__in=removed_ids).delete()
    to_add = selected_ids - current_ids
    CampaignParticipant.objects.bulk_create([
        CampaignParticipant(campaign=campaign, employee_id=pk) for pk in to_add
    ], batch_size=500)


@login_required
@permission_required("campaigns.add_campaign", raise_exception=True)
@require_http_methods(["GET", "POST"])
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.status = Campaign.Status.DRAFT
            campaign.save()
            _save_audience(campaign, form)
        messages.success(request, "Кампания создана. Нажмите «Запустить» для отправки.")
        return redirect("campaign_detail", campaign_id=campaign.pk)
    return render(request, "campaigns/form.html", {"form": form, "page_title": "Новая кампания"})


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_http_methods(["GET", "POST"])
def campaign_edit(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    if (CampaignDispatch.objects.filter(campaign=campaign).exists()
            or TrainingLink.objects.filter(participant__campaign=campaign).exists()
            or ParticipantEvent.objects.filter(participant__campaign=campaign).exists()):
        messages.error(request, "Кампания уже имеет ссылки, события или отправки. Редактирование отключено для сохранения истории.")
        return redirect("campaign_detail", campaign_id=campaign.pk)
    form = CampaignForm(request.POST or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Campaign.objects.select_for_update().get(pk=campaign_id)
            if CampaignDispatch.objects.filter(campaign=locked).exists():
                messages.error(request, "Кампания уже запущена.")
                return redirect("campaign_detail", campaign_id=campaign_id)
            form.save()
            _save_audience(locked, form)
        messages.success(request, "Кампания и участники сохранены.")
        return redirect("campaign_detail", campaign_id=campaign.pk)
    return render(request, "campaigns/form.html", {"form": form, "page_title": "Изменить кампанию", "campaign": campaign})


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@permission_required("delivery.start_dispatch", raise_exception=True)
@require_POST
def campaign_start(request, campaign_id):
    get_object_or_404(Campaign, pk=campaign_id)
    try:
        with transaction.atomic():
            dispatch, created = launch_campaign(campaign_id, request.user)
            if created:
                def enqueue():
                    try:
                        from delivery.tasks import dispatch_campaign
                        dispatch_campaign.delay(str(dispatch.pk))
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception("Не удалось отправить задачу в Celery: %s", dispatch.pk)
                transaction.on_commit(enqueue)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
        return redirect("campaign_detail", campaign_id=campaign_id)
    if created:
        messages.success(request, "Кампания запущена. Письма поставлены в очередь SMTP.")
    else:
        messages.info(request, "Кампания уже запускалась. Повторной отправки не будет.")
    return redirect("campaign_detail", campaign_id=campaign_id)


@login_required
@permission_required("campaigns.view_campaign", raise_exception=True)
@require_GET
def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(Campaign.objects.select_related("email_template"), pk=campaign_id)
    base = CampaignParticipant.objects.filter(campaign=campaign).select_related(
        "employee", "employee__department", "training_link", "delivery_record"
    ).order_by("employee__last_name", "employee__first_name", "pk")
    query = request.GET.get("q", "").strip()[:100]
    group = request.GET.get("department", "").strip()
    action = request.GET.get("action", "").strip()
    if query:
        base = base.filter(Q(employee__first_name__icontains=query) | Q(employee__last_name__icontains=query) | Q(employee__email__icontains=query))
    if group.isdigit() and len(group) <= 9:
        base = base.filter(employee__department_id=int(group))
    if action in ParticipantEvent.Kind.values:
        base = base.filter(training_events__kind=action).distinct()
    if action == "none":
        base = base.exclude(training_events__kind=ParticipantEvent.Kind.LINK_VISITED)

    page = Paginator(base, 25).get_page(request.GET.get("page"))
    page_ids = [item.pk for item in page.object_list]
    first_events = {}
    for event in ParticipantEvent.objects.filter(participant_id__in=page_ids).order_by("occurred_at"):
        first_events.setdefault((event.participant_id, event.kind), event.occurred_at)
    rows = []
    for item in page.object_list:
        link = getattr(item, "training_link", None)
        rows.append({
            "participant": item,
            "delivery": getattr(item, "delivery_record", None),
            "opened": first_events.get((item.pk, ParticipantEvent.Kind.EMAIL_OPEN_SIGNAL)),
            "visited": first_events.get((item.pk, ParticipantEvent.Kind.LINK_VISITED)),
            "completed": first_events.get((item.pk, ParticipantEvent.Kind.TRAINING_COMPLETED)),
            "token": link.token if link and not link.revoked and link.expires_at > timezone.now() else None,
        })
    counts = ParticipantEvent.objects.filter(participant__campaign=campaign).aggregate(
        opened=Count("participant_id", filter=Q(kind=ParticipantEvent.Kind.EMAIL_OPEN_SIGNAL), distinct=True),
        visited=Count("participant_id", filter=Q(kind=ParticipantEvent.Kind.LINK_VISITED), distinct=True),
        completed=Count("participant_id", filter=Q(kind=ParticipantEvent.Kind.TRAINING_COMPLETED), distinct=True),
    )
    total = CampaignParticipant.objects.filter(campaign=campaign).count()
    opened = counts["opened"] or 0
    visited = counts["visited"] or 0
    completed = counts["completed"] or 0
    departments = list(campaign.participants.filter(employee__department__isnull=False).values(
        "employee__department_id", "employee__department__name"
    ).distinct().order_by("employee__department__name"))
    recent_events = ParticipantEvent.objects.filter(participant__campaign=campaign).select_related(
        "participant__employee"
    ).order_by("-occurred_at")[:8]
    return render(request, "campaigns/detail.html", {
        "campaign": campaign, "has_dispatch": CampaignDispatch.objects.filter(campaign=campaign).exists(),
        "rows": rows, "page": page, "query": query, "group": group, "action": action,
        "departments": departments, "recent_events": recent_events,
        "total": total, "opened": opened, "visited": visited, "completed": completed,
        "pct_opened": round(100 * opened / total) if total else 0,
        "pct_visited": round(100 * visited / total) if total else 0,
        "pct_completed": round(100 * completed / total) if total else 0,
        "legacy_event_count": campaign.events.count(),
        "smtp_accepted": sum(1 for row in rows if row["delivery"] and row["delivery"].status == "accepted"),
        "mailpit_url": "http://127.0.0.1:8025/",
    })


def _csv_safe(value):
    s = str(value or "")
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s


@login_required
@permission_required("campaigns.view_campaign", raise_exception=True)
@require_GET
def campaign_export_csv(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="campaign-{campaign.pk}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Фамилия", "Имя", "Email", "Передача SMTP", "Принято SMTP", "Сигнал открытия письма", "Переход", "Завершение"])
    records = CampaignParticipant.objects.filter(campaign=campaign).select_related("employee", "delivery_record").order_by("employee__last_name", "employee__first_name")
    event_firsts = {}
    for ev in ParticipantEvent.objects.filter(participant__campaign=campaign).order_by("occurred_at"):
        event_firsts.setdefault((ev.participant_id, ev.kind), ev.occurred_at)
    for participant in records:
        delivery = getattr(participant, "delivery_record", None)
        def stamp(dt):
            return timezone.localtime(dt).strftime("%d.%m.%Y %H:%M:%S") if dt else ""
        writer.writerow([
            _csv_safe(participant.employee.last_name), _csv_safe(participant.employee.first_name),
            _csv_safe(participant.employee.email), delivery.get_status_display() if delivery else "",
            stamp(delivery.smtp_accepted_at) if delivery else "",
            stamp(event_firsts.get((participant.pk, ParticipantEvent.Kind.EMAIL_OPEN_SIGNAL))),
            stamp(event_firsts.get((participant.pk, ParticipantEvent.Kind.LINK_VISITED))),
            stamp(event_firsts.get((participant.pk, ParticipantEvent.Kind.TRAINING_COMPLETED))),
        ])
    return response


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_POST
def create_training_links(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    participants = campaign.participants.select_related("employee").filter(employee__is_active=True)
    if participants.count() > 2000:
        messages.error(request, "Для одной операции допускается не более 2000 участников.")
        return redirect("campaign_detail", campaign_id=campaign_id)
    created = 0
    for participant in participants.iterator():
        link, was_created = TrainingLink.objects.get_or_create(
            participant=participant,
            defaults={"created_by": request.user, "expires_at": timezone.now() + timedelta(days=30)},
        )
        renewed = bool(link.revoked or link.expires_at <= timezone.now())
        if renewed:
            # Rotating a primary key via save(update_fields=...) is unsafe.
            # Delete only the link; events belong to participant and are preserved.
            link.delete()
            TrainingLink.objects.create(
                participant=participant,
                created_by=request.user,
                expires_at=timezone.now() + timedelta(days=30),
            )
        created += int(was_created or renewed)
    messages.success(request, f"Создано учебных ссылок: {created}. Письма не отправлялись.")
    return redirect("campaign_detail", campaign_id=campaign_id)


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_POST
def revoke_training_link(request, campaign_id, participant_id):
    item = get_object_or_404(CampaignParticipant, campaign_id=campaign_id, pk=participant_id)
    TrainingLink.objects.filter(participant=item).update(revoked=True)
    messages.success(request, "Учебная ссылка отозвана.")
    return redirect("campaign_detail", campaign_id=campaign_id)


def _record_training_event(participant, kind):
    # Each kind is recorded at most once per 5-minute interval, without IP or form values.
    now = timezone.now()
    return ParticipantEvent.objects.get_or_create(
        participant=participant, kind=kind, dedupe_slot=int(now.timestamp()) // 300,
    )[0]


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def training_visit(request, token):
    link = get_object_or_404(
        TrainingLink.objects.select_related("participant__campaign", "participant__employee"), token=token,
    )
    if link.revoked or link.expires_at <= timezone.now():
        return render(request, "campaigns/training_unavailable.html", status=410)
    if link.participant.campaign.status not in (Campaign.Status.APPROVED, Campaign.Status.RUNNING):
        return render(request, "campaigns/training_unavailable.html", status=403)
    if request.method == "POST":
        # No form fields are persisted: this is solely the acknowledgment button.
        _record_training_event(link.participant, ParticipantEvent.Kind.TRAINING_COMPLETED)
        return render(request, "campaigns/training_landing.html", {"completed": True})
    purpose = (request.headers.get("Purpose", "") + " " + request.headers.get("Sec-Purpose", "") + " " + request.headers.get("X-Moz", "")).lower()
    if "prefetch" not in purpose and "prerender" not in purpose:
        _record_training_event(link.participant, ParticipantEvent.Kind.LINK_VISITED)
    response = render(request, "campaigns/training_landing.html", {"completed": False})
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


# Legacy endpoint stays available for admin diagnostics only; not a source of individual identity.
@login_required
@permission_required("campaigns.add_safeevent", raise_exception=True)
@require_POST
def record_safe_event(request, campaign_id, kind):
    if kind not in ("page_view", "form_submitted"):
        raise Http404()
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    SafeEvent.objects.create(campaign=campaign, kind=kind, source="admin_test", confidence=0)
    return HttpResponse("OK", content_type="text/plain")


def _smtp_settings():
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    use_ssl = os.environ.get("SMTP_USE_SSL", "0") == "1"
    use_tls = os.environ.get("SMTP_USE_STARTTLS", "1") == "1"
    if username and not (use_ssl or use_tls):
        raise ValueError("SMTP с учётными данными требует TLS.")
    if use_ssl and use_tls:
        raise ValueError("Нельзя одновременно включить TLS и SSL")
    if not 1 <= port <= 65535:
        raise ValueError("Некорректный SMTP-порт")
    return host, port, username, password, use_ssl, use_tls


def _smtp_connect():
    host, port, username, password, use_ssl, use_tls = _smtp_settings()
    if not host:
        raise ValueError("SMTP_HOST не задан в .env")
    client = (smtplib.SMTP_SSL(host, port, timeout=5, context=ssl.create_default_context())
              if use_ssl else smtplib.SMTP(host, port, timeout=5))
    try:
        client.ehlo()
        if use_tls:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if username:
            if not password:
                raise ValueError("SMTP_PASSWORD не задан в .env")
            client.login(username, password)
        return client
    except Exception:
        client.close()
        raise


@login_required
@permission_required("campaigns.view_campaign", raise_exception=True)
@require_GET
def mail_diagnostics(request):
    allowlist = sorted({v.strip().lower() for v in os.environ.get("SMTP_TEST_RECIPIENTS", "").split(",") if v.strip()})
    return render(request, "campaigns/mail_diagnostics.html", {
        "host": os.environ.get("SMTP_HOST", "").strip() or "не настроен",
        "port": os.environ.get("SMTP_PORT", "587"),
        "allowlist": allowlist,
    })


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_POST
def mail_check_connection(request):
    try:
        with _smtp_connect() as client:
            client.noop()
        messages.success(request, "SMTP-подключение и выбранный способ аутентификации работают.")
    except (OSError, smtplib.SMTPException, ValueError) as error:
        messages.error(request, f"SMTP-проверка не пройдена ({type(error).__name__}). Проверьте хост, TLS и учётные данные в .env.")
    return redirect("mail_diagnostics")


@login_required
@permission_required("campaigns.change_campaign", raise_exception=True)
@require_POST
def mail_send_test(request):
    allowed = {v.strip().lower() for v in os.environ.get("SMTP_TEST_RECIPIENTS", "").split(",") if v.strip()}
    target = request.POST.get("recipient", "").strip().lower()
    sender = os.environ.get("SMTP_FROM_EMAIL", "").strip()
    if not allowed or target not in allowed or not sender:
        messages.error(request, "Укажите SMTP_FROM_EMAIL и разрешённого адресата SMTP_TEST_RECIPIENTS в .env.")
        return redirect("mail_diagnostics")
    if not cache.add(f"smtp_test_{request.user.pk}", "1", timeout=60):
        messages.error(request, "Повторную отправку можно делать не чаще раза в минуту.")
        return redirect("mail_diagnostics")
    try:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = target
        msg["Subject"] = "[TEST] Security Awareness: проверка SMTP"
        msg.set_content("Это безопасное тестовое письмо для проверки SMTP. Кампания не запускалась. Пароли и ссылки отсутствуют.")
        with _smtp_connect() as client:
            client.send_message(msg)
        messages.success(request, f"Тестовое письмо передано SMTP-серверу для {target}. Это не гарантирует доставку в ящик.")
    except (OSError, smtplib.SMTPException, ValueError) as error:
        messages.error(request, f"Не удалось передать письмо SMTP-серверу ({type(error).__name__}).")
    return redirect("mail_diagnostics")
