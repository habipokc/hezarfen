from django.core.management.base import BaseCommand

from tracking.retention import prune_positions, record_run


class Command(BaseCommand):
    help = "Delete position history older than POSITIONS_RETENTION_DAYS."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="override the retention")

    def handle(self, *args, days=None, **options):
        result = prune_positions(days)
        record_run(result, trigger="command")
        self.stdout.write(
            f"deleted {result.deleted} positions older than {result.days} days "
            f"({result.cutoff:%F %T}) in {result.seconds:.2f} s"
        )
