from django.db import migrations, models


def reset_unjoined_room_counts(apps, schema_editor):
    room_model = apps.get_model("rooms", "Room")
    room_model.objects.filter(current_players=1).update(current_players=0)


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0002_room_password_hash"),
    ]

    operations = [
        migrations.AlterField(
            model_name="room",
            name="current_players",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(
            reset_unjoined_room_counts,
            migrations.RunPython.noop,
        ),
    ]
