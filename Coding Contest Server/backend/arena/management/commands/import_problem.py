"""Import contest question(s) from JSON file(s) into a local contest."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from jsonschema import validate, ValidationError as SchemaError
from arena.models import Contest, Problem


class Command(BaseCommand):
    help = "Import problem(s) from JSON file or directory into a contest"

    def add_arguments(self, parser):
        parser.add_argument("contest", help="Contest ID (local primary key or E-Code contestId)")
        parser.add_argument("path", help="Path to question JSON file or directory containing JSON files")
        parser.add_argument("--replace", action="store_true", help="Replace problem if question ID already exists in this contest")

    def handle(self, contest, path, replace=False, **options):
        # Resolve contest
        c = None
        if contest.isdigit():
            c = Contest.objects.filter(pk=int(contest)).first()
        if not c:
            c = Contest.objects.filter(ecode_contest_id=contest).first()
        if not c:
            raise CommandError(f"Contest '{contest}' not found in local database.")

        schema_path = settings.BASE.parent / "frontend/dist/question-schema.json"
        if not schema_path.exists():
            schema_path = settings.BASE / "var/static/question-schema.json"
        if not schema_path.exists():
            raise CommandError("Question schema file not found.")
            
        schema = json.loads(schema_path.read_text())

        target_path = Path(path).resolve()
        if not target_path.exists():
            raise CommandError(f"File or directory does not exist: {target_path}")

        if target_path.is_file():
            files = [target_path]
        else:
            files = sorted(target_path.glob("*.json"))
            if not files:
                raise CommandError(f"No .json files found in directory: {target_path}")

        imported = 0
        for f in files:
            try:
                raw = json.loads(f.read_text())
                items = raw if isinstance(raw, list) else [raw]
                for data in items:
                    validate(data, schema)
                    
                    # Check test case IDs uniqueness
                    ids = [t["id"] for t in data["testCases"]]
                    if len(set(ids)) != len(ids):
                        raise CommandError(f"Test case IDs must be unique in {f.name} ({data.get('id', '')})")

                    data["topics"] = list(dict.fromkeys(" ".join(t.split()).casefold() for t in data["topics"]))
                    if "" in data["topics"]:
                        raise CommandError(f"Topics cannot be empty in {f.name} ({data.get('id', '')})")

                    cases = [
                        dict(args=[t["input"]], expected=t["expectedOutput"], sample=(t["visibility"] == "public"))
                        for t in data["testCases"]
                    ]

                    p = Problem.objects.filter(external_id=data["id"]).first()
                    if p and p.contest_id != c.pk:
                        raise CommandError(f"Question ID '{data['id']}' already exists in another contest (Contest {p.contest_id}).")
                    if p and not replace:
                        raise CommandError(f"Question ID '{data['id']}' already exists in this contest. Use --replace to overwrite.")

                    p = p or Problem(contest=c, external_id=data["id"])
                    p.title = data["title"]
                    p.statement = data["description"]
                    p.package = data
                    p.cases = cases
                    p.published = True
                    p.function = "solve"
                    p.starter = data["languages"]["python3"]["starterCode"]
                    p.full_clean()
                    p.save()

                    pub_count = sum(1 for tc in data["testCases"] if tc.get("visibility") == "public")
                    hid_count = sum(1 for tc in data["testCases"] if tc.get("visibility") == "hidden")
                    pts = data.get("scoring", {}).get("maxScore", 100)

                    self.stdout.write(self.style.SUCCESS(
                        f"✓ Imported [{data['id']}] \"{data['title']}\": "
                        f"{pub_count} public, {hid_count} hidden tests, {pts} pts ({f.name})"
                    ))
                    imported += 1

            except SchemaError as e:
                raise CommandError(f"Schema error in {f.name} at {e.json_path}: {e.message}")
            except Exception as e:
                raise CommandError(f"Failed to import {f.name}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Successfully imported {imported} problem(s) into contest '{c.title}' (Local ID: {c.pk})."
        ))
