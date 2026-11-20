from django.contrib import admin
from .models import EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "created_by", "updated_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("name", "subject", "tags", "description")
    readonly_fields = ("created_by", "created_at", "updated_at")
    fieldsets = (
        ("Основное", {"fields": ("name", "category", "tags", "status", "description")}),
        ("Содержимое", {"fields": ("subject", "html_body", "text_body")}),
        ("Аудит", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

from .models import SenderAddress, SenderDomain

admin.site.register(SenderAddress)
admin.site.register(SenderDomain)
