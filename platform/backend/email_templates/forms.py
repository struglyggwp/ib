from django import forms
from .models import EmailTemplate


class EmailTemplateForm(forms.ModelForm):
    email_file = forms.FileField(label="Загрузить HTML письма", required=False)
    page_file = forms.FileField(label="Загрузить HTML страницы по ссылке", required=False)

    class Meta:
        model = EmailTemplate
        fields = ("name", "category", "tags", "sender", "subject", "email_file", "html_body", "page_file", "landing_html", "text_body", "description", "status")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Например, Приглашение на обучение"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.TextInput(attrs={"class": "form-control", "placeholder": "обучение, безопасность, внутренние коммуникации"}),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "html_body": forms.Textarea(attrs={"class": "form-control code-area", "rows": 14, "spellcheck": "false"}),
            "text_body": forms.Textarea(attrs={"class": "form-control", "rows": 10}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }
        help_texts = {
            "html_body": "Разрешённый HTML будет очищен при предварительном просмотре. Скрипты и обработчики событий не выполняются.",
            "text_body": "Текстовая альтернатива для почтовых клиентов без HTML.",
            "tags": "Несколько тегов разделяйте запятыми.",
        }

    def clean_tags(self):
        raw = self.cleaned_data.get("tags", "")
        tags = []
        seen = set()
        for item in raw.split(","):
            tag = " ".join(item.split())
            key = tag.casefold()
            if tag and key not in seen:
                tags.append(tag)
                seen.add(key)
        return ", ".join(tags)

    def clean(self):
        cleaned = super().clean()
        from .import_html import fragment, LIMIT
        self.import_notes = []
        for upload, field in (("email_file", "html_body"), ("page_file", "landing_html")):
            source = cleaned.get(field, "")
            file = cleaned.get(upload)
            if file:
                if file.size > LIMIT:
                    self.add_error(upload, "Файл больше 2 МиБ.")
                    continue
                try:
                    source = file.read().decode("utf-8-sig")
                except UnicodeError:
                    self.add_error(upload, "Сохраните HTML в UTF-8.")
                    continue
            if source:
                try:
                    cleaned[field], removed = fragment(source)
                except forms.ValidationError as exc:
                    self.add_error(field, exc)
                    continue
                if file and not cleaned[field].strip():
                    self.add_error(upload, "После очистки документ пуст.")
                if removed:
                    details = ", ".join(f"{k} ({v})" for k, v in sorted(removed.items()))
                    self.import_notes.append(f"{self.fields[field].label} — удалены {details}.")
        if not cleaned.get("html_body", "").strip() and not cleaned.get("text_body", "").strip():
            raise forms.ValidationError("Заполните хотя бы одну версию письма: HTML или текстовую.")
        return cleaned
