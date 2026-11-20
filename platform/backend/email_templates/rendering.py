import html
import re

import bleach

VARIABLES = {
    "first_name": "Алексей",
    "last_name": "Иванов",
    "middle_name": "Сергеевич",
    "email": "alexey.ivanov@example.test",
    "department": "Отдел обучения",
    "position": "Специалист",
    "company_name": "Учебная организация",
}

_TOKEN = re.compile(r"{{\s*([a-z_]+)\s*}}")
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "br", "div", "span", "h1", "h2", "h3", "h4", "table", "thead", "tbody",
    "tr", "td", "th", "strong", "em", "u", "hr", "blockquote", "ul", "ol", "li",
}
ALLOWED_ATTRIBUTES = {
    "a": ["title"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}


def substitute(value, *, escape_values=False):
    def replace(match):
        key = match.group(1)
        if key not in VARIABLES:
            return match.group(0)
        result = VARIABLES[key]
        return html.escape(result) if escape_values else result
    return _TOKEN.sub(replace, value or "")


def preview_html(value):
    from .import_html import fragment
    return fragment(substitute(value, escape_values=True))[0]

