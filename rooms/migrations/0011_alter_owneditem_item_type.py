from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0010_room_is_ranked_rankmatchentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="owneditem",
            name="item_type",
            field=models.CharField(
                choices=[
                    ("avatar", "アバター"),
                    ("card", "カード"),
                    ("frame", "フレーム"),
                    ("stamp", "スタンプ"),
                    ("title", "称号"),
                ],
                max_length=12,
            ),
        ),
    ]
