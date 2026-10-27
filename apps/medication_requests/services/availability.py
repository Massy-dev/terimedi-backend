
from uuid import UUID

from ..models import PharmacyAssignment


class AvailabilityService:
    """
    Validation des disponibilités par médicament.

    Le résultat est une liste normalisée :
    [
        {"item_id": "<uuid>", "quantity": 2},
        ...
    ]

    Les médicaments absents de la proposition ont
    une quantité disponible égale à zéro.
    """

    @classmethod
    def validate(
        cls,
        *,
        medication_request,
        response,
        quantities,
    ):
        if not isinstance(quantities, list):
            raise ValueError(
                "Les disponibilités doivent être une liste."
            )

        items = list(
            medication_request.items.all()
        )

        if not items:
            raise ValueError(
                "Cette demande ne contient pas de médicaments structurés."
            )

        requested = {
            str(item.id): item
            for item in items
        }

        available = {}
        seen = set()

        for entry in quantities:
            if not isinstance(entry, dict):
                raise ValueError(
                    "Chaque disponibilité doit être un objet."
                )

            if set(entry.keys()) != {"item_id", "quantity"}:
                raise ValueError(
                    "Chaque disponibilité doit contenir "
                    "uniquement item_id et quantity."
                )

            raw_id = entry["item_id"]

            try:
                item_id = str(UUID(str(raw_id)))
            except (ValueError, TypeError, AttributeError):
                raise ValueError(
                    "Identifiant de médicament invalide."
                ) from None

            if item_id not in requested:
                raise ValueError(
                    "Un médicament ne fait pas partie de cette demande."
                )

            if item_id in seen:
                raise ValueError(
                    "Un médicament est présent plusieurs fois."
                )

            seen.add(item_id)

            quantity = entry["quantity"]

            if type(quantity) is not int:
                raise ValueError(
                    "La quantité disponible doit être un entier."
                )

            if quantity < 0:
                raise ValueError(
                    "La quantité disponible ne peut pas être négative."
                )

            if quantity > requested[item_id].quantity:
                raise ValueError(
                    "La quantité disponible ne peut pas dépasser "
                    "la quantité demandée."
                )

            available[item_id] = quantity

        normalized = [
            {
                "item_id": str(item.id),
                "quantity": available.get(str(item.id), 0),
            }
            for item in items
        ]

        total_available = sum(
            entry["quantity"]
            for entry in normalized
        )

        is_complete = all(
            available.get(str(item.id), 0) == item.quantity
            for item in items
        )

        if response == PharmacyAssignment.Status.ACCEPTED:
            if not is_complete:
                raise ValueError(
                    "Une réponse Disponible exige toutes "
                    "les quantités demandées."
                )

        elif response == PharmacyAssignment.Status.PARTIAL:
            if total_available == 0 or is_complete:
                raise ValueError(
                    "Une réponse partielle exige au moins "
                    "un médicament disponible, sans couvrir "
                    "la totalité de la demande."
                )

        elif response == PharmacyAssignment.Status.REJECTED:
            if total_available != 0:
                raise ValueError(
                    "Une réponse Indisponible ne peut pas "
                    "contenir de quantités disponibles."
                )

        else:
            raise ValueError(
                "Réponse de pharmacie invalide."
            )

        return normalized
