from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0004_gameplayer_placement"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="is_finished",
            field=models.BooleanField(default=False),
        ),
    ]
