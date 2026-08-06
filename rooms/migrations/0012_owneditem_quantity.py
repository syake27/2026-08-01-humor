from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0011_alter_owneditem_item_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="owneditem",
            name="quantity",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name="owneditem",
            constraint=models.CheckConstraint(
                check=models.Q(quantity__gte=1, quantity__lte=99),
                name="owned_item_quantity_between_1_and_99",
            ),
        ),
    ]
