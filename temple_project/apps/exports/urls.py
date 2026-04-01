from django.urls import path
from . import views

app_name = "exports"

urlpatterns = [
    path("csv/", views.export_csv, name="csv"),
    path("excel/", views.export_excel, name="excel"),
    path("reporting/", views.reporting, name="reporting"),
]
