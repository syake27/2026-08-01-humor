from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0013_rename_rate_boost_card"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopPurchaseHistory",
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
                            ("card", "カード"),
                            ("frame", "フレーム"),
                            ("stamp", "スタンプ"),
                            ("title", "称号"),
                        ],
                        max_length=12,
                    ),
                ),
                ("item_name", models.CharField(max_length=50)),
                ("quantity", models.PositiveSmallIntegerField(default=1)),
                ("coins_spent", models.PositiveIntegerField()),
                ("purchased_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shop_purchase_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-purchased_at", "-id"]},
        ),
    ]
