from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0009_gamesession_baba_guess_preview"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="baba_reveal_correct",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="baba_reveal_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
