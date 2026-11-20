from django.urls import path
from . import views

urlpatterns = [
    path("", views.employee_list, name="employee_list"),
    path("new/", views.employee_create, name="employee_create"),
    path("import/", views.csv_import, name="employee_csv_import"),
    path("<int:employee_id>/", views.employee_detail, name="employee_detail"),
    path("<int:employee_id>/edit/", views.employee_edit, name="employee_edit"),
]
