
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.prelaunch.models import (
    PharmacyPreRegistration,
    WaitlistEntry,
)


User = get_user_model()


class PrelaunchDashboardSecurityTests(APITestCase):
    """
    Tests de sécurité et de fonctionnement du dashboard
    administrateur TeriMedi.
    """

    def setUp(self):
        self.url = reverse("prelaunch_admin:dashboard")

        # Le modèle utilisateur TeriMedi utilise un téléphone.
        # On crée les utilisateurs avec les champs essentiels
        # afin de rester compatible avec le CustomUser.
        self.normal_user = User.objects.create_user(
            phone_number="+2250700000011",
            password="TestPassword123!",
        )

        self.staff_user = User.objects.create_user(
            phone_number="+2250700000012",
            password="TestPassword123!",
        )
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])

        self.admin_user = User.objects.create_superuser(
            phone_number="+2250700000013",
            password="TestPassword123!",
        )

    def authenticate(self, user):
        """
        Authentification avec un véritable access token JWT.
        """
        token = AccessToken.for_user(user)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(token)}"
        )

    def test_anonymous_user_cannot_access_dashboard(self):
        """
        Un visiteur non connecté doit recevoir 401.
        """
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_invalid_jwt_is_rejected(self):
        """
        Un jeton invalide doit être rejeté.
        """
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer invalid-token"
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_normal_user_cannot_access_dashboard(self):
        """
        Un utilisateur ordinaire doit recevoir 403.
        """
        self.authenticate(self.normal_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_cannot_access_dashboard(self):
        """
        is_staff=True ne doit pas suffire.
        """
        self.authenticate(self.staff_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_superuser_can_access_dashboard(self):
        """
        Un superutilisateur actif doit pouvoir consulter
        les statistiques.
        """
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("patients", response.data)
        self.assertIn("pharmacies", response.data)

    def test_dashboard_returns_zero_when_database_empty(self):
        """
        Les statistiques doivent fonctionner
        même sans préinscriptions.
        """
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["patients"]["total"],
            0,
        )

        self.assertEqual(
            response.data["patients"]["verified"],
            0,
        )

        self.assertEqual(
            response.data["patients"]["verification_rate"],
            0,
        )

        self.assertEqual(
            response.data["pharmacies"]["total"],
            0,
        )

        self.assertEqual(
            response.data["pharmacies"]["approved"],
            0,
        )

    def test_dashboard_statistics_are_correct(self):
        """
        Les compteurs doivent refléter les enregistrements
        réellement présents en base.
        """

        # Deux patients préinscrits.
        patient_1 = WaitlistEntry.objects.create(
            phone="+2250700000021",
            first_name="Patient Test 1",
            commune="Cocody",
            status=WaitlistEntry.Status.PENDING,
            consent_at=timezone.now(),
        )

        patient_2 = WaitlistEntry.objects.create(
            phone="+2250700000022",
            first_name="Patient Test 2",
            commune="Cocody",
            status=WaitlistEntry.Status.VERIFIED,
            consent_at=timezone.now(),
        )

        # Deux pharmacies candidates.
        pharmacy_1 = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie Test 1",
            commune="Cocody",
            address="Riviera 2",
            contact_name="Responsable 1",
            phone="+2250700000031",
            status=PharmacyPreRegistration.Status.NEW,
            consent_at=timezone.now(),
        )

        pharmacy_2 = PharmacyPreRegistration.objects.create(
            pharmacy_name="Pharmacie Test 2",
            commune="Marcory",
            address="Zone 4",
            contact_name="Responsable 2",
            phone="+2250700000032",
            status=PharmacyPreRegistration.Status.APPROVED,
            consent_at=timezone.now(),
        )

        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Patients
        self.assertEqual(
            response.data["patients"]["total"],
            2,
        )

        self.assertEqual(
            response.data["patients"]["verified"],
            1,
        )

        self.assertEqual(
            response.data["patients"]["pending"],
            1,
        )

        self.assertEqual(
            response.data["patients"]["verification_rate"],
            50.0,
        )

        # Pharmacies
        self.assertEqual(
            response.data["pharmacies"]["total"],
            2,
        )

        self.assertEqual(
            response.data["pharmacies"]["new"],
            1,
        )

        self.assertEqual(
            response.data["pharmacies"]["approved"],
            1,
        )

        # Vérification des données en base
        self.assertTrue(
            WaitlistEntry.objects.filter(
                pk=patient_1.pk
            ).exists()
        )

        self.assertTrue(
            WaitlistEntry.objects.filter(
                pk=patient_2.pk
            ).exists()
        )

        self.assertTrue(
            PharmacyPreRegistration.objects.filter(
                pk=pharmacy_1.pk
            ).exists()
        )

        self.assertTrue(
            PharmacyPreRegistration.objects.filter(
                pk=pharmacy_2.pk
            ).exists()
        )

    def test_inactive_superuser_cannot_access_dashboard(self):
        """
        Un superutilisateur désactivé ne doit pas
        accéder au dashboard, même avec un JWT.
        """
        self.admin_user.is_active = False
        self.admin_user.save(update_fields=["is_active"])

        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_dashboard_does_not_expose_personal_data(self):
        """
        Le dashboard statistique ne doit pas
        exposer les coordonnées des inscrits.
        """
        self.authenticate(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            set(response.data.keys()),
            {"patients", "pharmacies"},
        )

        self.assertNotIn(
            "phone",
            str(response.data).lower(),
        )

        self.assertNotIn(
            "email",
            str(response.data).lower(),
        )

        self.assertNotIn(
            "contact_name",
            str(response.data).lower(),
        )

    def test_admin_session_rejects_anonymous_user(self):
        url = reverse("prelaunch_admin:admin-session")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)


    def test_admin_session_rejects_normal_user(self):
        url = reverse("prelaunch_admin:admin-session")

        self.authenticate(self.normal_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)


    def test_admin_session_accepts_superuser(self):
        url = reverse("prelaunch_admin:admin-session")

        self.authenticate(self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_admin"])
        self.assertEqual(
            response.data["id"],
            str(self.admin_user.pk),
        )


    def test_admin_session_rejects_inactive_superuser(self):
        url = reverse("prelaunch_admin:admin-session")

        self.admin_user.is_active = False
        self.admin_user.save(update_fields=["is_active"])

        self.authenticate(self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)
