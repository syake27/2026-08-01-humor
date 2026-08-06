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
    rating = models.PositiveIntegerField(default=1000)

    def __str__(self):
        return f"{self.user.username}: {self.coins} coins"


class OwnedItem(models.Model):
    ITEM_TYPES = [
        ("avatar", "アバター"),
        ("card", "カード"),
        ("frame", "フレーム"),
        ("stamp", "スタンプ"),
        ("title", "称号"),
    ]

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="owned_items",
    )
    item_code = models.CharField(max_length=50)
    item_type = models.CharField(max_length=12, choices=ITEM_TYPES)
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=20, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    is_equipped = models.BooleanField(default=False)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item_type", "acquired_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item_code"],
                name="unique_owned_item_per_user",
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=1, quantity__lte=99),
                name="owned_item_quantity_between_1_and_99",
            ),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.name}"


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
    is_ranked = models.BooleanField(default=False)
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


class RankMatchEntry(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="rank_match_entry",
    )
    room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="rank_match_entries",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["joined_at", "id"]

    def __str__(self):
        state = self.room.room_id if self.room_id else "waiting"
        return f"{self.user.username}: {state}"
