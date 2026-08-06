from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0007_userprofile"),
        ("game", "0005_gamesession_is_finished"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="coin_rewards_granted",
            field=models.BooleanField(default=False),
        ),
    ]
