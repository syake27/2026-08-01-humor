from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0006_gamesession_coin_rewards_granted"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameStamp",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("stamp_code", models.CharField(max_length=50)),
                ("stamp_name", models.CharField(max_length=50)),
                ("stamp_icon", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stamps",
                        to="game.gameplayer",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stamps",
                        to="game.gamesession",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
