from django.test import TestCase
from django.contrib.auth.models import User
from .management.commands.import_ecode import Command


class OfflineRosterTests(TestCase):
    def test_pin_login_and_revocation(self):
        row = dict(enrollmentNumber="TEST-01", username="fixture-user", fullName="Test Student",
                   batchYear="2026", contestPin="001234")
        Command().refresh([row])
        user = User.objects.get(username=row["username"])
        self.assertNotEqual(user.password,row["contestPin"])
        self.assertEqual(self.client.post("/api/login", {"enrollment":"TEST-01","pin":"wrong"}).status_code,401)
        self.assertEqual(self.client.post("/api/login", {"enrollment":"TEST-01","pin":"001234"}).status_code,200)
        self.assertEqual(self.client.get("/api/session").json()["details"]["batch"], "2026")
        self.assertEqual(self.client.get("/api/organizer/roster").status_code,403)
        Command().refresh([])
        self.assertEqual(self.client.post("/api/login", {"enrollment":"TEST-01","pin":"001234"}).status_code,401)
