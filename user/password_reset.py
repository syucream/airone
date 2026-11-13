import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from user.models import User

logger = logging.getLogger(__name__)


def send_password_reset_email(message: EmailMultiAlternatives) -> None:
    """Keep transport failures from revealing whether a reset recipient exists."""
    try:
        message.send()
    except (SMTPException, OSError):
        logger.exception("Unable to send password reset email")


def get_password_reset_user(username: str) -> User | None:
    """Resolve an unambiguous, eligible reset recipient for either request route."""
    if settings.AIRONE["PASSWORD_RESET_DISABLED"]:
        return None

    users = list(User.objects.filter(username__iexact=username, is_active=True)[:2])
    if len(users) == 1 and users[0].can_reset_password and users[0].email:
        return users[0]
    return None
