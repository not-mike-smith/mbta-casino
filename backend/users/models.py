from django.db import models


class UserAccount(models.Model):
    email = models.EmailField(unique=True)
    token_balance = models.IntegerField(default=1000)
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_account"
        indexes = [
            models.Index(fields=["session_key"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(token_balance__gte=0),
                name="user_account_token_balance_non_negative",
            ),
        ]

    def __str__(self):
        return self.email
