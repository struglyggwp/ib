import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmailTemplateForm
from .models import EmailTemplate
from .rendering import VARIABLES, preview_html, substitute


@login_required
def template_list(request):
    qs = EmailTemplate.objects.select_related("created_by")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query) | Q(subject__icontains=query)
            | Q(tags__icontains=query) | Q(description__icontains=query)
        )
    if category in EmailTemplate.Category.values:
        qs = qs.filter(category=category)
    if status in EmailTemplate.Status.values:
        qs = qs.filter(status=status)
    return render(request, "email_templates/list.html", {
        "templates": qs, "query": query, "selected_category": category,
        "selected_status": status, "categories": EmailTemplate.Category.choices,
        "statuses": EmailTemplate.Status.choices,
    })


def review_import(request, form, item=None):
    data = request.POST.copy()
    for field in ("html_body", "landing_html"):
        data[field] = form.cleaned_data.get(field, "")
    context = {
        "form": EmailTemplateForm(data, instance=item),
        "item": item,
        "page_title": "Проверка перед сохранением",
        "review": True,
        "mail_preview": preview_html(data["html_body"]),
        "landing_preview": data["landing_html"],
        "notes": form.import_notes,
    }
    return render(request, "email_templates/form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def template_create(request):
    form = EmailTemplateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        if "review" in request.POST:
            return review_import(request, form)
        item = form.save(commit=False)
        item.created_by = request.user
        item.save()
        for note in form.import_notes:
            messages.info(request, note)
        messages.success(request, "Шаблон письма создан.")
        return redirect("email_template_detail", template_id=item.pk)
    return render(request, "email_templates/form.html", {"form": form, "page_title": "Новый шаблон"})


@login_required
def template_detail(request, template_id):
    item = get_object_or_404(EmailTemplate.objects.select_related("created_by"), pk=template_id)
    return render(request, "email_templates/detail.html", {"item": item})


@login_required
@require_http_methods(["GET", "POST"])
def template_edit(request, template_id):
    item = get_object_or_404(EmailTemplate, pk=template_id)
    form = EmailTemplateForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        if "review" in request.POST:
            return review_import(request, form, item)
        form.save()
        for note in form.import_notes:
            messages.info(request, note)
        messages.success(request, "Изменения шаблона сохранены.")
        return redirect("email_template_detail", template_id=item.pk)
    return render(request, "email_templates/form.html", {"form": form, "page_title": "Изменить шаблон", "item": item})


@login_required
@require_POST
def template_delete(request, template_id):
    item = get_object_or_404(EmailTemplate, pk=template_id)
    try:
        item.delete()
    except ProtectedError:
        messages.error(request, "Нельзя удалить шаблон, используемый сценарием. Сначала смените шаблон в сценарии.")
        return redirect("email_template_detail", template_id=item.pk)
    messages.success(request, "Шаблон удалён.")
    return redirect("email_template_list")


@login_required
def template_preview(request, template_id):
    item = get_object_or_404(EmailTemplate, pk=template_id)
    return render(request, "email_templates/preview.html", {
        "item": item,
        "preview_subject": substitute(item.subject),
        "preview_text": substitute(item.text_body),
        "recipients": [x.strip() for x in os.environ.get("SMTP_TEST_RECIPIENTS", "").split(",") if x.strip()],
        "preview_html": preview_html(item.html_body),
        "variables": VARIABLES, "page_preview": preview_html(item.landing_html),
    })


@require_http_methods(["GET", "HEAD"])
def training_material(request, template_id):
    item = get_object_or_404(EmailTemplate, pk=template_id, status=EmailTemplate.Status.ACTIVE)
    from .import_html import fragment
    response = render(request, "email_templates/material.html", {"content": fragment(item.landing_html)[0]})
    response["Content-Security-Policy"] = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def send_preview(request, template_id):
    import smtplib
    from email.message import EmailMessage
    from email.utils import make_msgid
    from types import SimpleNamespace

    from django.core.cache import cache
    from django.core.exceptions import ValidationError
    from django.urls import reverse
    from campaigns.views import _smtp_connect
    from delivery.policy import landing_url, sandbox_mode, template_sender, validate_sender
    from delivery.rendering import render_material_email

    item = get_object_or_404(EmailTemplate, pk=template_id)
    recipient = request.POST.get("recipient", "").strip().lower()
    allowed = {v.strip().lower() for v in os.environ.get("SMTP_TEST_RECIPIENTS", "").split(",") if v.strip()}
    if not recipient or recipient not in allowed:
        messages.error(request, "Выберите разрешённый тестовый ящик.")
        return redirect("email_template_preview", template_id=item.pk)
    try:
        sender = template_sender(item)
        domain = SimpleNamespace(domain=sender.split("@")[-1], active=True, sandbox_only=sandbox_mode())
        validate_sender(domain, sender)
        url = landing_url(domain) + reverse("training_material", args=[item.pk])
        user = SimpleNamespace(**{**VARIABLES, "department": None, "position": None})
        subject, plain, body = render_material_email(item, user, url)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient
        message["Message-ID"] = make_msgid(domain=domain.domain)
        message.set_content(plain)
        message.add_alternative(body, subtype="html")
        if not cache.add(f"template_preview:{request.user.pk}", 1, timeout=60):
            raise ValidationError("Повторите через минуту.")
        with _smtp_connect() as client:
            client.send_message(message)
        messages.success(request, "Тестовое письмо принято SMTP-сервером.")
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    except (ValueError, OSError, smtplib.SMTPException) as error:
        messages.error(request, f"Ошибка SMTP ({type(error).__name__}).")
    return redirect("email_template_preview", template_id=item.pk)
