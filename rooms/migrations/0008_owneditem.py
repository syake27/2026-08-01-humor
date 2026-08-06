from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rooms", "0007_userprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="OwnedItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("item_code", models.CharField(max_length=50)),
                (
                    "item_type",
                    models.CharField(
                        choices=[
                            ("avatar", "アバター"),
                            ("frame", "フレーム"),
                            ("stamp", "スタンプ"),
                            ("title", "称号"),
                        ],
                        max_length=12,
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("icon", models.CharField(blank=True, max_length=20)),
                ("is_equipped", models.BooleanField(default=False)),
                ("acquired_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["item_type", "acquired_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="owneditem",
            constraint=models.UniqueConstraint(
                fields=("user", "item_code"),
                name="unique_owned_item_per_user",
            ),
        ),
    ]
