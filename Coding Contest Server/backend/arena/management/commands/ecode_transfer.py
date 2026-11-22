from io import StringIO
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from arena.models import EcodeTransfer


class Command(BaseCommand):
    help="Execute an organizer-requested transfer."

    def add_arguments(self, parser):
        parser.add_argument("key")

    def handle(self,key,**options):
        output=StringIO()
        task=EcodeTransfer.objects.get(key=key,status="running")
        try:
            if key=="roster":
                call_command("import_ecode",stdout=output)
            elif key=="fetch-contest":
                call_command("fetch_ecode_contest",stdout=output)
            else:
                cid=int(key.removeprefix("standings-"))
                from arena.models import Contest
                c = Contest.objects.get(pk=cid)
                target_id = c.ecode_contest_id or f"codeclash-lan-{cid}"
                call_command("sync_ecode",cid,target_id,stdout=output)
        except Exception as exc:
            task.status="error"
            task.message=str(exc)[:300] if isinstance(exc,CommandError) else "Transfer failed. Check the Acer database and connectivity."
        else:
            task.status="done"
            task.message=output.getvalue().strip()
        task.save(update_fields=["message","status"])
