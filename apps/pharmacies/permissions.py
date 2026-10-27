from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsPharmacyStaff(BasePermission):
    message = "Pharmacy staff access required."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.role == User.Role.PHARMACY_STAFF
        )