
import shutil
import tempfile

from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.pharmacies.models import Pharmacy


class PharmacyAdminDocumentSecurityTests(TransactionTestCase):
    def setUp(self):
        self.media_directory = tempfile.mkdtemp()

        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory,
        )
        self.media_override.enable()

        self.addCleanup(self.media_override.disable)
        self.addCleanup(
            shutil.rmtree,
            self.media_directory,
            ignore_errors=True,
        )

        self.admin_user = User.objects.create_user(
            phone_number="+2250701010101",
            password="StrongPassword123!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )
        self.admin_user.is_staff = True
        self.admin_user.is_superuser = True
        self.admin_user.save(
            update_fields=["is_staff", "is_superuser"]
        )

        self.unauthorized_user = User.objects.create_user(
            phone_number="+2250702020202",
            password="StrongPassword123!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )
        self.unauthorized_user.is_staff = True
        self.unauthorized_user.save(
            update_fields=["is_staff"]
        )

        self.authorized_staff = User.objects.create_user(
            phone_number="+2250703030303",
            password="StrongPassword123!",
            role=User.Role.PATIENT,
            is_phone_verified=True,
        )
        self.authorized_staff.is_staff = True
        self.authorized_staff.save(
            update_fields=["is_staff"]
        )

        permission = Permission.objects.get(
            content_type__app_label="pharmacies",
            codename="view_pharmacy",
        )
        self.authorized_staff.user_permissions.add(
            permission
        )

        self.pharmacy = Pharmacy.objects.create(
            name="Pharmacie Sécurité Test",
            phone_number="+2250704040404",
            address="Cocody, Abidjan",
            commune="Cocody",
            location=Point(
                -3.9670,
                5.3890,
                srid=4326,
            ),
            status=Pharmacy.Status.PENDING,
            is_active=True,
        )

        self.pharmacy.verification_document.save(
            "justificatif.pdf",
            ContentFile(
                b"private pharmacy verification document"
            ),
            save=True,
        )

        self.url = reverse(
            "admin:pharmacies_pharmacy_verification_document",
            args=[self.pharmacy.pk],
        )

    def test_superuser_can_view_document(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )
        
        cache_control = response["Cache-Control"]
        self.assertIn("private", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("max-age=0", cache_control)

        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

        content = b"".join(response.streaming_content)
        response.close()
        self.assertEqual(
            content,
            b"private pharmacy verification document",
        )

    def test_staff_with_view_permission_can_view_document(self):
        self.client.force_login(self.authorized_staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        response.close()

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/admin/login/",
            response["Location"],
        )

    def test_staff_without_permission_is_denied(self):
        self.client.force_login(
            self.unauthorized_user
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_nonexistent_pharmacy_returns_404(self):
        self.client.force_login(self.admin_user)

        url = reverse(
            "admin:pharmacies_pharmacy_verification_document",
            args=["00000000-0000-0000-0000-000000000001"],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_pharmacy_without_document_returns_404(self):
        self.client.force_login(self.admin_user)

        self.pharmacy.verification_document.delete(
            save=True
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_public_media_url_is_not_served_by_django(self):
        self.client.logout()

        response = self.client.get(
            "/media/pharmacies/verification/test.pdf"
        )

        self.assertEqual(response.status_code, 404)
