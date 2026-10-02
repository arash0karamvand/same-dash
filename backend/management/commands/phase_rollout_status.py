import json

from django.core.management.base import BaseCommand

from logic.migration_readiness import apply_safe_backfill, readiness_report


class Command(BaseCommand):
    help = "Phase 1-6 rollout flags and safe legacy-data backfill readiness"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply only unambiguous backfills and queue ambiguous records.",
        )
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        result = apply_safe_backfill() if options["apply"] else readiness_report()
        result["mode"] = "apply" if options["apply"] else "dry-run"
        text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        self.stdout.write(text)
