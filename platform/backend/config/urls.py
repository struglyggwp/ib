from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from core import views
from campaigns.views import training_visit
from campaigns.open_tracking import email_open_pixel

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("campaigns/", include("campaigns.urls")),
    path("learn/<uuid:token>/", training_visit, name="training_visit"),
    path("track/open/<uuid:token>.gif", email_open_pixel, name="email_open_pixel"),
    path("employees/", include("employees.urls")),
    path("templates/", include("email_templates.urls")),
    path("scenarios/", RedirectView.as_view(pattern_name="campaign_list", permanent=False)),
    path("scenarios/<path:legacy>/", RedirectView.as_view(pattern_name="campaign_list", permanent=False)),
    path("delivery/", include("delivery.urls")),
]
