from .models import OwnedItem, UserProfile


RANK_TIERS = [
    ("beginner-1", "ビギナー I", 1000, "◆"),
    ("beginner-2", "ビギナー II", 1100, "◆"),
    ("beginner-3", "ビギナー III", 1200, "◆"),
    ("bronze", "ブロンズ", 1300, "♢"),
    ("silver", "シルバー", 1500, "◇"),
    ("gold", "ゴールド", 1700, "★"),
    ("platinum", "プラチナ", 1900, "✦"),
    ("diamond", "ダイヤモンド", 2100, "◆"),
    ("master", "マスター", 2400, "♛"),
    ("humor-king", "ユーモア王", 2800, "♛"),
]


def rank_title_code(rank_code):
    return f"title_rank_{rank_code.replace('-', '_')}"


def grant_rank_titles(user, rating=None):
    if rating is None:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        rating = profile.rating

    granted_codes = []
    # 全アカウントは1000レート開始なので、降格後も初期ランク称号を保持する。
    achieved_rating = max(1000, rating)
    for rank_code, rank_name, minimum_rate, icon in RANK_TIERS:
        if achieved_rating < minimum_rate:
            continue
        item_code = rank_title_code(rank_code)
        _, created = OwnedItem.objects.get_or_create(
            user=user,
            item_code=item_code,
            defaults={
                "item_type": "title",
                "name": rank_name,
                "icon": icon,
                "is_equipped": False,
            },
        )
        if created:
            granted_codes.append(item_code)
    return granted_codes


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
    "stamp_coconut": "rooms/images/stamps/stamp_coconut_good.png",
    "stamp_coconut_battle": "rooms/images/stamps/stamp_coconut_battle.png",
    "stamp_coconut_sad": "rooms/images/stamps/stamp_coconut_sad.png",
    "stamp_coconut_happy": "rooms/images/stamps/stamp_coconut_happy.png",
    "stamp_coconut_peace": "rooms/images/stamps/stamp_coconut_peace.png",
}

ITEM_DISPLAY_NAMES = {
    "card_help_limited": "レートブースト",
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
    grant_rank_titles(user)


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
