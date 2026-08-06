from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0010_gamesession_baba_reveal"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="baba_reveal_mode",
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
