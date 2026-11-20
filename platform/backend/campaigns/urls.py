from django.urls import path
from . import views

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("new/", views.campaign_create, name="campaign_create"),
    path("<uuid:campaign_id>/start/", views.campaign_start, name="campaign_start"),
    path("mail/", views.mail_diagnostics, name="mail_diagnostics"),
    path("mail/check/", views.mail_check_connection, name="mail_check_connection"),
    path("mail/test-message/", views.mail_send_test, name="mail_send_test"),
    path("<uuid:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("<uuid:campaign_id>/edit/", views.campaign_edit, name="campaign_edit"),
    path("<uuid:campaign_id>/export.csv", views.campaign_export_csv, name="campaign_export_csv"),
    path("<uuid:campaign_id>/links/create/", views.create_training_links, name="create_training_links"),
    path("<uuid:campaign_id>/links/<int:participant_id>/revoke/", views.revoke_training_link, name="revoke_training_link"),
    path("event/<uuid:campaign_id>/<str:kind>/", views.record_safe_event, name="record_safe_event"),
]
