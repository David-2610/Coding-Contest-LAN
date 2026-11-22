import fcntl
import logging
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from arena.engine import tick
from arena.models import Job

class Command(BaseCommand):
    help = "Process pending contest jobs using concurrent execution slots with auto-recovery."

    def add_arguments(self, parser):
        parser.add_argument("--slot", type=int, default=1, help="Worker slot number (1-12)")

    def handle(self, *args, **options):
        slot = options.get("slot") or 1
        lock_file = settings.DATA / f"worker_{slot}.lock"
        with lock_file.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CommandError(f"Worker slot {slot} is already running")
            if slot == 1:
                Job.objects.filter(state="running").update(state="queued")
            logging.info("Judge worker slot #%d started and listening for jobs...", slot)
            while True:
                try:
                    if not tick(worker_id=slot):
                        time.sleep(0.25)
                except Exception as exc:
                    logging.exception("Recovered from unexpected exception in worker slot #%d: %s", slot, exc)
                    time.sleep(1)
