"""
Сервис отправки email.

EMAIL_BACKEND=console — выводит код в лог (для разработки).
EMAIL_BACKEND=smtp    — отправляет через SMTP.
"""

import logging

from app.core.interfaces import IEmailService
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)


class EmailService(IEmailService):
    """Отправка email с кодом подтверждения."""

    def send_verification_code(self, email: str, code: str) -> None:
        """Отправить код подтверждения на указанный email."""
        if settings.EMAIL_BACKEND == "smtp":
            self._send_smtp(email, code)
        else:
            self._send_console(email, code)

    def _send_console(self, email: str, code: str) -> None:
        """Вывести код в лог (режим разработки)."""
        logger.info("=" * 60)
        logger.info(f"[EMAIL] To: {email}")
        logger.info(f"[EMAIL] Verification code: {code}")
        logger.info("[EMAIL] Code expires in 10 minutes")
        logger.info("=" * 60)

    def _send_smtp(self, email: str, code: str) -> None:
        """Отправить email через SMTP."""
        import smtplib
        from email.mime.text import MIMEText

        body = (
            f"Ваш код подтверждения для Perfume App: {code}\n\n"
            f"Код действует 10 минут.\n"
            f"Если вы не запрашивали код — проигнорируйте это письмо."
        )
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"Код подтверждения: {code}"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = email

        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
