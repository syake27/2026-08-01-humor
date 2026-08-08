import re
import secrets
import string
from datetime import timedelta
from math import ceil
from urllib.parse import urlencode

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    DEFAULT_BABA_CHARACTERS,
    OwnedItem,
    RankMatchEntry,
    Room,
    RoomParticipant,
    ShopPurchaseHistory,
    UserProfile,
)
from .services import (
    ITEM_IMAGE_PATHS,
    RANK_TIERS,
    ensure_default_owned_items,
    get_equipped_customization,
    rank_title_code,
)

ITEM_CATALOG = [
    ("default_penguin", "avatar", "ペンギン", "🐧", "アカウント登録時に入手"),
    (
        "avatar_palm_limited",
        "avatar",
        "トロピカルパーム",
        "",
        "期間限定ショップで購入",
    ),
    ("avatar_cat", "avatar", "ねこ", "🐱", "ショップで購入"),
    ("avatar_robot", "avatar", "ロボット", "🤖", "対戦を10回プレイ"),
    ("avatar_alien", "avatar", "宇宙人", "👾", "ショップで購入"),
    (
        "card_help_limited",
        "card",
        "レートブースト",
        "⚡",
        "期間限定ショップで購入",
    ),
    (
        "card_skip",
        "card",
        "スキップカード",
        "⏭️",
        "期間限定ショップで購入",
    ),
    (
        "card_reverse",
        "card",
        "リバースカード",
        "🔄",
        "期間限定ショップで購入",
    ),
    (
        "card_time_plus",
        "card",
        "タイムプラス",
        "⏱️",
        "期間限定ショップで購入",
    ),
    (
        "card_time_minus",
        "card",
        "タイムマイナス",
        "⏳",
        "期間限定ショップで購入",
    ),
    ("default_sky_frame", "frame", "スカイリング", "◯", "アカウント登録時に入手"),
    ("frame_sunset", "frame", "サンセットリング", "◯", "ショップで購入"),
    ("frame_gold", "frame", "ゴールドリング", "◯", "1位を10回獲得"),
    ("frame_forest", "frame", "フォレストリング", "◯", "ショップで購入"),
    (
        "frame_tropical_beach",
        "frame",
        "トロピカルビーチ",
        "◯",
        "期間限定ショップで購入",
    ),
    ("default_fight_stamp", "stamp", "ファイトスタンプ", "●", "アカウント登録時に入手"),
    ("stamp_nice", "stamp", "ナイス！", "👍", "ショップで購入"),
    ("stamp_thanks", "stamp", "ありがとう", "✨", "対戦を5回プレイ"),
    ("stamp_surprise", "stamp", "びっくり", "😲", "ショップで購入"),
    (
        "stamp_summer_set",
        "stamp",
        "サマースタンプ",
        "🏖️",
        "期間限定ショップで購入",
    ),
    (
        "stamp_coconut",
        "stamp",
        "ココナッツスタンプ",
        "",
        "期間限定ショップで購入",
    ),
    ("stamp_coconut_battle", "stamp", "バトルスタンプ", "", "ショップで購入"),
    ("stamp_coconut_sad", "stamp", "かなしいスタンプ", "", "ショップで購入"),
    ("stamp_coconut_happy", "stamp", "ハッピースタンプ", "", "ショップで購入"),
    ("stamp_coconut_peace", "stamp", "ピーススタンプ", "", "ショップで購入"),
    ("stamp_poop", "stamp", "うんちスタンプ", "", "ショップで購入"),
    ("stamp_special_wait", "stamp", "まだかなー？", "", "ショップで購入"),
    ("stamp_special_ma", "stamp", "ま？", "", "ショップで購入"),
    ("stamp_special_amazon", "stamp", "Amazon！", "", "ショップで購入"),
    ("default_first_step", "title", "はじめての一歩", "★", "アカウント登録時に入手"),
    ("title_word_master", "title", "ことばマスター", "★", "100個の言葉を回答"),
    ("title_baba_hunter", "title", "ババハンター", "◆", "ショップで購入"),
    ("title_shiritori_king", "title", "しりとり王", "♛", "1位を25回獲得"),
]

