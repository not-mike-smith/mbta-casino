from typing import TypedDict

import structlog
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from mbta_casino.responses import error_response

from .auth import get_current_user
from .models import UserAccount

logger = structlog.get_logger()


class RegisterBody(TypedDict):
    email: str


def _user_data(user):
    return {
        "id": user.id,
        "email": user.email,
        "token_balance": user.token_balance,
        "created_at": user.created_at.isoformat(),
    }


@api_view(["POST"])
def register(request: Request):
    body: RegisterBody = request.data  # type: ignore[assignment]
    email = body.get("email", "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return error_response("A valid email address is required.")

    user, created = UserAccount.objects.get_or_create(email=email)

    # Invalidate any previous session and issue a fresh one.
    # flush() deletes the old session record; setting values on request.session
    # afterwards creates a brand new session.
    request.session.flush()
    request.session["user_account_id"] = user.id
    # save() is called explicitly here so that session_key is available immediately
    # to store on the UserAccount record.
    request.session.save()

    user.session_key = request.session.session_key
    user.save(update_fields=["session_key", "updated_at"])

    logger.info("user_registered" if created else "user_session_reissued", user_id=user.id)

    return Response(_user_data(user), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
def logout(request: Request):
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    user.session_key = None
    user.save(update_fields=["session_key", "updated_at"])

    request.session.flush()

    logger.info("user_logged_out", user_id=user.id)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request: Request):
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)
    return Response(_user_data(user))
