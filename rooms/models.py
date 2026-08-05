from django.db import models


class Room(models.Model):
    room_id = models.CharField(max_length=8, unique=True)
    host = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosted_rooms",
    )
    max_players = models.PositiveSmallIntegerField(default=4)
    current_players = models.PositiveSmallIntegerField(default=1)
    time_limit = models.PositiveSmallIntegerField(default=60)
    theme = models.CharField(max_length=80, blank=True)
    has_password = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.room_id
