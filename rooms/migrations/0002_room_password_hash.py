from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="password_hash",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
