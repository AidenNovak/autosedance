from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from ..config import get_settings

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, code: str, *, ttl_minutes: int) -> None:
    """Send the OTP code to the given email.

    In dev, you can set AUTH_DEV_PRINT_CODE=1 to log the code instead of sending.
    """

    settings = get_settings()
    if settings.auth_dev_print_code:
        logger.info("[DEV] OTP for %s: %s (ttl=%sm)", to_email, code, ttl_minutes)
        return

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password or not settings.smtp_from:
        raise RuntimeError("SMTP is not configured")

    subject = f"AutoSedance verification code: {code}"
    body = (
        f"Your AutoSedance verification code is: {code}\n\n"
        f"This code expires in {ttl_minutes} minutes.\n\n"
        "If you did not request this code, you can ignore this email."
    )

    msg = EmailMessage()
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_from))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, int(settings.smtp_port), timeout=15) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port), timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

