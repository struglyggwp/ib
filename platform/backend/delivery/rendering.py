"""Safe training text + HTML; generated link is the only clickable link."""
import html
import re

import bleach
from django.urls import reverse

from email_templates.rendering import ALLOWED_ATTRIBUTES, ALLOWED_TAGS

_VARIABLE = re.compile(r"{{\s*([a-z_]+)\s*}}")


def render_email(template, employee, url, open_pixel_url=None):
    values = {
        "first_name": employee.first_name, "last_name": employee.last_name,
        "middle_name": employee.middle_name, "email": employee.email,
        "department": employee.department.name if employee.department else "",
        "position": employee.position.name if employee.position else "",
        "company_name": "Организация",
    }

    def replace(source, escape=False):
        return _VARIABLE.sub(lambda m: (html.escape(str(values[m.group(1)]), quote=True) if escape else str(values[m.group(1)])) if m.group(1) in values else m.group(0), source or "")

    subject = bleach.clean(replace(template.subject), tags=[], strip=True).replace("\r", " ").replace("\n", " ")[:250]
    raw_text = replace(template.text_body)
    sanitized = bleach.clean(replace(template.html_body, escape=True), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True, strip_comments=True)
    text = (raw_text or bleach.clean(sanitized, tags=[], strip=True)) + "\n\nУчебная ссылка: " + url + "\n"
    html_body = (sanitized or "<p>" + html.escape(raw_text).replace("\n", "<br>") + "</p>")
    html_body += '<p><a href="' + html.escape(url, quote=True) + '">Открыть учебную страницу</a></p>'
    if open_pixel_url:
        # A separate unguessable token per delivered message; no email/PII in URL.
        html_body += ('<img src="' + html.escape(open_pixel_url, quote=True)
                      + '" alt="" width="1" height="1" '
                      + 'style="display:block;width:1px;height:1px;border:0" />')
    return subject, text, html_body


def render_material_email(template, employee, url):
    values = {
        "first_name": employee.first_name, "last_name": employee.last_name,
        "middle_name": employee.middle_name, "email": employee.email,
        "department": employee.department.name if employee.department else "",
        "position": employee.position.name if employee.position else "",
        "company_name": "Организация",
    }

    def replace(source, escape=False):
        return _VARIABLE.sub(lambda m: (html.escape(str(values[m.group(1)]), quote=True) if escape else str(values[m.group(1)])) if m.group(1) in values else m.group(0), source or "")

    subject = bleach.clean(replace(template.subject), tags=[], strip=True).replace("\r", " ").replace("\n", " ")[:250]
    raw_text = replace(template.text_body)
    from email_templates.import_html import fragment
    sanitized = fragment(replace(template.html_body, escape=True))[0]
    body = sanitized or "<p>" + html.escape(raw_text).replace("\n", "<br>") + "</p>"
    anchor = '<a href="' + html.escape(url, quote=True) + '">Открыть учебную страницу</a>'
    body = body.replace("[[lesson]]", anchor) if "[[lesson]]" in body else body + "<p>" + anchor + "</p>"
    text = raw_text or bleach.clean(sanitized, tags=[], strip=True)
    text = text.replace("[[lesson]]", url) if "[[lesson]]" in text else text + "\n\nУчебная ссылка: " + url
    label = "Корпоративное обучение по ИБ"
    return "[Обучение ИБ] " + subject, label + "\n\n" + text, "<h2>" + label + "</h2>" + body
