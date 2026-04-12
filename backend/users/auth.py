import structlog

from .models import UserAccount

logger = structlog.get_logger()


def get_current_user(request):
    """
    Return the UserAccount associated with the current session, or None.

    Views that require authentication call this and return a 401 if None is returned.
    This is the single place that translates a session cookie into a UserAccount,
    so all auth logic is in one spot rather than repeated across views.
    """
    user_account_id = request.session.get("user_account_id")
    if not user_account_id:
        return None
    try:
        return UserAccount.objects.get(id=user_account_id)
    except UserAccount.DoesNotExist:
        # Session references a user that no longer exists — treat as unauthenticated.
        logger.warning("session_references_missing_user", user_account_id=user_account_id)
        return None
