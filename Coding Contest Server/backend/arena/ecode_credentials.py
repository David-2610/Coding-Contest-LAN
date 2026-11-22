import os
from django.conf import settings
from django.core.management.base import CommandError


def sync_secret():
    secret = os.environ.get("CODECLASH_SYNC_SECRET")
    if not secret:
        try:
            secret = (settings.DATA / "ecode-sync.key").read_text().strip()
        except OSError:
            pass
    if not secret:
        raise CommandError("Configure the E-Code sync secret on the Acer.")
    return secret
