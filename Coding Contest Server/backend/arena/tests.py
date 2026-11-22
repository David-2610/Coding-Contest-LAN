from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .engine import close_contest,tick
from .models import Contest,Draft,Entry,Job,Problem
from .sandbox import execute

class Journey(TestCase):
    def setUp(self):
        now=timezone.now()
        self.contest=Contest.objects.create(title="Test",starts=now-timedelta(minutes=1),ends=now+timedelta(hours=1))
        self.people=[]
        for n in range(2):
            u=get_user_model().objects.create_user(username=f"user{n}")
            from .models import Profile
            Profile.objects.create(user=u,enrollment=str(n),ecode_batch="2026")
            self.people.append(u)
            Entry.objects.create(acknowledged=now,contest=self.contest,user=u,enrollment=str(n),display=f"Solver {n}")
        self.problem=Problem.objects.create(contest=self.contest,title="Even",statement="Count even",function="f",starter="def f(x): pass",published=True,
            cases=[{"args":[[2,3]],"expected":1,"sample":True},
                   {"args":[[0,2]],"expected":2,"sample":False},
                   {"args":[[0,4]],"expected":2,"sample":False}])
        self.client.force_login(self.people[0])
    def post(self,action,**fields):
        return self.client.post(f"/api/problems/{self.problem.pk}/{action}",fields,content_type="application/json")
    def test_journey(self):
        wrong="def f(x): return sum(n!=0 and n%2==0 for n in x)"
        good="def f(x): return sum(n%2==0 for n in x)"
        token=str(uuid4())
        receipt=self.post("submit",source=wrong,token=token).json()
        with patch("arena.engine.execute", wraps=execute) as runner:
            tick()
        self.assertEqual(runner.call_count, 2)
        url=f'/api/jobs/{receipt["id"]}'
        result = self.client.get(url).json()["result"]
        self.assertEqual((result["passed"], result["total"], result["skipped"]), (1, 3, 1))
        case, = result["cases"]
        self.assertEqual((case["number"], case["status"]), (2, "Wrong answer"))
        self.client.force_login(self.people[1]); self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.people[0])
        self.post("run",source=good,tests=[],token=str(uuid4()))
        tick()
        board=f"/api/contests/{self.contest.pk}/leaderboard"
        self.assertEqual(self.client.get(board).json()["rows"][0]["solved"],0)
        self.post("submit",source=good,token=str(uuid4())); tick()
        self.assertEqual(self.client.get(board).json()["rows"][0]["solved"],1)
        unfinished="def f(x):"
        self.assertEqual(self.post("draft",source=unfinished,revision=0).status_code,200)
        self.assertEqual(self.post("draft",source=good,revision=0).status_code,409)
        self.contest.ends=timezone.now()-timedelta(microseconds=1); self.contest.save()
        self.assertEqual(self.post("submit",source=wrong,token=token).json(),receipt)
        self.assertEqual(self.post("submit",source=good,token=str(uuid4())).status_code,403)
        close_contest(self.contest.pk);close_contest(self.contest.pk);tick()
        archive=Job.objects.get(kind="archive")
        self.assertEqual(archive.source,unfinished)
        self.assertEqual(archive.result["verdict"],"Failed")
        self.contest.refresh_from_db()
        self.assertEqual(self.contest.final["rows"][0]["solved"],1)
        self.assertNotIn("enrollment",self.contest.final["rows"][0])
    def test_sandbox_boundaries(self):
        for code in ["open('/etc/passwd').read()","__import__('socket').socket()","__import__('os').fork()"]:
            status,_=execute("def f(): return "+code,"f",[])
            self.assertEqual(status,"Runtime error")
