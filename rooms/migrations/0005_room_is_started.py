from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0004_roomparticipant"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="is_started",
            field=models.BooleanField(default=False),
        ),
    ]
