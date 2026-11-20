"""Create optional Django groups with permissions. Does not assign users."""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


ROLE_PERMISSIONS = {
    "ИБ-оператор": {
        "campaigns": {"view_campaign", "add_campaign", "change_campaign", "view_campaignparticipant", "view_safeevent", "view_traininglink", "view_participantevent"},
        "email_templates": {"view_emailtemplate", "add_emailtemplate", "change_emailtemplate"},
        "employees": {"view_employee", "view_department", "view_position"},
        "delivery": {"view_campaigndispatch", "view_deliveryrecord", "view_dispatchaudit", "start_dispatch", "stop_dispatch"},
    },
    "ИБ-аудитор": {
        "campaigns": {"view_campaign", "view_campaignparticipant", "view_safeevent", "view_traininglink", "view_participantevent"},
        "delivery": {"view_simulationdomain", "view_campaigndispatch", "view_deliveryrecord", "view_dispatchaudit"},
    },
}


class Command(BaseCommand):
    help = "Создать группы ИБ-оператор/ИБ-аудитор, не назначая пользователей"

    def handle(self, *args, **options):
        for role_name, by_app in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role_name)
            permissions = []
            for app, names in by_app.items():
                permissions.extend(Permission.objects.filter(content_type__app_label=app, codename__in=names))
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"{role_name}: назначено {len(permissions)} разрешений"))
        self.stdout.write("Пользователи не добавлялись в группы. Ролевые проверки старых модулей будут усилены в следующей версии.")
