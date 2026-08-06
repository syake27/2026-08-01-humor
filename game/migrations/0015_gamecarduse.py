from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0014_card_effect_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameCardUse",
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
                ("card_code", models.CharField(max_length=50)),
                ("card_name", models.CharField(max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="card_uses",
                        to="game.gameplayer",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="card_uses",
                        to="game.gamesession",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
