from datetime import timedelta
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from arena.models import Contest,Entry,Problem
class Command(BaseCommand):
    @transaction.atomic
    def handle(self,*a,**kw):
        from django.core.management.base import CommandError
        raise CommandError("Pilot account provisioning is disabled.")
