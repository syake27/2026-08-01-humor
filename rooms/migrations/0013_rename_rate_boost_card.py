from django.db import migrations


def rename_rate_boost_card(apps, schema_editor):
    owned_item = apps.get_model("rooms", "OwnedItem")
    owned_item.objects.filter(item_code="card_help_limited").update(
        name="レートブースト"
    )


def restore_old_card_name(apps, schema_editor):
    owned_item = apps.get_model("rooms", "OwnedItem")
    owned_item.objects.filter(item_code="card_help_limited").update(
        name="おたすけカード"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0012_owneditem_quantity"),
    ]

    operations = [
        migrations.RunPython(rename_rate_boost_card, restore_old_card_name),
    ]
