from django.db import migrations, models


DEFAULT_BABA_CHARACTERS = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "はひふへほまみむめもやゆよらりるれろわをん"
)


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0005_room_is_started"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="baba_characters",
            field=models.CharField(
                default=DEFAULT_BABA_CHARACTERS,
                max_length=64,
            ),
        ),
    ]
