from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.models import Count, F
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from campaigns.models import Campaign, SafeEvent, ParticipantEvent
from employees.models import Employee
from email_templates.models import EmailTemplate

@login_required
def dashboard(request):
    campaigns = Campaign.objects.all()
    stats = {
        "total": campaigns.count(),
        "draft": campaigns.filter(status=Campaign.Status.DRAFT).count(),
        "active": campaigns.filter(status__in=[Campaign.Status.APPROVED, Campaign.Status.RUNNING]).count(),
        "events": SafeEvent.objects.count() + ParticipantEvent.objects.count(),
        "employees": Employee.objects.count(),
        "templates": EmailTemplate.objects.count(),
    }
    recent = campaigns.annotate(legacy_count=Count("events", distinct=True), tracked_count=Count("participants__training_events", distinct=True)).annotate(event_count=F("legacy_count") + F("tracked_count"))[:5]
    return render(request, "dashboard.html", {"stats": stats, "recent_campaigns": recent})

@require_GET
def health(request):
    db_ok = True
    try:
        connections["default"].ensure_connection()
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok})

def csrf_failure(request, reason=""):
    return render(request, "csrf_error.html", status=403)
