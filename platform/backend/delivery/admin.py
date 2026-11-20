from django.contrib import admin
from .models import SimulationDomain, CampaignDispatch, DeliveryRecord, DispatchAudit, DispatchThrottle


@admin.register(SimulationDomain)
class SimulationDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "sandbox_only", "active")
    exclude = ("verification_code", "verified_at")
    readonly_fields = ("domain", "sandbox_only", "created_by", "created_at")
    def has_add_permission(self, request):
        return False  # Use controlled verification UI
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CampaignDispatch)
class CampaignDispatchAdmin(admin.ModelAdmin):
    list_display = ("campaign", "domain", "state", "created_at", "finished_at")
    readonly_fields = [f.name for f in CampaignDispatch._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ("dispatch", "recipient_email", "status", "smtp_accepted_at", "error_code")
    readonly_fields = [f.name for f in DeliveryRecord._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(DispatchAudit)
class DispatchAuditAdmin(admin.ModelAdmin):
    list_display = ("dispatch", "action", "actor", "created_at")
    readonly_fields = [f.name for f in DispatchAudit._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
