from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import Contest,Entry,ConnectionEvent

class CandidateAccess(TestCase):
    def setUp(self):
        now=timezone.now()
        self.live=Contest.objects.create(title="Live",starts=now-timedelta(hours=1),ends=now+timedelta(hours=1))
        self.future=Contest.objects.create(title="Next",starts=now+timedelta(hours=1),ends=now+timedelta(hours=2))
        self.admin=get_user_model().objects.create_superuser("organizer",password="organizer-private")
    def test_registration_session_and_roles(self):
        response=self.client.post("/api/signup",{"username":"candidate","password":"contestant-private","full_name":"Sam Doe","enrollment":"A-5","email":"sam@example.test","phone":"+91 1234567890","is_staff":True})
        self.assertEqual(response.status_code,404)
        from .management.commands.import_ecode import Command
        Command().refresh([dict(enrollmentNumber="A-5",username="candidate",fullName="Sam Doe",batchYear="2026",contestPin="123456")])
        self.client.post("/api/login",{"username":"A-5","password":"123456"})
        self.assertFalse(self.client.get("/api/session").json()["staff"])
        self.assertEqual(self.client.get(f"/api/organizer/{self.live.id}").status_code,403)
        self.assertEqual(self.client.post(f"/api/contests/{self.future.id}/enter").status_code,403)
        url=f"/api/contests/{self.live.id}"
        self.assertEqual(self.client.post(url+"/enter",{"agree":True},content_type="application/json").status_code,200)
        self.assertEqual(self.client.post(url+"/heartbeat").status_code,200)
        entry=Entry.objects.get()
        Entry.objects.filter(pk=entry.pk).update(last_seen=timezone.now()-timedelta(minutes=1))
        self.client.post(url+"/heartbeat")
        self.assertEqual(ConnectionEvent.objects.filter(kind="Heartbeat lost").count(),1)
        self.assertEqual(self.client.post("/api/logout").status_code,200)
        self.assertIsNone(self.client.get("/api/session").json()["user"])
        errors=[]
        for name in ("admin","missing-user"):
            response=self.client.post("/api/login",{"username":name,"password":"contestant-private"})
            self.assertEqual(response.status_code,401)
            errors.append(response.json())
        self.assertEqual(*errors)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/api/organizer/{self.live.id}").json()["rows"][0]["name"],"Sam Doe")

    def test_question_import_and_lifecycle(self):
        from pathlib import Path
        from django.conf import settings
        import json
        self.client.force_login(self.admin)
        c=self.future
        c.stage="Draft";c.save()
        url=f"/api/organizer/{c.pk}"
        doc=json.loads((settings.BASE.parent/"frontend/dist/question-example.json").read_text())
        def publish(data):
            return self.client.post(url+"/problems",data,content_type="application/json")
        self.assertEqual(publish({}).status_code,400)
        self.assertEqual(publish(doc).status_code,201)
        self.assertEqual(publish(doc).status_code,409)
        for stage in ("Scheduled","Waiting Room","Active"):
            self.assertEqual(self.client.post(url+"/stage",{"stage":stage}).status_code,200)
        self.assertEqual(publish(doc).status_code,409)
        self.assertEqual(self.client.post(url+"/stage",{"stage":"Ended"}).status_code,200)

    def test_disqualification_persists_and_reverses(self):
        from .management.commands.import_ecode import Command
        Command().refresh([dict(enrollmentNumber="E01",username="student",fullName="Student",batchYear="2026",contestPin="123456")])
        candidate=get_user_model().objects.get(username="student")
        entry=Entry.objects.create(user=candidate,contest=self.live,enrollment="E01",display="Student",acknowledged=timezone.now())
        url=f"/api/organizer/entries/{entry.pk}/eligibility"
        self.client.force_login(candidate)
        self.assertEqual(self.client.post(url,{"action":"disqualify","reason":"Review"}).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url,{"action":"disqualify","reason":""}).status_code,400)
        self.assertEqual(self.client.post(url,{"action":"disqualify","reason":"Review"}).status_code,200)
        self.client.force_login(candidate)
        state=self.client.get(f"/api/workspace?contest={self.live.pk}").json()
        self.assertFalse(state["eligible"]);self.assertIn("Review",state["reason"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url,{"action":"reinstate","reason":"Reviewed"}).status_code,200)
        self.assertEqual(entry.decision_set.count(),2)
