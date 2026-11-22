import fcntl
import time
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from arena.engine import tick
from arena.models import Job
class Command(BaseCommand):
    help="Process pending contest jobs using one local execution slot."
    def handle(self,*args,**kwargs):
        with (settings.DATA/"worker.lock").open("a") as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise CommandError("Worker already running")
            Job.objects.filter(state="running").update(state="queued")
            while True:
                if not tick(): time.sleep(.4)
