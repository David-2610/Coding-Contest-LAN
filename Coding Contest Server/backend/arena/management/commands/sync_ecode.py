"""Publish a finalized round after an explicit organizer invocation."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from arena.models import Contest
from arena.ecode_client import sync_contest_results, EcodeApiError, EcodeSyncVerificationError
from arena.ecode_contest import generate_sync_payload, ContestSyncError


class Command(BaseCommand):
    help = "Send a finalized contest to E-Code using its official E-Code contest ID"

    def add_arguments(self, parser):
        parser.add_argument("local_id", type=int)
        parser.add_argument("contest_id", nargs="?", default=None)
        parser.add_argument("--check", action="store_true", help="Validate payload without sending to E-Code")
        parser.add_argument("--force", action="store_true", help="Force sync even if already marked as synced")

    def handle(self, local_id, contest_id, check, force=False, **options):
        contest = Contest.objects.filter(pk=local_id).first()
        if not contest or not contest.final:
            raise CommandError("This contest has no finalized standings.")

        if contest_id:
            contest.ecode_contest_id = contest_id

        if not contest.ecode_contest_id:
            raise CommandError("This contest does not have an official E-Code contestId. Fetch contest details from E-Code first.")

        if contest.sync_status == "SYNCED" and not force and not check:
            raise CommandError(
                f"Contest {contest.pk} was already synchronized on {contest.synced_at}. "
                "Use --force if you genuinely need to re-sync."
            )

        try:
            payload, warnings = generate_sync_payload(contest)
        except ContestSyncError as e:
            raise CommandError(f"Payload validation failed: {e}")

        for w in warnings:
            self.stdout.write(self.style.WARNING(f"Warning: {w}"))

        if check:
            self.stdout.write(self.style.SUCCESS(
                f"Validated {len(payload['participants'])} results for contestId: {payload['contestId']}."
            ))
            self.stdout.write(f"Total problems: {payload['totalProblems']}")
            return

        # Perform sync
        contest.sync_status = "SYNCING"
        contest.save(update_fields=["sync_status"])

        try:
            result = sync_contest_results(payload)
            synced_count = result.get("data", {}).get("participantsSynced", len(payload["participants"]))
            
            contest.synced_at = timezone.now()
            contest.sync_status = "SYNCED"
            contest.sync_response = result.get("data")
            contest.save(update_fields=["synced_at", "sync_status", "sync_response"])
            
            self.stdout.write(self.style.SUCCESS(
                f"Synchronized {synced_count} results to E-Code for contestId '{contest.ecode_contest_id}'."
            ))
        except EcodeSyncVerificationError as e:
            contest.sync_status = "SYNC_PENDING"
            contest.save(update_fields=["sync_status"])
            raise CommandError(
                f"Sync transmission timed out. Outcome on E-Code is uncertain. Check online standings before retrying: {e}"
            )
        except (EcodeApiError, ValueError, KeyError, TypeError) as e:
            contest.sync_status = "SYNC_FAILED"
            contest.save(update_fields=["sync_status"])
            raise CommandError(f"Sync failed: {e}")
