from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0007_gamestamp"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="baba_challenger",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="baba_challenge_sessions",
                to="game.gameplayer",
            ),
        ),
    ]
