from .models import OwnedItem


DEFAULT_OWNED_ITEMS = [
    ("default_penguin", "avatar", "ペンギン", "🐧", True),
    ("default_sky_frame", "frame", "スカイリング", "◯", True),
    ("default_fight_stamp", "stamp", "ファイトスタンプ", "💪", True),
    ("default_first_step", "title", "はじめての一歩", "★", True),
]

ITEM_IMAGE_PATHS = {
    "avatar_palm_limited": "rooms/images/icons/avatar_palm_limited.png",
    "card_help_limited": "rooms/images/cards/card_reta_up.png",
    "card_skip": "rooms/images/cards/card_skip.png",
    "card_reverse": "rooms/images/cards/card_reverse.png",
    "card_time_plus": "rooms/images/cards/card_time_plus.png",
    "card_time_minus": "rooms/images/cards/card_time_minus.png",
    "frame_tropical_beach": "rooms/images/frames/frame_tropical_beach.png",
    "stamp_coconut": "rooms/images/stamps/stamp_coconut.png",
}

FRAME_STYLE_CLASSES = {
    "default_sky_frame": "frame-sky",
    "frame_sunset": "frame-sunset",
    "frame_gold": "frame-gold",
    "frame_forest": "frame-forest",
    "frame_tropical_beach": "frame-tropical-beach",
}


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


def _format_customization(equipped):
    avatar = equipped.get("avatar")
    frame = equipped.get("frame")
    stamp = equipped.get("stamp")
    title = equipped.get("title")
    return {
        "avatar_code": avatar.item_code if avatar else "default_penguin",
        "avatar_name": avatar.name if avatar else "ペンギン",
        "avatar_icon": avatar.icon if avatar and avatar.icon else "🐧",
        "avatar_image_path": (
            ITEM_IMAGE_PATHS.get(avatar.item_code, "") if avatar else ""
        ),
        "frame_code": frame.item_code if frame else "default_sky_frame",
        "frame_class": FRAME_STYLE_CLASSES.get(
            frame.item_code if frame else "default_sky_frame",
            "frame-sky",
        ),
        "frame_image_path": (
            ITEM_IMAGE_PATHS.get(frame.item_code, "") if frame else ""
        ),
        "stamp_icon": stamp.icon if stamp and stamp.icon else "💪",
        "stamp_image_path": (
            ITEM_IMAGE_PATHS.get(stamp.item_code, "") if stamp else ""
        ),
        "stamp_name": stamp.name if stamp else "ファイトスタンプ",
        "title_name": title.name if title else "はじめての一歩",
    }


def get_equipped_customizations(user_ids):
    user_ids = [user_id for user_id in user_ids if user_id]
    equipped_by_user = {user_id: {} for user_id in user_ids}
    for item in OwnedItem.objects.filter(
        user_id__in=user_ids,
        is_equipped=True,
    ):
        equipped_by_user.setdefault(item.user_id, {})[item.item_type] = item
    return {
        user_id: _format_customization(equipped_by_user.get(user_id, {}))
        for user_id in user_ids
    }


def get_equipped_customization(user):
    ensure_default_owned_items(user)
    return get_equipped_customizations([user.id])[user.id]
