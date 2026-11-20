from django.contrib import admin
from .models import Campaign, SafeEvent, CampaignParticipant

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "starts_at", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at", "scenario", "scenario_version")
    fieldsets = (
        ("Основное", {"fields": ("name", "description", "status")}),
        ("Планирование", {"fields": ("starts_at", "email_template", "scenario", "scenario_version")}),
        ("Аудит", {"fields": ("id", "created_by", "created_at", "updated_at")}),
    )
    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(SafeEvent)
class SafeEventAdmin(admin.ModelAdmin):
    list_display = ("campaign", "kind", "source", "confidence", "occurred_at")
    list_filter = ("kind", "source", "occurred_at")
    readonly_fields = [f.name for f in SafeEvent._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


@admin.register(CampaignParticipant)
class CampaignParticipantAdmin(admin.ModelAdmin):
    list_display = ("campaign", "employee", "added_at")
    list_filter = ("campaign",)
    search_fields = ("employee__email", "employee__last_name")
    readonly_fields = ("campaign", "employee", "added_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


from .models import TrainingLink, ParticipantEvent

@admin.register(TrainingLink)
class TrainingLinkAdmin(admin.ModelAdmin):
    list_display = ("participant", "created_at", "expires_at", "revoked")
    list_filter = ("revoked",)
    readonly_fields = [f.name for f in TrainingLink._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(ParticipantEvent)
class ParticipantEventAdmin(admin.ModelAdmin):
    list_display = ("participant", "kind", "occurred_at")
    list_filter = ("kind",)
    readonly_fields = [f.name for f in ParticipantEvent._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
