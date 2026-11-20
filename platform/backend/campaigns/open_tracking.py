"""Open tracking is an image-load *signal*, not proof that a person read email.

Does not store IPs, User-Agent or any request parameters. All valid/invalid
requests return the same transparent GIF to avoid an existence oracle.
"""

import os

from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from delivery.models import DeliveryRecord
from .models import ParticipantEvent, TrainingLink

# Transparent single-pixel GIF (43 bytes). No external assets, cookies or JS.
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
    b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _can_log(request):
    # These explicit request headers indicate prefetch rather than user viewing.
    # Mail proxies may still fetch without such headers; the signal is uncertain.
    purpose = " ".join((
        request.headers.get("Purpose", ""),
        request.headers.get("Sec-Purpose", ""),
        request.headers.get("X-Moz", ""),
    )).lower()
    return "prefetch" not in purpose and "prerender" not in purpose


@require_GET
def email_open_pixel(request, token):
    response = HttpResponse(PIXEL_GIF, content_type="image/gif")
    response["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Content-Length"] = str(len(PIXEL_GIF))

    if os.environ.get("SMTP_OPEN_TRACKING_ENABLED", "1") != "1" or not _can_log(request):
        return response

    try:
        record = DeliveryRecord.objects.select_related(
            "participant__campaign",
        ).get(open_token=token)
    except DeliveryRecord.DoesNotExist:
        return response

    # No event before the message is handed to SMTP, or for a blocked/failed
    # delivery. This also prevents someone inspecting the queue from
    # creating fake opens for still-pending recipients.
    if record.status != DeliveryRecord.State.ACCEPTED or not record.smtp_accepted_at:
        return response
    if not TrainingLink.objects.filter(
        participant_id=record.participant_id, revoked=False,
        expires_at__gt=timezone.now(),
    ).exists():
        return response

    now = timezone.now()
    try:
        ParticipantEvent.objects.get_or_create(
            participant_id=record.participant_id,
            kind=ParticipantEvent.Kind.EMAIL_OPEN_SIGNAL,
            dedupe_slot=int(now.timestamp()) // 300,
        )
    except IntegrityError:
        # Concurrent requests for the same message/slot: the DB uniqueness
        # rule wins. Do not expose this through a tracking endpoint.
        pass
    return response