ITEM_CATALOG.extend(
    (
        rank_title_code(rank_code),
        "title",
        rank_name,
        icon,
        f"{minimum_rate}レート到達",
    )
    for rank_code, rank_name, minimum_rate, icon in RANK_TIERS
)

SHOP_PRODUCT_PRICES = {
    "avatar_palm_limited": 800,
    "card_help_limited": 300,
    "card_skip": 300,
    "card_reverse": 300,
    "card_time_plus": 300,
    "card_time_minus": 300,
    "stamp_coconut": 400,
    "stamp_coconut_battle": 400,
    "stamp_coconut_sad": 400,
    "stamp_coconut_happy": 400,
    "stamp_coconut_peace": 400,
    "stamp_poop": 400,
    "stamp_special_wait": 500,
    "stamp_special_ma": 500,
    "stamp_special_amazon": 500,
    "title_baba_hunter": 1000,
    "frame_tropical_beach": 500,
}

RANK_MATCH_PLAYERS = 4
RANK_MATCH_COUNTDOWN_SECONDS = 3
RANK_MATCH_ACTIVE_SECONDS = 20


def _clean_baba_characters(value):
    """50音から選ばれた文字を、重複のない文字列として保存する。"""
    selected = []
    for character in value:
        if character in DEFAULT_BABA_CHARACTERS and character not in selected:
            selected.append(character)
    return "".join(selected) or DEFAULT_BABA_CHARACTERS


def _get_battle_stats(user):
    from game.models import GamePlayer

    recent_results = list(
        GamePlayer.objects.filter(
            user=user,
            session__is_finished=True,
            placement__isnull=False,
        )
        .select_related("session__room")
        .annotate(word_count=Count("words"))
        .order_by("-session__started_at", "-id")
    )
    battle_count = len(recent_results)
    win_count = sum(player.placement == 1 for player in recent_results)
    current_win_streak = 0
    for player in recent_results:
        if player.placement != 1:
            break
        current_win_streak += 1

    best_win_streak = 0
    running_win_streak = 0
    for player in recent_results:
        if player.placement == 1:
            running_win_streak += 1
            best_win_streak = max(best_win_streak, running_win_streak)
        else:
            running_win_streak = 0
    rank_counts = {
        placement: sum(
            player.placement == placement for player in recent_results
        )
        for placement in range(1, 5)
    }
    return {
        "battle_count": battle_count,
        "win_count": win_count,
        "win_rate": round(win_count / battle_count * 100, 1) if battle_count else 0,
        "current_win_streak": current_win_streak,
        "best_win_streak": best_win_streak,
        "total_words": sum(player.word_count for player in recent_results),
        "best_rank": min(
            (player.placement for player in recent_results),
            default=None,
        ),
        "rank_counts": rank_counts,
        "recent_results": recent_results[:20],
    }


def _get_rank_data(rating):
    current_index = 0
    for index, (_, _, minimum_rate, _) in enumerate(RANK_TIERS):
        if rating >= minimum_rate:
            current_index = index

    rank_tiers = []
    for index, (code, name, minimum_rate, icon) in enumerate(RANK_TIERS):
        next_minimum = (
            RANK_TIERS[index + 1][2]
            if index + 1 < len(RANK_TIERS)
            else None
        )
        rank_tiers.append(
            {
                "code": code,
                "name": name,
                "minimum_rate": minimum_rate,
                "maximum_rate": next_minimum - 1 if next_minimum else None,
                "icon": icon,
                "is_current": index == current_index,
            }
        )

    current_rank = rank_tiers[current_index]
    next_rank = (
        rank_tiers[current_index + 1]
        if current_index + 1 < len(rank_tiers)
        else None
    )
    if next_rank:
        rank_span = next_rank["minimum_rate"] - current_rank["minimum_rate"]
        progress = min(
            100,
            max(0, (rating - current_rank["minimum_rate"]) / rank_span * 100),
        )
    else:
        progress = 100

    return {
        "rating": rating,
        "current_rank": current_rank,
        "next_rank": next_rank,
        "progress": round(progress, 1),
        "rate_to_next": (
            max(0, next_rank["minimum_rate"] - rating) if next_rank else 0
        ),
        "rank_tiers": rank_tiers,
    }


