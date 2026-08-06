from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0008_owneditem"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="rating",
            field=models.PositiveIntegerField(default=1000),
        ),
    ]
