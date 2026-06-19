import json
import logging
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.config import BACKEND_ROOT, settings

logger = logging.getLogger(__name__)


class AuthEmailDeliveryError(Exception):
    pass


class AuthEmailConfigurationError(AuthEmailDeliveryError):
    pass


@dataclass(frozen=True)
class AuthEmailMessage:
    to_email: str
    subject: str
    body: str
    purpose: str
    code: str | None = None


class AuthEmailSender(Protocol):
    def send(self, message: AuthEmailMessage) -> None: ...


class LocalDevEmailSender:
    """Write plaintext auth codes to a local JSONL outbox for development only."""

    def __init__(self, outbox_path: str | Path = settings.auth_local_email_outbox_path) -> None:
        path = Path(outbox_path)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        self._outbox_path = path

    @property
    def outbox_path(self) -> Path:
        return self._outbox_path

    def send(self, message: AuthEmailMessage) -> None:
        self._outbox_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sent_at": datetime.now(UTC).isoformat(),
            **asdict(message),
        }
        with self._outbox_path.open("a", encoding="utf-8") as outbox:
            outbox.write(json.dumps(payload, sort_keys=True))
            outbox.write("\n")
        logger.info(
            "Auth email written to local outbox path=%s purpose=%s to=%s",
            self._outbox_path,
            message.purpose,
            message.to_email,
        )


class MailgunEmailSender:
    """Send auth email messages with Mailgun's Provider API."""

    def __init__(
        self,
        *,
        api_key: str | None = settings.mailgun_api_key,
        domain: str | None = settings.mailgun_domain,
        from_email: str = settings.auth_email_from_address,
        api_base_url: str = settings.mailgun_api_base_url,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key:
            raise AuthEmailConfigurationError("MAILGUN_API_KEY is required for Mailgun email delivery.")
        if not domain:
            raise AuthEmailConfigurationError("MAILGUN_DOMAIN is required for Mailgun email delivery.")

        self._api_key = api_key
        self._domain = domain
        self._from_email = from_email
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def send(self, message: AuthEmailMessage) -> None:
        url = f"{self._api_base_url}/v3/{self._domain}/messages"
        payload = urllib.parse.urlencode(
            {
                "from": self._from_email,
                "to": message.to_email,
                "subject": message.subject,
                "text": message.body,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Authorization": _basic_auth_header("api", self._api_key)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                status = response.status
        except OSError as exc:
            raise AuthEmailDeliveryError("Mailgun email delivery failed.") from exc

        if status < 200 or status >= 300:
            raise AuthEmailDeliveryError(f"Mailgun email delivery failed with status {status}.")


def build_auth_email_sender() -> AuthEmailSender:
    if settings.auth_email_delivery_backend == "local":
        return LocalDevEmailSender()
    if settings.auth_email_delivery_backend == "mailgun":
        return MailgunEmailSender()
    raise AuthEmailConfigurationError("Unsupported auth email delivery backend.")


def _basic_auth_header(username: str, password: str) -> str:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"
