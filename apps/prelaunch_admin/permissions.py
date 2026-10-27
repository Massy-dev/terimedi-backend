
from rest_framework.permissions import BasePermission


class IsPrelaunchAdmin(BasePermission):
    """
    Accès réservé aux utilisateurs Django actifs
    possédant le statut superuser.

    Le compte superuser est le seul rôle autorisé
    pendant cette première phase.
    """

    message = "Accès réservé à l'administration TeriMedi."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
        )