def _add_room_participant(room_id, user):
    with transaction.atomic():
        room = Room.objects.select_for_update().get(pk=room_id)
        participant = RoomParticipant.objects.filter(room=room, user=user).first()
        participant_count = room.participants.count()

        if participant:
            room.current_players = participant_count
            room.save(update_fields=["current_players"])
            return room, True

        if participant_count >= room.max_players:
            return room, False

        RoomParticipant.objects.create(room=room, user=user)
        room.current_players = participant_count + 1
        room.save(update_fields=["current_players"])
        return room, True


def _generate_room_id():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        room_id = "".join(secrets.choice(alphabet) for _ in range(4))
        if not Room.objects.filter(room_id=room_id).exists():
            return room_id


def _join_rank_queue(user):
    """待機を更新し、先着4人が揃ったらランクルームを確定する。"""
    now = timezone.now()
    active_since = now - timedelta(seconds=RANK_MATCH_ACTIVE_SECONDS)

    with transaction.atomic():
        entry = (
            RankMatchEntry.objects.select_for_update()
            .select_related("room")
            .filter(user=user)
            .first()
        )
        if entry and entry.room_id:
            game_session = getattr(entry.room, "game_session", None)
            if game_session and game_session.is_finished:
                entry.delete()
                entry = None

        if entry is None:
            entry = RankMatchEntry.objects.create(user=user)
        elif entry.room_id is None:
            entry.last_seen_at = now
            entry.save(update_fields=["last_seen_at"])

        if entry.room_id:
            return entry

        RankMatchEntry.objects.filter(
            room__isnull=True,
            last_seen_at__lt=active_since,
        ).exclude(pk=entry.pk).delete()

        waiting_entries = list(
            RankMatchEntry.objects.select_for_update()
            .filter(room__isnull=True, last_seen_at__gte=active_since)
            .select_related("user")
            .order_by("joined_at", "id")[:RANK_MATCH_PLAYERS]
        )
        if len(waiting_entries) < RANK_MATCH_PLAYERS:
            return entry

        room = Room.objects.create(
            room_id=_generate_room_id(),
            host=waiting_entries[0].user,
            max_players=RANK_MATCH_PLAYERS,
            current_players=RANK_MATCH_PLAYERS,
            time_limit=60,
            is_ranked=True,
        )
        RoomParticipant.objects.bulk_create(
            [
                RoomParticipant(room=room, user=waiting_entry.user)
                for waiting_entry in waiting_entries
            ]
        )
        waiting_ids = [waiting_entry.pk for waiting_entry in waiting_entries]
        RankMatchEntry.objects.filter(pk__in=waiting_ids).update(
            room=room,
            matched_at=now,
        )
        return RankMatchEntry.objects.select_related("room").get(pk=entry.pk)


def _rank_match_state(entry):
    if not entry.room_id:
        active_since = timezone.now() - timedelta(seconds=RANK_MATCH_ACTIVE_SECONDS)
        waiting_count = RankMatchEntry.objects.filter(
            room__isnull=True,
            last_seen_at__gte=active_since,
        ).count()
        return {
            "matched": False,
            "waiting_count": min(waiting_count, RANK_MATCH_PLAYERS),
            "countdown": None,
            "is_started": False,
            "game_url": "",
        }

    room = entry.room
    start_at = entry.matched_at + timedelta(seconds=RANK_MATCH_COUNTDOWN_SECONDS)
    countdown = max(0, ceil((start_at - timezone.now()).total_seconds()))
    if countdown == 0 and not room.is_started:
        with transaction.atomic():
            room = Room.objects.select_for_update().get(pk=room.pk)
            if not room.is_started:
                from game.services import ensure_game_session

                ensure_game_session(room)
                room.is_started = True
                room.save(update_fields=["is_started"])

    game_url = f'{reverse("game:game")}?{urlencode({"room_id": room.room_id})}'
    return {
        "matched": True,
        "waiting_count": RANK_MATCH_PLAYERS,
        "countdown": countdown,
        "is_started": room.is_started,
        "game_url": game_url if room.is_started else "",
    }


