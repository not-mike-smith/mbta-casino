from datetime import datetime

import structlog
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import Bet

logger = structlog.get_logger()


def resolve_bets_for_arrived_predictions(prediction_ids: list[int], actual_arrival: datetime) -> None:
    """Resolve all active bets against a set of just-arrived predictions."""
    bets = (
        Bet.objects.filter(
            train_prediction_id__in=prediction_ids,
            status=Bet.Status.ACTIVE,
        )
        .select_related("user_account")
    )
    for bet in bets:
        _resolve_bet(bet, actual_arrival)


def _resolve_bet(bet: Bet, actual_arrival: datetime) -> None:
    delta_seconds = (actual_arrival - bet.predicted_arrival_time).total_seconds()

    if abs(delta_seconds) <= settings.PUSH_TOLERANCE_SECONDS:
        outcome = Bet.Status.PUSH
    elif delta_seconds < 0:
        # Train arrived before the predicted time.
        outcome = Bet.Status.WON if bet.direction == Bet.Direction.BEFORE else Bet.Status.LOST
    else:
        # Train arrived after the predicted time.
        outcome = Bet.Status.WON if bet.direction == Bet.Direction.AFTER else Bet.Status.LOST

    if outcome == Bet.Status.WON:
        credit = bet.amount * 2
    elif outcome == Bet.Status.PUSH:
        credit = bet.amount
    else:
        credit = 0

    bet.status = outcome
    bet.resolved_at = timezone.now()
    bet.actual_arrival_time = actual_arrival
    bet.save(update_fields=["status", "resolved_at", "actual_arrival_time"])

    if credit > 0:
        # F() expression ensures the increment is atomic at the DB level.
        bet.user_account.token_balance = F("token_balance") + credit
        bet.user_account.save(update_fields=["token_balance", "updated_at"])

    logger.info(
        "bet_resolved",
        bet_id=bet.id,
        user_id=bet.user_account_id,
        outcome=outcome,
        credit=credit,
        delta_seconds=int(delta_seconds),
    )
