from django.urls import path
from . import views

urlpatterns = [
    path("<int:template_id>/material/", views.training_material, name="training_material"),
    path("<int:template_id>/test/", views.send_preview, name="template_test"),
    path("", views.template_list, name="email_template_list"),
    path("new/", views.template_create, name="email_template_create"),
    path("<int:template_id>/", views.template_detail, name="email_template_detail"),
    path("<int:template_id>/edit/", views.template_edit, name="email_template_edit"),
    path("<int:template_id>/delete/", views.template_delete, name="email_template_delete"),
    path("<int:template_id>/preview/", views.template_preview, name="email_template_preview"),
]