def home(request):
    return render(request, "rooms/home.html")


def match(request):
    return render(request, "rooms/match.html")


@login_required(login_url="rooms:login")
def normal_match(request):
    active_since = timezone.now() - timedelta(hours=2)
    search_query = request.GET.get("q", "").strip().upper()[:8]
    rooms = (
        Room.objects.filter(
            is_active=True,
            is_started=False,
            is_ranked=False,
            created_at__gte=active_since,
        )
        .select_related("host")
        .annotate(participant_count=Count("participants"))
    )
    if search_query:
        rooms = rooms.filter(room_id__icontains=search_query)
    return render(
        request,
        "rooms/normal_match.html",
        {"rooms": rooms, "search_query": search_query},
    )


@login_required(login_url="rooms:login")
def normal_match_status(request):
    active_since = timezone.now() - timedelta(hours=2)
    rooms = Room.objects.filter(
        is_active=True,
        is_started=False,
        is_ranked=False,
        created_at__gte=active_since,
    ).annotate(participant_count=Count("participants"))
    return JsonResponse(
        {
            "rooms": [
                {
                    "room_id": room.room_id,
                    "current_players": room.participant_count,
                    "max_players": room.max_players,
                }
                for room in rooms
            ]
        }
    )


@login_required(login_url="rooms:login")
def join_normal_room(request, room_id):
    active_since = timezone.now() - timedelta(hours=2)
    room = get_object_or_404(
        Room,
        room_id=room_id.upper(),
        is_active=True,
        is_started=False,
        is_ranked=False,
        created_at__gte=active_since,
    )

    if (
        room.participants.count() >= room.max_players
        and not RoomParticipant.objects.filter(
            room=room,
            user=request.user,
        ).exists()
    ):
        return redirect("rooms:normal_match")

    access_key = f"room_access_{room.room_id}"
    if not room.has_password:
        room, joined = _add_room_participant(room.pk, request.user)
        if not joined:
            return redirect("rooms:normal_match")
        request.session[access_key] = True
        query = urlencode(
            {"room_id": room.room_id, "members": room.max_players, "source": "normal"}
        )
        return redirect(f"/wait/?{query}")

    error = ""
    if request.method == "POST":
        password = request.POST.get("password", "")
        if check_password(password, room.password_hash):
            room, joined = _add_room_participant(room.pk, request.user)
            if not joined:
                return redirect("rooms:normal_match")
            request.session[access_key] = True
            query = urlencode(
                {
                    "room_id": room.room_id,
                    "members": room.max_players,
                    "source": "normal",
                }
            )
            return redirect(f"/wait/?{query}")
        error = "合言葉が違います。"

    return render(
        request,
        "rooms/room_password.html",
        {"room": room, "error": error},
    )


@require_POST
@login_required(login_url="rooms:login")
def leave_normal_room(request, room_id):
    room = get_object_or_404(Room, room_id=room_id.upper())
    with transaction.atomic():
        locked_room = Room.objects.select_for_update().get(pk=room.pk)
        RoomParticipant.objects.filter(
            room=locked_room,
            user=request.user,
        ).delete()
        locked_room.current_players = locked_room.participants.count()
        locked_room.save(update_fields=["current_players"])

    request.session.pop(f"room_access_{room.room_id}", None)
    return redirect("rooms:normal_match")


@require_POST
@login_required(login_url="rooms:login")
def start_room(request, room_id):
    with transaction.atomic():
        room = get_object_or_404(
            Room.objects.select_for_update(),
            room_id=room_id.upper(),
            is_active=True,
        )
        if room.host_id != request.user.id:
            return HttpResponseForbidden("ルーム作成者だけがゲームを開始できます。")
        from game.services import ensure_game_session

        ensure_game_session(room)
        room.is_started = True
        room.save(update_fields=["is_started"])
    game_url = f'{reverse("game:game")}?{urlencode({"room_id": room.room_id})}'
    return redirect(game_url)


