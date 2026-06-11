from django.urls import path
from . import views

app_name = "loges"

urlpatterns = [
    path("",                    views.liste_loges,   name="liste"),
    path("<int:pk>/",           views.detail_loge,   name="detail"),
    path("<int:pk>/modifier/",  views.modifier_loge, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer_loge, name="supprimer"),
]
