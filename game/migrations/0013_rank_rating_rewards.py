from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0012_gamesession_turn_started_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="rating_rewards_granted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gameplayer",
            name="rating_after",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gameplayer",
            name="rating_before",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gameplayer",
            name="rating_change",
            field=models.SmallIntegerField(default=0),
        ),
    ]
