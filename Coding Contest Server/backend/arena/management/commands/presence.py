import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db import transaction,close_old_connections
from django.utils import timezone
from arena.models import Entry,ConnectionEvent
from arena.portal import expire,GRACE

class Command(BaseCommand):
    help="Observe expired workspace heartbeats. Mark gaps in observer coverage as unknown."
    def handle(self,*args,**kwargs):
        previous=None
        while True:
            close_old_connections()
            now=timezone.now()
            unknown=previous is None or now-previous>GRACE
            with transaction.atomic():
                rows=Entry.objects.select_for_update().filter(Q(contest__stage__in=["Scheduled","Waiting Room"])|Q(contest__starts__lte=now,contest__ends__gt=now),presence="Online",last_seen__lt=now-GRACE)
                for entry in rows:
                    if unknown:
                        entry.presence="Unknown";entry.save(update_fields=["presence"])
                        ConnectionEvent.objects.create(entry=entry,kind="Observation gap")
                    else:expire(entry,now)
            previous=now

            # Continuous Multi-Judge Worker Watchdog & Self-Healing
            try:
                from arena.models import Job
                import subprocess
                from django.conf import settings
                stalled = Job.objects.filter(state="queued", received__lt=now - timedelta(seconds=12)).exists()
                workers_file = settings.DATA / "judge-workers"
                target_count = 4
                if workers_file.exists():
                    try: target_count = int(workers_file.read_text().strip())
                    except Exception: pass
                active_count = sum(1 for i in range(1, target_count + 1) if subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"coding-contest-pilot-judge-{i}"]).returncode == 0)
                if stalled or active_count < target_count:
                    server_script = settings.BASE / "scripts" / "server"
                    subprocess.run(["bash", str(server_script), "start"], timeout=8)
            except Exception:
                pass

            time.sleep(4)
