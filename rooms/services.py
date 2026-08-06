from .models import OwnedItem


DEFAULT_OWNED_ITEMS = [
    ("default_penguin", "avatar", "ペンギン", "🐧", True),
    ("default_sky_frame", "frame", "スカイリング", "◯", True),
    ("default_fight_stamp", "stamp", "ファイトスタンプ", "💪", True),
    ("default_first_step", "title", "はじめての一歩", "★", True),
]


def ensure_default_owned_items(user):
    for item_code, item_type, name, icon, is_equipped in DEFAULT_OWNED_ITEMS:
        OwnedItem.objects.get_or_create(
            user=user,
            item_code=item_code,
            defaults={
                "item_type": item_type,
                "name": name,
                "icon": icon,
                "is_equipped": is_equipped,
            },
        )
