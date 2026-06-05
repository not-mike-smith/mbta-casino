from datetime import timedelta

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from mbta.models import TrainPrediction
from mbta_casino.responses import error_response
from users.auth import get_current_user

from .models import Bet

logger = structlog.get_logger()

RESOLVED_STATUSES = [Bet.Status.WON, Bet.Status.LOST, Bet.Status.PUSH, Bet.Status.VOID]


def _bet_data(bet: Bet) -> dict:
    return {
        "id": bet.id,
        "prediction_id": bet.train_prediction_id,
        "station_name": bet.train_prediction.station.name,
        "mbta_route_id": bet.train_prediction.mbta_route_id,
        "direction_label": bet.train_prediction.direction_label,
        "predicted_arrival_time": bet.predicted_arrival_time.isoformat(),
        "direction": bet.direction,
        "amount": bet.amount,
        "status": bet.status,
        "placed_at": bet.placed_at.isoformat(),
        "resolved_at": bet.resolved_at.isoformat() if bet.resolved_at else None,
        "actual_arrival_time": bet.actual_arrival_time.isoformat() if bet.actual_arrival_time else None,
    }


def _token_delta(bet: Bet) -> int:
    if bet.status == Bet.Status.WON:
        return bet.amount
    if bet.status == Bet.Status.LOST:
        return -bet.amount
    return 0  # PUSH or VOID


@api_view(["POST"])
def place_bet(request: Request) -> Response:
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    body = request.data
    prediction_id = body.get("prediction_id")
    direction = body.get("direction")
    amount = body.get("amount")

    if not all([prediction_id, direction, amount is not None]):
        return error_response("prediction_id, direction, and amount are required.")

    if direction not in (Bet.Direction.BEFORE, Bet.Direction.AFTER):
        return error_response("direction must be BEFORE or AFTER.")

    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return error_response("amount must be a positive integer.")

    try:
        prediction = TrainPrediction.objects.select_related("station").get(id=prediction_id)
    except TrainPrediction.DoesNotExist:
        return error_response("Prediction not found.", status_code=422)

    now = timezone.now()
    cutoff = now + timedelta(minutes=settings.BETTING_WINDOW_MINUTES)
    if prediction.has_arrived or prediction.predicted_arrival <= cutoff:
        return error_response("This prediction is no longer open for betting.", status_code=422)

    with transaction.atomic():
        # Lock the user row so concurrent requests can't both pass the balance check.
        locked_user = user.__class__.objects.select_for_update().get(id=user.id)

        if Bet.objects.filter(user_account=locked_user, status=Bet.Status.ACTIVE).exists():
            return error_response(
                "You already have an active bet. Wait for it to resolve before placing another.",
                status_code=409,
            )

        if locked_user.token_balance < amount:
            return error_response(
                f"Insufficient balance. You have {locked_user.token_balance} tokens.",
                status_code=422,
            )

        locked_user.token_balance -= amount
        locked_user.save(update_fields=["token_balance", "updated_at"])

        bet = Bet.objects.create(
            user_account=locked_user,
            train_prediction=prediction,
            amount=amount,
            direction=direction,
            predicted_arrival_time=prediction.predicted_arrival,
        )

    logger.info("bet_placed", bet_id=bet.id, user_id=user.id, amount=amount, direction=direction)
    return Response(_bet_data(bet), status=status.HTTP_201_CREATED)


@api_view(["GET"])
def active_bet(request: Request) -> Response:
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    bet = (
        Bet.objects.filter(user_account=user, status=Bet.Status.ACTIVE)
        .select_related("train_prediction__station")
        .first()
    )
    return Response(_bet_data(bet) if bet else None)


@api_view(["GET"])
def bet_history(request: Request) -> Response:
    user = get_current_user(request)
    if user is None:
        return error_response("Not authenticated.", status_code=401)

    try:
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except (TypeError, ValueError):
        return error_response("page and page_size must be positive integers.")

    qs = (
        Bet.objects.filter(user_account=user, status__in=RESOLVED_STATUSES)
        .select_related("train_prediction__station")
        .order_by("-placed_at")
    )

    count = qs.count()
    offset = (page - 1) * page_size
    results = qs[offset : offset + page_size]

    return Response({
        "count": count,
        "page": page,
        "page_size": page_size,
        "results": [
            {**_bet_data(b), "token_delta": _token_delta(b)}
            for b in results
        ],
    })
