from django.core.management.base import BaseCommand
from huey.contrib.djhuey import HUEY


class Command(BaseCommand):
    help = "Flushes whole Huey storage or a build lock for a single course. Helpful if a task lock got stuck."

    def add_arguments(self, parser):
        parser.add_argument('course_key', nargs='?', type=str, default="")

    def handle(self, *args, **options):
        # Check by arguments.
        if options["course_key"]:
            storage_key = HUEY.lock_task(f"build-{options['course_key']}")._key
            HUEY.delete(storage_key)
            self.stdout.write(f"Deleted lock for course with key {options['course_key']}")
        else:
            HUEY.flush()
            self.stdout.write(f"Flushed Huey storage")
