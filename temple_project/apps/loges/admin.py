from django.contrib import admin
from .models import Obedience, Loge


@admin.register(Obedience)
class ObedienceAdmin(admin.ModelAdmin):
    list_display = ["nom"]
    search_fields = ["nom"]


@admin.register(Loge)
class LogeAdmin(admin.ModelAdmin):
    list_display = ["abreviation", "nom", "obedience", "type_loge", "effectif_total", "actif"]
    list_filter = ["obedience", "type_loge", "actif"]
    search_fields = ["nom", "abreviation"]
