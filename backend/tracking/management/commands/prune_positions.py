from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracking.models import Position


class Command(BaseCommand):
    help = "Delete position history older than POSITIONS_RETENTION_DAYS."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="override the retention")

    def handle(self, *args, days=None, **options):
        days = days if days is not None else settings.POSITIONS_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        # The ts filter is served by the BRIN index: whole block ranges older than the
        # cutoff are found without visiting every row.
        deleted, _ = Position.objects.filter(ts__lt=cutoff).delete()
        self.stdout.write(f"deleted {deleted} positions older than {days} days ({cutoff:%F %T})")
