import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rooms", "0005_room_is_started"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("current_turn_order", models.PositiveSmallIntegerField(default=0)),
                ("turn_number", models.PositiveIntegerField(default=1)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("room", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="game_session", to="rooms.room")),
            ],
        ),
        migrations.CreateModel(
            name="GamePlayer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(max_length=150)),
                ("title", models.CharField(default="はじめての一歩", max_length=40)),
                ("remaining_seconds", models.PositiveIntegerField(default=60)),
                ("is_alive", models.BooleanField(default=True)),
                ("turn_order", models.PositiveSmallIntegerField()),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="players", to="game.gamesession")),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="game_players", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["turn_order"]},
        ),
        migrations.AddConstraint(
            model_name="gameplayer",
            constraint=models.UniqueConstraint(fields=("session", "turn_order"), name="unique_game_turn_order"),
        ),
    ]
