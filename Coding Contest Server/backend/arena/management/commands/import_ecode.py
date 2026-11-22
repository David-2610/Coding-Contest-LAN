"""Refresh the offline roster without persisting the upstream response."""
from arena.ecode_credentials import sync_secret
import json
import re
from urllib.error import URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from arena.models import Profile


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Command(BaseCommand):
    help = "Refresh E-Code student sign-in from the authenticated roster"

    def handle(self, **options):
        from arena.ecode_client import fetch_roster, EcodeApiError
        try:
            rows, data = fetch_roster(timeout=90)
            self.refresh(rows)
        except (EcodeApiError, ValueError, TypeError, KeyError) as exc:
            raise CommandError(f"Roster request or validation failed: {exc}") from None
        self.stdout.write(f"Roster refreshed: {len(rows)} students.")

    @transaction.atomic
    def refresh(self, rows):
        seen = set()
        for row in rows:
            enrollment, handle, name, batch, pin = (row[k] for k in
                ("enrollmentNumber", "username", "fullName", "batchYear", "contestPin"))
            if not all(isinstance(v,str) and v.strip()==v and v for v in (enrollment,handle,name,batch,pin)):
                raise ValueError
            if (handle.casefold()=="organizer" or enrollment.casefold()=="organizer" or len(enrollment)>64 or len(handle)>150 or len(name)>80 or
                    not re.fullmatch(r"[0-9]{4}",batch) or not re.fullmatch(r"[0-9]{6}",pin) or enrollment.casefold() in seen):
                raise ValueError
            seen.add(enrollment.casefold())
            profile = Profile.objects.select_related("user").filter(enrollment=enrollment).first()
            if profile and (not profile.ecode_batch or profile.user.is_staff or profile.user.is_superuser):
                raise CommandError("Enrollment conflicts with a local account. Roster refresh rolled back.")
            user = profile.user if profile else User()
            if User.objects.filter(username__iexact=handle).exclude(pk=user.pk).exists():
                raise CommandError("Username conflict. Roster refresh rolled back.")
            changed = not profile or user.username != handle or not user.is_active
            user.username, user.is_active = handle, True
            if not profile or not user.check_password(pin):
                user.set_password(pin)
                changed = True
            if changed:
                user.save()
            if profile and (profile.full_name,profile.enrollment,profile.ecode_batch)==(name,enrollment,batch):
                continue
            Profile.objects.update_or_create(user=user, defaults=dict(full_name=name,enrollment=enrollment,ecode_batch=batch))
        for profile in Profile.objects.exclude(ecode_batch="").select_related("user"):
            if profile.enrollment.casefold() not in seen:
                User.objects.filter(pk=profile.user_id).update(is_active=False)
