from django.db import models


class TrainPrediction(models.Model):
    station = models.ForeignKey(
        "stations.Station",
        on_delete=models.PROTECT,
        related_name="predictions",
    )
    mbta_prediction_id = models.CharField(max_length=128, unique=True)
    mbta_trip_id = models.CharField(max_length=128)
    mbta_route_id = models.CharField(max_length=32)
    direction_id = models.SmallIntegerField()
    stop_sequence = models.IntegerField(null=True, blank=True)
    predicted_arrival = models.DateTimeField()
    has_arrived = models.BooleanField(default=False)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "train_prediction"
        indexes = [
            models.Index(fields=["station", "mbta_route_id", "direction_id"]),
            models.Index(fields=["has_arrived"]),
            models.Index(fields=["updated_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(direction_id__in=[0, 1]),
                name="train_prediction_direction_id_valid",
            ),
        ]

    def __str__(self):
        return f"{self.mbta_route_id} → {self.station} at {self.predicted_arrival}"
