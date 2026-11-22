import subprocess
import sys
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .portal import organizer
from .models import Contest, EcodeTransfer


@organizer
@require_http_methods(["GET", "POST"])
def transfer(request, cid=None):
    if cid is not None:
        key = f"standings-{cid}"
    elif "contest" in request.path or request.GET.get("key") == "fetch-contest":
        key = "fetch-contest"
    else:
        key = "roster"
    if cid is not None and not Contest.objects.filter(pk=cid,final__isnull=False).exists():
        return JsonResponse({"error":"Final standings are not ready."},status=409)
    with transaction.atomic():
        task, _ = EcodeTransfer.objects.select_for_update().get_or_create(key=key)
        if task.status=="running" and timezone.now()-task.updated>timedelta(minutes=3):
            service=subprocess.run(["systemctl","--user","is-active","codeclash-transfer-"+key],capture_output=True,text=True)
            if service.stdout.strip() in ("inactive","failed","unknown"):
                task.status="error"
                task.message="Transfer interrupted. Check E-Code before retrying."
                task.save()
        if request.method=="POST" and task.status!="running" and not (cid and task.status=="done"):
            task.status="running"
            if cid:
                task.message = "Sending final standings…"
            elif key == "fetch-contest":
                task.message = "Fetching contest from E-Code…"
            else:
                task.message = "Fetching roster…"
            task.save()
            transaction.on_commit(lambda: dispatch(key))
    task.refresh_from_db()
    return JsonResponse({"status":task.status,"message":task.message})


def dispatch(key):
    backend=settings.BASE
    command=["systemd-run","--user","--quiet","--collect","--unit=codeclash-transfer-"+key,
             "--working-directory="+str(backend),"--setenv=LD_LIBRARY_PATH="+str(backend/"var/maria-runtime/usr/lib/x86_64-linux-gnu"),
             "--property=UMask=0077","--",sys.executable,"manage.py","ecode_transfer",key]
    try:
        subprocess.run(command,check=True,timeout=10)
    except (OSError,subprocess.SubprocessError):
        EcodeTransfer.objects.filter(key=key).update(status="error",message="Could not start the transfer service. Check the Acer user services.")
