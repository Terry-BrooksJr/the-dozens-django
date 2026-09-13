from mailer.backend import DbBackend
from mailer.engine import send_all


class ImmediateDbBackend(DbBackend):
    """Queues via django-mailer, then drains the queue immediately.

    Plain DbBackend only writes to the `Message` table — delivery and the
    MessageLog audit trail only happen when something calls
    mailer.engine.send_all(), normally a scheduled `manage.py send_mail`
    process. Nothing in this deploy schedules that, so messages would sit
    queued forever. Draining inline keeps send_all()'s MessageLog/
    DontSendEntry bookkeeping and retry-on-failure behavior while making
    delivery effectively synchronous.
    """

    def send_messages(self, email_messages):
        count = super().send_messages(email_messages)
        send_all()
        return count