@login_required(login_url="rooms:login")
def create(request):
    if request.method == "POST":
        try:
            max_players = int(request.POST.get("members", 4))
        except (TypeError, ValueError):
            max_players = 4
        max_players = max(2, min(4, max_players))

        try:
            time_limit = int(request.POST.get("time", 60))
        except (TypeError, ValueError):
            time_limit = 60
        time_limit = max(1, min(90, time_limit))

        alphabet = string.ascii_uppercase + string.digits
        while True:
            room_id = "".join(secrets.choice(alphabet) for _ in range(4))
            if not Room.objects.filter(room_id=room_id).exists():
                break

        room_password = request.POST.get("password", "")
        with transaction.atomic():
            room = Room.objects.create(
                room_id=room_id,
                host=request.user,
                max_players=max_players,
                current_players=1,
                time_limit=time_limit,
                theme=request.POST.get("theme", "").strip()[:80],
                baba_characters=_clean_baba_characters(
                    request.POST.get("baba_characters", DEFAULT_BABA_CHARACTERS)
                ),
                has_password=bool(room_password),
                password_hash=make_password(room_password) if room_password else "",
            )
            RoomParticipant.objects.create(room=room, user=request.user)
        request.session[f"room_access_{room.room_id}"] = True
        query = urlencode({"room_id": room.room_id, "members": room.max_players})
        return redirect(f"/wait/?{query}")

    return render(
        request,
        "rooms/create_room.html",
        {"default_baba_characters": DEFAULT_BABA_CHARACTERS},
    )


def join(request):
    return render(request, "rooms/join_room.html")


@login_required(login_url="rooms:login")
def rank(request):
    entry = _join_rank_queue(request.user)
    state = _rank_match_state(entry)
    if state["is_started"]:
        return redirect(state["game_url"])

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "rooms/rank_match.html",
        {
            "rank_data": _get_rank_data(user_profile.rating),
            "rank_state": state,
        },
    )


@login_required(login_url="rooms:login")
def rank_match_status(request):
    entry = _join_rank_queue(request.user)
    return JsonResponse(_rank_match_state(entry))


@require_POST
@login_required(login_url="rooms:login")
def leave_rank_match(request):
    matched_room = None
    with transaction.atomic():
        entry = (
            RankMatchEntry.objects.select_for_update()
            .select_related("room")
            .filter(user=request.user)
            .first()
        )
        if entry and entry.room_id is None:
            entry.delete()
        elif entry:
            matched_room = entry.room
    if matched_room:
        if matched_room.is_started:
            game_url = f'{reverse("game:game")}?{urlencode({"room_id": matched_room.room_id})}'
            return redirect(game_url)
        return redirect("rooms:rank")
    return redirect("rooms:match")


def wait(request):
    try:
        max_players = int(request.GET.get("members", 4))
    except (TypeError, ValueError):
        max_players = 4

    max_players = max(2, min(4, max_players))
    room_id = request.GET.get("room_id", "A7K9").strip().upper()[:8] or "A7K9"
    back_to_normal = request.GET.get("source") == "normal"

    room = Room.objects.filter(room_id=room_id, is_active=True).first()
    if room:
        if (
            request.user.is_authenticated
            and room.host_id == request.user.id
            and not room.participants.filter(user=request.user).exists()
        ):
            room, _ = _add_room_participant(room.pk, request.user)
        if room.has_password and not request.session.get(f"room_access_{room.room_id}"):
            return redirect("rooms:join_normal_room", room_id=room.room_id)
        if room.is_started:
            return redirect("game:game")
        if back_to_normal and request.user.is_authenticated:
            room, joined = _add_room_participant(room.pk, request.user)
            if not joined:
                return redirect("rooms:normal_match")
        max_players = room.max_players
        current_players = room.participants.count()
        if room.current_players != current_players:
            room.current_players = current_players
            room.save(update_fields=["current_players"])
    else:
        current_players = 0

    return render(
        request,
        "rooms/waiting_room.html",
        {
            "current_players": current_players,
            "max_players": max_players,
            "room_id": room_id,
            "back_to_normal": back_to_normal,
            "is_host": bool(room and room.host_id == request.user.id),
        },
    )


