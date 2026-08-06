from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0008_gamesession_baba_challenger"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="baba_guess_preview",
            field=models.CharField(blank=True, max_length=1),
        ),
    ]
