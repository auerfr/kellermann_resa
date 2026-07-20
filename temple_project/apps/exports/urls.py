from django.urls import path
from . import views

app_name = "exports"

urlpatterns = [
    path("csv/", views.export_csv, name="csv"),
    path("excel/", views.export_excel, name="excel"),
    path("reporting/", views.reporting, name="reporting"),
    path("statistiques/export/", views.statistiques_export, name="statistiques_export"),
    path("planning/pdf/", views.planning_pdf, name="planning_pdf"),
    path("planning/grille-mensuelle/", views.planning_pdf_grille_mensuelle, name="planning_pdf_grille_mensuelle"),
    path("planning/annuel-a3/", views.planning_pdf_annuel_a3, name="planning_pdf_annuel_a3"),
    path("planning/annuel-a4/", views.planning_pdf_annuel_a4, name="planning_pdf_annuel_a4"),
    path("portail/<str:token>/planning.pdf", views.planning_loge_pdf, name="planning_loge_pdf"),
    path("portail/<str:token>/grille.pdf", views.planning_loge_grille_pdf, name="planning_loge_grille_pdf"),
    path("portail/<str:token>/annuel.pdf", views.planning_loge_annuel_pdf, name="planning_loge_annuel_pdf"),
    path("bilan-saison/", views.bilan_saison_excel, name="bilan_saison"),
]