def room_status(request, room_id):
    room = (
        Room.objects.filter(
            room_id=room_id.upper(),
            is_active=True,
        )
        .annotate(participant_count=Count("participants"))
        .first()
    )
    if room is None:
        return JsonResponse({"active": False}, status=404)
    return JsonResponse(
        {
            "active": True,
            "room_id": room.room_id,
            "current_players": room.participant_count,
            "max_players": room.max_players,
            "is_started": room.is_started,
            "game_url": f'{reverse("game:game")}?{urlencode({"room_id": room.room_id})}',
        }
    )


def rule(request):
    return render(request, "rooms/rules.html")


def profile(request):
    coin_balance = 0
    battle_stats = None
    rank_data = None
    if request.user.is_authenticated:
        customization = get_equipped_customization(request.user)
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        coin_balance = user_profile.coins
        battle_stats = _get_battle_stats(request.user)
        rank_data = _get_rank_data(user_profile.rating)
    return render(
        request,
        "rooms/profile.html",
        {
            "coin_balance": coin_balance,
            "battle_stats": battle_stats,
            "rank_data": rank_data,
            "customization": customization if request.user.is_authenticated else None,
        },
    )


@login_required(login_url="rooms:login")
def battle_stats(request):
    return render(
        request,
        "rooms/battle_stats.html",
        {"battle_stats": _get_battle_stats(request.user)},
    )


@login_required(login_url="rooms:login")
def rank_rates(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "rooms/rank_rates.html",
        {"rank_data": _get_rank_data(user_profile.rating)},
    )


@login_required(login_url="rooms:login")
def inventory(request):
    ensure_default_owned_items(request.user)
    group_details = [
        ("avatar", "アバター", "自分らしいアイコン"),
        ("card", "カード", "対戦で使えるアイテム"),
        ("frame", "フレーム", "アイコンを囲むデザイン"),
        ("stamp", "スタンプ", "対戦で使えるリアクション"),
        ("title", "称号", "名前の下に表示する称号"),
    ]
    selected_type = request.GET.get("type", "").strip()
    valid_types = {key for key, _, _ in group_details}
    if selected_type not in valid_types | {"customize"}:
        selected_type = ""

    owned_items_query = OwnedItem.objects.filter(user=request.user)
    if selected_type == "customize":
        customize_types = {"avatar", "frame", "stamp", "title"}
        owned_items_query = owned_items_query.filter(item_type__in=customize_types)
        group_details = [
            details for details in group_details if details[0] in customize_types
        ]
    elif selected_type:
        owned_items_query = owned_items_query.filter(item_type=selected_type)
        group_details = [
            details for details in group_details if details[0] == selected_type
        ]
    owned_items = list(owned_items_query)
    owned_by_code = {item.item_code: item for item in owned_items}
    catalog_by_code = {item[0]: item for item in ITEM_CATALOG}
    include_unowned = (
        bool(selected_type)
        and selected_type != "customize"
        and request.GET.get("include") == "1"
    )
    display_items = []
    if include_unowned:
        for item_code, item_type, name, icon, acquisition_method in ITEM_CATALOG:
            if item_type != selected_type:
                continue
            owned_item = owned_by_code.get(item_code)
            display_items.append(
                {
                    "item_code": item_code,
                    "item_type": item_type,
                    "name": name,
                    "icon": icon,
                    "image_path": ITEM_IMAGE_PATHS.get(item_code, ""),
                    "acquisition_method": acquisition_method,
                    "is_owned": owned_item is not None,
                    "quantity": owned_item.quantity if owned_item else 0,
                    "is_equipped": bool(owned_item and owned_item.is_equipped),
                    "can_equip": item_type != "card",
                }
            )
        catalog_codes = {item[0] for item in ITEM_CATALOG}
        display_items.extend(
            {
                "item_code": item.item_code,
                "item_type": item.item_type,
                "name": item.name,
                "icon": item.icon,
                "image_path": ITEM_IMAGE_PATHS.get(item.item_code, ""),
                "acquisition_method": "ショップ・イベントで入手",
                "is_owned": True,
                "quantity": item.quantity,
                "is_equipped": item.is_equipped,
                "can_equip": item.item_type != "card",
            }
            for item in owned_items
            if item.item_code not in catalog_codes
        )
    else:
        display_items = [
            {
                "item_code": item.item_code,
                "item_type": item.item_type,
                "name": item.name,
                "icon": item.icon,
                "image_path": ITEM_IMAGE_PATHS.get(item.item_code, ""),
                "acquisition_method": (
                    catalog_by_code[item.item_code][4]
                    if item.item_code in catalog_by_code
                    else "ショップ・イベントで入手"
                ),
                "is_owned": True,
                "quantity": item.quantity,
                "is_equipped": item.is_equipped,
                "can_equip": item.item_type != "card",
            }
            for item in owned_items
        ]

    item_groups = [
        {
            "key": key,
            "label": label,
            "description": description,
            "items": [item for item in display_items if item["item_type"] == key],
            "owned_count": sum(item.item_type == key for item in owned_items),
        }
        for key, label, description in group_details
    ]
    return render(
        request,
        "rooms/inventory.html",
        {
            "item_groups": item_groups,
            "item_count": len(owned_items),
            "selected_type": selected_type,
            "include_unowned": include_unowned,
            "show_ownership_toggle": bool(
                selected_type and selected_type != "customize"
            ),
            "page_title": (
                "カスタマイズ一覧"
                if selected_type == "customize"
                else f"{group_details[0][1]}一覧"
                if selected_type
                else "所持アイテム"
            ),
        },
    )


