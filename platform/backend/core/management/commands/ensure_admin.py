import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Create the initial administrator if it does not exist."
    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@training.test")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not password or password.startswith("ChangeThis"):
            raise CommandError("Set a unique DJANGO_SUPERUSER_PASSWORD in .env.")
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True, "is_active": True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Administrator '{username}' created."))
        elif not user.is_staff or not user.is_superuser:
            raise CommandError("Configured admin username exists but is not a superuser; resolve manually.")
        else:
            self.stdout.write("Administrator already exists; password was not changed.")
