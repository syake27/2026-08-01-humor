from django.db import models


class GameSession(models.Model):
    room = models.OneToOneField(
        "rooms.Room",
        on_delete=models.CASCADE,
        related_name="game_session",
    )
    current_turn_order = models.PositiveSmallIntegerField(default=0)
    turn_number = models.PositiveIntegerField(default=1)
    current_letter = models.CharField(max_length=1, default="き")
    baba_letter = models.CharField(max_length=1, blank=True)
    is_finished = models.BooleanField(default=False)
    coin_rewards_granted = models.BooleanField(default=False)
    rating_rewards_granted = models.BooleanField(default=False)
    baba_challenger = models.ForeignKey(
        "game.GamePlayer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="baba_challenge_sessions",
    )
    baba_guess_preview = models.CharField(max_length=1, blank=True)
    baba_reveal_correct = models.BooleanField(null=True, blank=True)
    baba_reveal_until = models.DateTimeField(null=True, blank=True)
    baba_reveal_mode = models.CharField(max_length=10, blank=True)
    turn_started_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Game {self.room.room_id}"


class GamePlayer(models.Model):
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        "auth.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="game_players",
    )
    display_name = models.CharField(max_length=150)
    title = models.CharField(max_length=40, default="はじめての一歩")
    remaining_seconds = models.PositiveIntegerField(default=60)
    is_alive = models.BooleanField(default=True)
    placement = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_before = models.PositiveIntegerField(null=True, blank=True)
    rating_change = models.SmallIntegerField(default=0)
    rating_after = models.PositiveIntegerField(null=True, blank=True)
    turn_order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["turn_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "turn_order"],
                name="unique_game_turn_order",
            ),
        ]

    def __str__(self):
        return self.display_name


class GameWord(models.Model):
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="words",
    )
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="words",
    )
    word = models.CharField(max_length=30)
    turn_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["turn_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "word"],
                name="unique_word_per_game",
            ),
        ]

    def __str__(self):
        return self.word


class GameStamp(models.Model):
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name="stamps",
    )
    player = models.ForeignKey(
        GamePlayer,
        on_delete=models.CASCADE,
        related_name="stamps",
    )
    stamp_code = models.CharField(max_length=50)
    stamp_name = models.CharField(max_length=50)
    stamp_icon = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.player.display_name}: {self.stamp_name}"