@require_POST
@login_required(login_url="rooms:login")
def equip_item(request):
    item_code = request.POST.get("item_code", "").strip()
    with transaction.atomic():
        item = (
            OwnedItem.objects.select_for_update()
            .filter(user=request.user, item_code=item_code)
            .first()
        )
        if item is None:
            return JsonResponse(
                {"error": "このアイテムは所持していません。"},
                status=404,
            )
        if item.item_type == "card":
            return JsonResponse(
                {"error": "カードは装備するアイテムではありません。"},
                status=400,
            )

        if item.item_type == "stamp":
            if item.is_equipped:
                item.is_equipped = False
                item.save(update_fields=["is_equipped"])
                return JsonResponse(
                    {
                        "message": f"「{item.name}」の装備を解除しました。",
                        "item_code": item.item_code,
                        "item_type": item.item_type,
                        "is_equipped": False,
                    }
                )
            # Stamps are multi-slot customizations, with a maximum of six.
            equipped_stamp_count = len(
                list(
                    OwnedItem.objects.select_for_update().filter(
                        user=request.user,
                        item_type="stamp",
                        is_equipped=True,
                    )
                )
            )
            if not item.is_equipped and equipped_stamp_count >= 6:
                return JsonResponse(
                    {"error": "スタンプは最大6個まで装備できます。"},
                    status=400,
                )
        else:
            OwnedItem.objects.filter(
                user=request.user,
                item_type=item.item_type,
                is_equipped=True,
            ).exclude(pk=item.pk).update(is_equipped=False)
        if not item.is_equipped:
            item.is_equipped = True
            item.save(update_fields=["is_equipped"])

    return JsonResponse(
        {
            "message": f"「{item.name}」を装備しました。",
            "item_code": item.item_code,
            "item_type": item.item_type,
            "is_equipped": True,
        }
    )


