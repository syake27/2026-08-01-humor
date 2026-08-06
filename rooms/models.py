from django.db import models


DEFAULT_BABA_CHARACTERS = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "はひふへほまみむめもやゆよらりるれろわをん"
)


class UserProfile(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="shiritori_profile",
    )
    coins = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}: {self.coins} coins"


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
    current_players = models.PositiveSmallIntegerField(default=0)
    time_limit = models.PositiveSmallIntegerField(default=60)
    theme = models.CharField(max_length=80, blank=True)
    baba_characters = models.CharField(
        max_length=64,
        default=DEFAULT_BABA_CHARACTERS,
    )
    has_password = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    is_started = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.room_id


class RoomParticipant(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="room_participations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room", "user"],
                name="unique_room_participant",
            ),
        ]

    def __str__(self):
        return f"{self.room.room_id}: {self.user.username}"
