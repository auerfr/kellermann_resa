from django.shortcuts import redirect

URLS_PUBLIQUES = ["/auth/", "/static/", "/media/", "/django-admin/"]


class AuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if any(path.startswith(u) for u in URLS_PUBLIQUES):
            return self.get_response(request)

        if path == "/":
            return self.get_response(request)

        if path.startswith("/admin/"):
            if request.user.is_authenticated and request.user.is_staff:
                return self.get_response(request)
            return redirect(f"/auth/admin/?next={path}")

        if path.startswith("/traiteur/"):
            # Les pages notification sont accessibles à tous les membres
            TRAITEUR_PUBLIC = ["/traiteur/notification/", "/traiteur/notification/confirmation/"]
            est_membre   = request.COOKIES.get("kellermann_membre") == "1"
            est_traiteur = (
                request.user.is_authenticated
                and (
                    request.user.is_staff
                    or request.user.groups.filter(name="Traiteur").exists()
                )
            )
            if est_traiteur:
                return self.get_response(request)
            if any(path.startswith(u) for u in TRAITEUR_PUBLIC) and (est_membre or est_traiteur):
                return self.get_response(request)
            if any(path.startswith(u) for u in TRAITEUR_PUBLIC):
                return redirect(f"/auth/login/?next={path}")
            return redirect(f"/auth/traiteur/?next={path}")

        est_admin  = request.user.is_authenticated and request.user.is_staff
        est_membre = request.COOKIES.get("kellermann_membre") == "1"

        if est_admin or est_membre:
            return self.get_response(request)

        return redirect(f"/auth/login/?next={path}")