def login_page(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = ""

    if request.user.is_authenticated:
        return redirect(next_url or "rooms:profile")

    error = ""
    username = ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is None:
            error = "アカウントネームまたはパスワードが違います。"
        else:
            auth_login(request, user)
            return redirect(next_url or "rooms:profile")

    return render(
        request,
        "rooms/login.html",
        {"error": error, "username": username, "next": next_url},
    )


def register_page(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = ""

    if request.user.is_authenticated:
        return redirect(next_url or "rooms:profile")

    error = ""
    username = ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password1", "")
        password_confirm = request.POST.get("password2", "")
        user_model = get_user_model()

        if not username:
            error = "アカウントネームを入力してください。"
        elif len(username) > 150:
            error = "アカウントネームは150文字以内で入力してください。"
        elif not re.fullmatch(r"[\w.@+-]+", username):
            error = "アカウントネームに使用できない文字が含まれています。"
        elif user_model.objects.filter(username__iexact=username).exists():
            error = "このアカウントネームはすでに使われています。"
        elif not password:
            error = "パスワードを入力してください。"
        elif password != password_confirm:
            error = "確認用パスワードが一致しません。"
        else:
            user = user_model.objects.create_user(
                username=username,
                password=password,
            )
            auth_login(request, user)
            return redirect(next_url or "rooms:profile")

    return render(
        request,
        "rooms/register.html",
        {"error": error, "username": username, "next": next_url},
    )


@require_POST
def logout_page(request):
    auth_logout(request)
    return redirect("rooms:home")


def shop(request):
    coin_balance = 0
    purchase_history = []
    if request.user.is_authenticated:
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        coin_balance = user_profile.coins
        purchase_history = list(
            ShopPurchaseHistory.objects.filter(user=request.user)[:50]
        )
        for purchase in purchase_history:
            purchase.image_path = ITEM_IMAGE_PATHS.get(purchase.item_code, "")
    owned_item_codes = set()
    owned_item_quantities = {item_code: 0 for item_code in SHOP_PRODUCT_PRICES}
    if request.user.is_authenticated:
        owned_items = OwnedItem.objects.filter(user=request.user)
        owned_item_codes = set(owned_items.values_list("item_code", flat=True))
        owned_item_quantities.update(
            dict(owned_items.values_list("item_code", "quantity"))
        )
    return render(
        request,
        "rooms/shop.html",
        {
            "coin_balance": coin_balance,
            "owned_item_codes": owned_item_codes,
            "owned_item_quantities": owned_item_quantities,
            "purchase_history": purchase_history,
        },
    )


@require_POST
@login_required(login_url="rooms:login")
def purchase_shop_item(request):
    item_code = request.POST.get("item_code", "").strip()
    price = SHOP_PRODUCT_PRICES.get(item_code)
    catalog_item = next(
        (item for item in ITEM_CATALOG if item[0] == item_code),
        None,
    )
    if price is None or catalog_item is None:
        return JsonResponse({"error": "この商品は購入できません。"}, status=404)

    _, item_type, name, icon, _ = catalog_item
    with transaction.atomic():
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        owned_item = (
            OwnedItem.objects.select_for_update()
            .filter(user=request.user, item_code=item_code)
            .first()
        )
        if item_type == "card" and owned_item and owned_item.quantity >= 99:
            return JsonResponse(
                {
                    "error": "このカードは99枚まで所持できます。",
                    "quantity": owned_item.quantity,
                    "max_quantity": 99,
                },
                status=409,
            )
        if item_type != "card" and owned_item:
            return JsonResponse(
                {"error": "このアイテムはすでに所持しています。"},
                status=409,
            )
        if profile.coins < price:
            return JsonResponse(
                {
                    "error": "コインが足りません。",
                    "coin_balance": profile.coins,
                },
                status=400,
            )

        profile.coins -= price
        profile.save(update_fields=["coins"])
        if owned_item:
            owned_item.quantity += 1
            owned_item.name = name
            owned_item.icon = icon
            owned_item.save(update_fields=["quantity", "name", "icon"])
        else:
            owned_item = OwnedItem.objects.create(
                user=request.user,
                item_code=item_code,
                item_type=item_type,
                name=name,
                icon=icon,
            )
        purchase_history_entry = ShopPurchaseHistory.objects.create(
            user=request.user,
            item_code=item_code,
            item_type=item_type,
            item_name=name,
            quantity=1,
            coins_spent=price,
        )

    return JsonResponse(
        {
            "message": f"「{name}」を購入しました！",
            "item_code": item_code,
            "item_type": item_type,
            "quantity": owned_item.quantity,
            "max_quantity": 99 if item_type == "card" else 1,
            "is_maxed": item_type == "card" and owned_item.quantity >= 99,
            "coin_balance": profile.coins,
            "purchase_history": {
                "id": purchase_history_entry.id,
                "item_name": purchase_history_entry.item_name,
                "coins_spent": purchase_history_entry.coins_spent,
                "purchased_at": purchase_history_entry.purchased_at.isoformat(),
            },
        }
    )


def ai(request):
    return render(request, "rooms/ai.html")
