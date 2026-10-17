"""Email backends built on django-mailer."""

import time

from django.conf import settings
from mailer.backend import DbBackend
from mailer.engine import send_all
from mailer.models import Message

from common.metrics import metrics


class ImmediateDbBackend(DbBackend):
    """Queues via django-mailer, then immediately delivers *just those* messages.

    Plain DbBackend only writes to the `Message` table — delivery and the
    MessageLog audit trail only happen when something calls
    mailer.engine.send_all(), normally a scheduled `manage.py send_mail`
    process. Nothing in this deploy schedules that, so messages would sit
    queued forever.

    send_all() with no arguments drains the *entire* queue, not just the
    messages this call enqueued: sending one email would also retry every
    other queued/deferred message, inflate this request's latency
    unpredictably, and race with any concurrent send_messages() call also
    draining the full table. Passing send_all() a queryset scoped to the
    Message rows this call just created avoids all of that while keeping
    send_all()'s MessageLog/DontSendEntry bookkeeping and retry-on-failure
    behavior.
    """

    def send_messages(self, email_messages):
        """Queue ``email_messages`` and deliver exactly those messages now.

        Returns:
            int: The number of messages queued.
        """
        # Mirrors DbBackend.send_messages(), but keeps the created rows
        # (with real pks - Postgres's bulk_create returns them) instead of
        # just a count, so delivery below can be scoped to them.
        batch_size = getattr(settings, "MAILER_MESSAGES_BATCH_SIZE", None)
        messages = Message.objects.bulk_create(
            [Message(email=email) for email in email_messages], batch_size
        )
        if not messages:
            return 0

        pks = [m.pk for m in messages]
        start = time.perf_counter()
        send_all(queryset=Message.objects.filter(pk__in=pks))
        # send_all() deletes each Message row it delivers (or discards as
        # undecodable); anything left was deferred after a failure or not
        # attempted, and stays queued.
        unsent = Message.objects.filter(pk__in=pks).count()
        metrics.record_email_delivery(
            sent=len(pks) - unsent,
            unsent=unsent,
            duration=time.perf_counter() - start,
        )
        return len(messages)
