from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0006_room_baba_characters"),
        ("game", "0002_game_word_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="baba_letter",
            field=models.CharField(blank=True, max_length=1),
        ),
    ]
