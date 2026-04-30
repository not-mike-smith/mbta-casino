from django.db import models


class Bet(models.Model):
    id: int

    class Direction(models.TextChoices):
        BEFORE = "BEFORE"
        AFTER = "AFTER"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        WON = "WON"
        LOST = "LOST"
        PUSH = "PUSH"
        VOID = "VOID"

    user_account = models.ForeignKey(
        "users.UserAccount",
        on_delete=models.PROTECT,
        related_name="bets",
    )
    train_prediction = models.ForeignKey(
        "mbta.TrainPrediction",
        on_delete=models.PROTECT,
        related_name="bets",
    )
    amount = models.IntegerField()
    direction = models.CharField(max_length=6, choices=Direction.choices)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.ACTIVE)
    # Snapshot of predicted arrival at the moment the bet was placed.
    # This is what the bet resolves against — not the live prediction.
    predicted_arrival_time = models.DateTimeField()
    actual_arrival_time = models.DateTimeField(null=True, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bet"
        indexes = [
            models.Index(fields=["user_account"]),
            models.Index(fields=["train_prediction"]),
            models.Index(fields=["status"]),
            models.Index(fields=["placed_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="bet_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Bet({self.user_account}, {self.direction}, {self.amount}, {self.status})"
