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
            time.sleep(4)
