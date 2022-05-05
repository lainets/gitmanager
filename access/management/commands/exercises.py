from django.core.management.base import BaseCommand, CommandError
from access.config import CourseConfig as config

class Command(BaseCommand):
    args = "<course_key</exercise_key>>"
    help = "Tests configuration files syntax."

    def handle(self, *args, **options):

        # Check by arguments.
        if len(args) > 0:
            if "/" in args[0]:
                course_key, exercise_key = args[0].split("/", 1)
            else:
                course_key = args[0]
                exercise_key = None
            course = config.get_or_none(course_key)
            if course is None:
                raise CommandError("Course not found for key: %s" % (course_key))
            self.stdout.write("Configuration syntax ok for: %s" % (course_key))

            if exercise_key:
                (_course, exercise) = config.course_and_exercise_configs(course_key, exercise_key)
                if exercise is None:
                    raise CommandError("Exercise not found for key: %s/%s" % (course_key, exercise_key))
                self.stdout.write("Configuration syntax ok for: %s/%s" % (course_key, exercise_key))

            else:
                _course = config.get(course_key)
                exercises = _course.get_exercise_list()
                for exercise in exercises:
                    self.stdout.write("Configuration syntax ok for: %s/%s" % (course_key, exercise["key"]))

        # Check all.
        else:
            for course in config.all():
                self.stdout.write("Configuration syntax ok for: %s" % (course.data["key"]))
                _course = config.get(course.data["key"])
                exercises = _course.get_exercise_list()
                for exercise in exercises:
                    self.stdout.write("Configuration syntax ok for: %s/%s" % (course.data["key"], exercise["key"]))
