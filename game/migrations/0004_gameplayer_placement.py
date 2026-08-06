from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0003_gamesession_baba_letter"),
    ]

    operations = [
        migrations.AddField(
            model_name="gameplayer",
            name="placement",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
