from uuid import UUID
from apps.notifications.events import queue_user_notification
from django.db import transaction
from django.utils import timezone

from apps.pharmacies.models import Pharmacy

from ..models import (
    MedicationRequest,
    MedicationRequestItem,
    PharmacyAssignment,
    PharmacyQuote,
    PharmacyQuoteItem,
)
from .availability import AvailabilityService
from .matching import MatchingService


class QuoteService:
    """
    Gestion des devis TeriMedi.

    Les montants sont exprimés en FCFA.

    Une décision du patient concerne simultanément :
    - les médicaments proposés ;
    - les quantités disponibles ;
    - les prix proposés.
    """

    MAX_QUOTE_ITEMS = 20
    MAX_AMOUNT = 9_223_372_036_854_775_807

    @staticmethod
    def _positive_integer(
        value,
        field_name,
        allow_zero=False,
    ):
        if type(value) is not int:
            raise ValueError(
                f"{field_name} doit être un entier."
            )

        if value < 0 or (
            value == 0 and not allow_zero
        ):
            raise ValueError(
                f"{field_name} doit être positif."
            )

        return value

    @classmethod
    def _validate_amount(cls, amount):
        if amount > cls.MAX_AMOUNT:
            raise ValueError(
                "Le montant du devis dépasse "
                "la limite autorisée."
            )

        return amount

    @classmethod
    @transaction.atomic
    def create_quote(
        cls,
        *,
        assignment_id,
        pharmacy_user,
        response,
        items,
        note="",
        available_items="",
    ):
        """
        Crée un devis pour une attribution pharmacie.

        Format pour une demande structurée :

        [
            {
                "item_id": "<uuid>",
                "quantity": 2,
                "unit_price": 1500
            }
        ]

        Format pour une demande historique :

        [
            {
                "name": "Paracétamol",
                "dosage": "500 mg",
                "unit": "BOX",
                "quantity": 2,
                "unit_price": 1500
            }
        ]
        """

        assignment = (
            PharmacyAssignment.objects
            .select_related(
                "medication_request",
                "pharmacy",
            )
            .filter(id=assignment_id)
            .first()
        )

        if assignment is None:
            raise ValueError(
                "Attribution introuvable."
            )

        medication_request = (
            MedicationRequest.objects
            .select_for_update()
            .get(
                id=assignment.medication_request_id
            )
        )

        assignment = (
            PharmacyAssignment.objects
            .select_for_update()
            .select_related("pharmacy")
            .get(id=assignment_id)
        )

        pharmacy = assignment.pharmacy

        if not pharmacy.memberships.filter(
            user=pharmacy_user,
            is_active=True,
        ).exists():
            raise ValueError(
                "Vous n'êtes pas autorisé à répondre "
                "pour cette pharmacie."
            )

        if not (
            pharmacy.is_active
            and pharmacy.status == Pharmacy.Status.APPROVED
        ):
            raise ValueError(
                "Cette pharmacie n'est pas autorisée."
            )

        if not medication_request.quote_requested:
            raise ValueError(
                "Cette demande ne nécessite pas de devis."
            )

        if (
            medication_request.status
            != MedicationRequest.Status.MATCHING
        ):
            raise ValueError(
                "Cette demande n'attend plus "
                "de réponse de pharmacie."
            )

        if (
            assignment.status
            != PharmacyAssignment.Status.PENDING
        ):
            raise ValueError(
                "Cette attribution a déjà reçu "
                "une réponse."
            )

        if (
            assignment.expires_at is not None
            and timezone.now() >= assignment.expires_at
        ):
            raise ValueError(
                "Le délai de réponse de la pharmacie "
                "a expiré."
            )

        if response not in (
            PharmacyAssignment.Status.ACCEPTED,
            PharmacyAssignment.Status.PARTIAL,
        ):
            raise ValueError(
                "Un devis nécessite une disponibilité "
                "totale ou partielle."
            )

        if not isinstance(note, str):
            raise ValueError(
                "La note du devis est invalide."
            )

        if not isinstance(available_items, str):
            raise ValueError(
                "La description des disponibilités "
                "est invalide."
            )

        if not isinstance(items, list) or not items:
            raise ValueError(
                "Le devis doit contenir "
                "au moins un médicament."
            )

        if len(items) > cls.MAX_QUOTE_ITEMS:
            raise ValueError(
                "Le devis ne peut pas dépasser "
                f"{cls.MAX_QUOTE_ITEMS} lignes."
            )

        if PharmacyQuote.objects.filter(
            assignment=assignment
        ).exists():
            raise ValueError(
                "Un devis existe déjà "
                "pour cette attribution."
            )

        request_items = list(
            medication_request.items.all()
        )

        quote_lines = []
        normalized_quantities = []

        if request_items:
            # Demande structurée : les lignes du devis
            # correspondent aux médicaments demandés.

            requested_by_id = {
                str(item.id): item
                for item in request_items
            }

            quantities = []
            prices = {}
            seen_ids = set()

            for entry in items:
                if not isinstance(entry, dict):
                    raise ValueError(
                        "Chaque ligne du devis "
                        "doit être un objet."
                    )

                if set(entry.keys()) != {
                    "item_id",
                    "quantity",
                    "unit_price",
                }:
                    raise ValueError(
                        "Une ligne structurée doit contenir "
                        "uniquement item_id, quantity "
                        "et unit_price."
                    )

                try:
                    item_id = str(
                        UUID(str(entry["item_id"]))
                    )
                except (
                    ValueError,
                    TypeError,
                    AttributeError,
                ):
                    raise ValueError(
                        "Identifiant de médicament invalide."
                    ) from None

                if item_id not in requested_by_id:
                    raise ValueError(
                        "Un médicament ne fait pas partie "
                        "de cette demande."
                    )

                if item_id in seen_ids:
                    raise ValueError(
                        "Un médicament est présent "
                        "plusieurs fois dans le devis."
                    )

                seen_ids.add(item_id)

                quantity = cls._positive_integer(
                    entry["quantity"],
                    "quantity",
                    allow_zero=True,
                )

                unit_price = cls._positive_integer(
                    entry["unit_price"],
                    "unit_price",
                )

                quantities.append({
                    "item_id": item_id,
                    "quantity": quantity,
                })

                prices[item_id] = unit_price

            normalized_quantities = (
                AvailabilityService.validate(
                    medication_request=medication_request,
                    response=response,
                    quantities=quantities,
                )
            )

            for entry in normalized_quantities:
                quantity = entry["quantity"]

                if quantity == 0:
                    continue

                item_id = entry["item_id"]
                medication_item = requested_by_id[item_id]
                unit_price = prices[item_id]

                subtotal = cls._validate_amount(
                    quantity * unit_price
                )

                quote_lines.append({
                    "medication_item": medication_item,
                    "name": medication_item.name,
                    "dosage": medication_item.dosage,
                    "unit": medication_item.unit,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                })

        else:
            # Demande historique :
            # ordonnance, photo ou texte libre.
            #
            # La pharmacie renseigne les médicaments
            # identifiés et leurs prix.
            #
            # La couverture complète de la demande
            # ne peut pas être déterminée
            # automatiquement.

            valid_units = {
                choice.value
                for choice in MedicationRequestItem.Unit
            }

            for entry in items:
                if not isinstance(entry, dict):
                    raise ValueError(
                        "Chaque ligne du devis "
                        "doit être un objet."
                    )

                required_fields = {
                    "name",
                    "quantity",
                    "unit_price",
                }

                allowed_fields = {
                    "name",
                    "dosage",
                    "unit",
                    "quantity",
                    "unit_price",
                }

                if not required_fields.issubset(
                    entry.keys()
                ):
                    raise ValueError(
                        "Une ligne doit contenir "
                        "name, quantity et unit_price."
                    )

                if set(entry.keys()) - allowed_fields:
                    raise ValueError(
                        "Une ligne contient "
                        "des champs inconnus."
                    )

                name = entry["name"]
                dosage = entry.get("dosage", "")
                unit = entry.get(
                    "unit",
                    MedicationRequestItem.Unit.BOX,
                )

                if (
                    not isinstance(name, str)
                    or not name.strip()
                    or len(name) > 255
                ):
                    raise ValueError(
                        "Le nom du médicament est invalide."
                    )

                if (
                    not isinstance(dosage, str)
                    or len(dosage) > 100
                ):
                    raise ValueError(
                        "Le dosage est invalide."
                    )

                if unit not in valid_units:
                    raise ValueError(
                        "L'unité du médicament est invalide."
                    )

                quantity = cls._positive_integer(
                    entry["quantity"],
                    "quantity",
                    allow_zero=True,
                )

                unit_price = cls._positive_integer(
                    entry["unit_price"],
                    "unit_price",
                )

                subtotal = cls._validate_amount(
                    quantity * unit_price
                )

                quote_lines.append({
                    "medication_item": None,
                    "name": name.strip(),
                    "dosage": dosage,
                    "unit": unit,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                })

        if not quote_lines:
            raise ValueError(
                "Le devis doit contenir au moins "
                "un médicament disponible."
            )

        total_amount = cls._validate_amount(
            sum(
                line["subtotal"]
                for line in quote_lines
            )
        )

        if total_amount <= 0:
            raise ValueError(
                "Le montant total du devis "
                "doit être supérieur à zéro."
            )

        now = timezone.now()

        quote = PharmacyQuote.objects.create(
            assignment=assignment,
            status=PharmacyQuote.Status.PROPOSED,
            total_amount=total_amount,
            note=note,
            proposed_at=now,
        )

        PharmacyQuoteItem.objects.bulk_create([
            PharmacyQuoteItem(
                quote=quote,
                position=index,
                **line,
            )
            for index, line in enumerate(quote_lines)
        ])

        assignment.status = response
        assignment.responded_at = now
        assignment.response_note = note
        assignment.available_items = available_items
        assignment.available_item_quantities = (
            normalized_quantities
        )

        assignment.save(
            update_fields=[
                "status",
                "responded_at",
                "response_note",
                "available_items",
                "available_item_quantities",
            ]
        )

        medication_request.status = (
            MedicationRequest.Status.QUOTE_PENDING
        )

        medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )
        queue_user_notification(
            user_id=medication_request.patient_id,
            title="Votre devis est disponible",
            body="Une pharmacie a proposé un devis pour votre demande.",
            data={
                "type": "QUOTE_PROPOSED",
                "quote_id": str(quote.id),
                "request_id": str(medication_request.id),
            },
        )
        return quote

    @classmethod
    @transaction.atomic
    def decide(
        cls,
        *,
        medication_request_id,
        patient,
        decision,
    ):
        """
        Décision du patient sur un devis.

        ACCEPT :
            Le devis est accepté.
            La demande passe à PHARMACY_FOUND.

        REJECT :
            Le devis est refusé.
            L'attribution est rejetée.
            Le matching recherche une autre pharmacie.
        """

        if decision not in ("ACCEPT", "REJECT"):
            raise ValueError(
                "La décision doit être "
                "ACCEPT ou REJECT."
            )

        medication_request = (
            MedicationRequest.objects
            .select_for_update()
            .filter(
                id=medication_request_id,
                patient=patient,
            )
            .first()
        )

        if medication_request is None:
            raise ValueError(
                "Demande introuvable."
            )

        if not medication_request.quote_requested:
            raise ValueError(
                "Cette demande ne nécessite "
                "pas de devis."
            )

        if (
            medication_request.status
            != MedicationRequest.Status.QUOTE_PENDING
        ):
            raise ValueError(
                "Cette demande n'attend pas "
                "de décision sur un devis."
            )

        assignment = (
            medication_request.assignments
            .select_for_update()
            .filter(
                status__in=[
                    PharmacyAssignment.Status.ACCEPTED,
                    PharmacyAssignment.Status.PARTIAL,
                ]
            )
            .order_by("-responded_at")
            .first()
        )

        if assignment is None:
            raise ValueError(
                "Aucune proposition de pharmacie "
                "active n'a été trouvée."
            )

        quote = (
            PharmacyQuote.objects
            .select_for_update()
            .filter(assignment=assignment)
            .first()
        )

        if quote is None:
            raise ValueError(
                "Aucun devis trouvé "
                "pour cette attribution."
            )

        if quote.status != PharmacyQuote.Status.PROPOSED:
            raise ValueError(
                "Ce devis a déjà fait l'objet "
                "d'une décision."
            )

        now = timezone.now()

        if decision == "ACCEPT":
            quote.status = PharmacyQuote.Status.ACCEPTED

            medication_request.status = (
                MedicationRequest.Status.PHARMACY_FOUND
            )

        else:
            quote.status = PharmacyQuote.Status.REJECTED

            assignment.status = (
                PharmacyAssignment.Status.REJECTED
            )

            assignment.save(
                update_fields=["status"]
            )

            medication_request.status = (
                MedicationRequest.Status.MATCHING
            )

        quote.decided_at = now

        quote.save(
            update_fields=[
                "status",
                "decided_at",
            ]
        )

        medication_request.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        if decision == "REJECT":
            MatchingService.assign_next_pharmacy(
                medication_request_id=medication_request.id
            )

        return quote
