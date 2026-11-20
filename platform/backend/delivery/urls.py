from django.urls import path
from . import views

urlpatterns = [
    path("domains/", views.domains, name="delivery_domains"),
    path("domains/new/", views.domain_create, name="delivery_domain_create"),
    path("domains/<int:pk>/verify/", views.domain_verify, name="delivery_domain_verify"),
    path("campaign/<uuid:campaign_id>/", views.dispatch_detail, name="delivery_dispatch"),
    path("campaign/<uuid:campaign_id>/stop/", views.dispatch_stop, name="delivery_dispatch_stop"),
]
