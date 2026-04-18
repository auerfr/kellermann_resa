from django.urls import path
from . import views

app_name = "exports"

urlpatterns = [
    path("csv/", views.export_csv, name="csv"),
    path("excel/", views.export_excel, name="excel"),
    path("reporting/", views.reporting, name="reporting"),
    path("planning/pdf/", views.planning_pdf, name="planning_pdf"),
    path("portail/<str:token>/planning.pdf", views.planning_loge_pdf, name="planning_loge_pdf"),
]
