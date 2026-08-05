import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="current_letter",
            field=models.CharField(default="き", max_length=1),
        ),
        migrations.CreateModel(
            name="GameWord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("word", models.CharField(max_length=30)),
                ("turn_number", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="words", to="game.gameplayer")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="words", to="game.gamesession")),
            ],
            options={"ordering": ["turn_number", "id"]},
        ),
        migrations.AddConstraint(
            model_name="gameword",
            constraint=models.UniqueConstraint(fields=("session", "word"), name="unique_word_per_game"),
        ),
    ]
