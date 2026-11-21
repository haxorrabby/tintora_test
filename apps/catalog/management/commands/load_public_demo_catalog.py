from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError
from django.db import transaction

from apps.catalog.models import Category, Product


FIXTURE_PATH = settings.BASE_DIR / "apps" / "catalog" / "fixtures" / "public_demo_catalog.json"


class Command(BaseCommand):
    help = "Load the public demo catalog once into an empty database."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")

    def handle(self, *args, **options):
        using = options["database"]

        if Product.objects.using(using).exists():
            self.stdout.write("Catalog already exists; leaving it unchanged.")
            return
        if Category.objects.using(using).exists():
            raise CommandError("Categories exist but products do not; refusing to import over partial data.")
        if not FIXTURE_PATH.is_file():
            raise CommandError(f"Public catalog fixture not found: {FIXTURE_PATH}")

        with transaction.atomic(using=using):
            call_command(
                "loaddata",
                str(FIXTURE_PATH),
                database=using,
                verbosity=0,
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS("Public demo catalog loaded."))
