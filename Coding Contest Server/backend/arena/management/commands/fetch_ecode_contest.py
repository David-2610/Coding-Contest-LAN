"""Fetch active contest details from E-Code and cache locally for offline contest."""
import json
from django.core.management.base import BaseCommand, CommandError
from arena.ecode_client import EcodeApiError, fetch_active_contest
from arena.ecode_contest import fetch_and_cache_contest, ContestConflictError

class Command(BaseCommand):
    help = "Fetch active contest details from E-Code and cache locally on the LAN server"

    def add_arguments(self, parser):
        parser.add_argument("--contest-id", help="Target specific contest ID")
        parser.add_argument("--event-id", help="Target specific event document ID")
        parser.add_argument("--force", action="store_true", help="Force overwrite even if contest has local activity")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and print details without modifying the local database")

    def handle(self, **options):
        contest_id = options.get("contest_id")
        event_id = options.get("event_id")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        self.stdout.write("Connecting to E-Code cloud...")
        try:
            if dry_run:
                data = fetch_active_contest(contest_id=contest_id, event_id=event_id)
                self.stdout.write(self.style.SUCCESS("E-Code active contest fetched successfully (dry-run):"))
                self.stdout.write(json.dumps(data, indent=2))
                return

            result = fetch_and_cache_contest(contest_id=contest_id, event_id=event_id, force=force)
            contest = result["contest"]
            action = "Created" if result["created"] else "Updated"
            
            self.stdout.write(self.style.SUCCESS(
                f"{action} local contest '{contest.title}' (Local ID: {contest.pk}, E-Code ID: {contest.ecode_contest_id})"
            ))
            self.stdout.write(f"  Schedule: {result['startsLocal']} -> {result['endsLocal']} ({result['durationMinutes']} mins)")
            self.stdout.write(f"  Status: {contest.ecode_status} | Batch Target: {contest.batch_target}")
            self.stdout.write(f"  Expected Problems: {result['totalProblems']}")
            if contest.banner_path:
                self.stdout.write(f"  Banner: Cached locally at {contest.banner_path}")
            elif contest.banner_url:
                self.stdout.write(f"  Banner URL: {contest.banner_url}")
                
        except ContestConflictError as e:
            raise CommandError(f"Conflict: {e}")
        except EcodeApiError as e:
            raise CommandError(f"E-Code API error: {e}")
        except Exception as e:
            raise CommandError(f"Failed to fetch contest: {e}")
