from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings


def membre_required(view_func):
    """Decorateur : autorise les membres (cookie) ET les admins (is_staff)."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        est_admin  = request.user.is_authenticated and request.user.is_staff
        est_membre = request.COOKIES.get("kellermann_membre") == "1"
        if est_admin or est_membre:
            return view_func(request, *args, **kwargs)
        return __import__("django.shortcuts", fromlist=["redirect"]).redirect(f"/auth/login/?next={request.path}")
    return wrapper


def bienvenue(request):
    return render(request, "auth/bienvenue.html")


def login_visiteur(request):
    if request.COOKIES.get("kellermann_membre") == "1":
        return redirect("/calendrier/")

    if request.method == "POST":
        mdp_saisi   = request.POST.get("mot_de_passe", "").strip().upper()
        try:
            from temple_project.apps.administration.models import Parametres
            params = Parametres.objects.first()
            mdp_annuel = params.mot_de_passe_annuel.upper() if params else getattr(settings, "MOT_DE_PASSE_ANNUEL", "KELLERMANN2026").upper()
        except Exception:
            mdp_annuel = getattr(settings, "MOT_DE_PASSE_ANNUEL", "KELLERMANN2026").upper()

        if mdp_saisi == mdp_annuel:
            next_url = request.GET.get("next", "/calendrier/")
            response = redirect(next_url)
            # Cookie valable 7 jours
            response.set_cookie(
                "kellermann_membre", "1",
                max_age=86400 * 7,
                httponly=True,
                samesite="Lax"
            )
            return response

        messages.error(request, "Code d'accès incorrect.")

    return render(request, "auth/login_visiteur.html")


def login_admin(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("/admin/")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", ""),
            password=request.POST.get("password", "")
        )
        if user and user.is_staff:
            login(request, user)
            return redirect(request.GET.get("next", "/admin/"))
        messages.error(request, "Identifiants incorrects ou accès non autorisé.")

    return render(request, "auth/login_admin.html")


def deconnexion(request):
    logout(request)
    response = redirect("/")
    response.delete_cookie("kellermann_membre")
    return response


def visiteur_context(request):
    """Context processor — rend visiteur_connecte disponible dans tous les templates."""
    return {
        "visiteur_connecte": request.COOKIES.get("kellermann_membre") == "1"
    }
