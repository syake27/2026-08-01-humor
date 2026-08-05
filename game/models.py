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
