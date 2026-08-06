from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0015_gamecarduse"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="card_reveal_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
