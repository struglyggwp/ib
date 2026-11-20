"""Recovery after broker outage. Never retries already claimed/ambiguous messages."""
from django.core.management.base import BaseCommand
from delivery.models import CampaignDispatch, DeliveryRecord
from delivery.tasks import dispatch_campaign


class Command(BaseCommand):
    help = "Повторно поставить в Celery ожидающие задания. Не повторяет SENDING/FAILED/ACCEPTED."

    def handle(self, *args, **kwargs):
        count = 0
        qs = CampaignDispatch.objects.filter(state__in=[CampaignDispatch.State.QUEUED, CampaignDispatch.State.RUNNING])
        for dispatch in qs:
            if not DeliveryRecord.objects.filter(dispatch=dispatch, status=DeliveryRecord.State.PENDING).exists():
                continue
            dispatch_campaign.delay(str(dispatch.pk))
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Перепоставлено в очередь кампаний: {count}"))
