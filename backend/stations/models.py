from django.db import models


class Station(models.Model):
    id: int
    mbta_stop_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    # JSON array of MBTA route IDs serving this station, e.g. ["Red", "Green-B"]
    route_ids = models.JSONField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "station"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name
