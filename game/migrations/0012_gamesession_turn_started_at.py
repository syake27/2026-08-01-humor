from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0011_gamesession_baba_reveal_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="turn_started_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
