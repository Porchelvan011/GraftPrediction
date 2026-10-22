import threading
import logging
import config

log = logging.getLogger(__name__)


class EmailWorker:
    def __init__(self, send_func):
        self.send_func = send_func

    def send_async(self, recipient, subject, body):
        # If a broker is configured, a Celery implementation could be used here.
        if config.BROKER_URL:
            # Celery stub: in production, user should wire Celery here.
            log.info("BROKER configured but Celery not wired - falling back to thread")
        th = threading.Thread(target=self._send_and_log, args=(recipient, subject, body), daemon=True)
        th.start()

    def _send_and_log(self, recipient, subject, body):
        try:
            self.send_func(recipient, subject, body)
        except Exception as e:
            log.exception("Failed to send email to %s: %s", recipient, e)


# Helper that expects a send_func(recipient, subject, body)
email_worker = EmailWorker(lambda r, s, b: log.info("Email to %s: %s", r, s))
