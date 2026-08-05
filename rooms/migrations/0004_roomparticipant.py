import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rooms", "0003_room_current_players_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoomParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="rooms.room")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="room_participations", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="roomparticipant",
            constraint=models.UniqueConstraint(fields=("room", "user"), name="unique_room_participant"),
        ),
    ]
