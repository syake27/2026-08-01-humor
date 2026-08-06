from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0013_rank_rating_rewards"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="skip_next_turn",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="turn_direction",
            field=models.SmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="gameplayer",
            name="rate_boost_active",
            field=models.BooleanField(default=False),
        ),
    ]
