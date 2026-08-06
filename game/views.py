import re
import unicodedata
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from rooms.models import OwnedItem, Room, UserProfile
from rooms.services import (
    ITEM_IMAGE_PATHS,
    ensure_default_owned_items,
    get_equipped_customizations,
)

from .models import GamePlayer, GameSession, GameStamp, GameWord
from .services import (
    choose_baba_letter,
    coin_reward_for_placement,
    ensure_game_session,
    grant_result_rewards,
)


AVATARS = [
    ("🐧", "avatar-blue"),
    ("🍎", "avatar-red"),
    ("🌻", "avatar-yellow"),
    ("👾", "avatar-purple"),
]

SMALL_KANA = str.maketrans(
    {
        "ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お",
        "ゃ": "や", "ゅ": "ゆ", "ょ": "よ", "っ": "つ", "ゎ": "わ",
    }
)
HIRAGANA_PATTERN = re.compile(r"^[ぁ-ゖー]+$")
KANA_VOICE_MARKS = {"\u3099", "\u309a"}
BABA_REVEAL_SECONDS = 6.2
BABA_WORD_EXPLOSION_SECONDS = 1.2


def _to_hiragana(text):
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
        for char in normalized
    ).translate(SMALL_KANA)


def _next_letter(normalized_word):
    if normalized_word[-1] not in {"ー", "ん"}:
        return normalized_word[-1]

    return next(
        (char for char in reversed(normalized_word[:-1]) if char != "ー"),
        normalized_word[-1],
    )


def _remove_kana_voice_mark(character):
    decomposed = unicodedata.normalize("NFD", character)
    without_mark = "".join(
        part for part in decomposed if part not in KANA_VOICE_MARKS
    )
    return unicodedata.normalize("NFC", without_mark)


def _matches_current_letter(normalized_word, current_letter):
    if normalized_word.startswith(current_letter):
        return True

    unvoiced_letter = _remove_kana_voice_mark(current_letter)
    return (
        unvoiced_letter != current_letter
        and normalized_word.startswith(unvoiced_letter)
    )


def _accepted_start_letters(current_letter):
    unvoiced_letter = _remove_kana_voice_mark(current_letter)
    if unvoiced_letter == current_letter:
        return [current_letter]
    return [current_letter, unvoiced_letter]


def _available_placements(session):
    player_count = session.players.count()
    assigned = set(
        session.players.exclude(placement=None).values_list("placement", flat=True)
    )
    return [
        placement
        for placement in range(1, player_count + 1)
        if placement not in assigned
    ]


def _elimination_placement(session):
    return max(_available_placements(session))


def _best_remaining_placement(session):
    return min(_available_placements(session))


def _tick_game_clock(session):
    now = timezone.now()
    _finalize_baba_reveal_if_due(session)
    if session.is_finished:
        return

    if session.baba_challenger_id or session.baba_reveal_until:
        session.turn_started_at = now
        session.save(update_fields=["turn_started_at"])
        return

    player = session.players.filter(
        turn_order=session.current_turn_order,
        is_alive=True,
    ).first()
    if player is None:
        return

    elapsed_seconds = int((now - session.turn_started_at).total_seconds())
    if elapsed_seconds <= 0:
        return

    if elapsed_seconds < player.remaining_seconds:
        player.remaining_seconds -= elapsed_seconds
        player.save(update_fields=["remaining_seconds"])
        session.turn_started_at += timedelta(seconds=elapsed_seconds)
        session.save(update_fields=["turn_started_at"])
        return

    player.remaining_seconds = 0
    player.placement = _elimination_placement(session)
    player.is_alive = False
    player.save(update_fields=["remaining_seconds", "placement", "is_alive"])

    remaining_players = list(
        session.players.filter(is_alive=True).order_by("turn_order")
    )
    if len(remaining_players) <= 1:
        if remaining_players:
            remaining_players[0].placement = _best_remaining_placement(session)
            remaining_players[0].save(update_fields=["placement"])
        session.is_finished = True
    else:
        later_players = [
            item
            for item in remaining_players
            if item.turn_order > player.turn_order
        ]
        session.current_turn_order = (
            later_players[0] if later_players else remaining_players[0]
        ).turn_order

    session.baba_challenger = player
    session.baba_guess_preview = "0"
    session.baba_reveal_correct = False
    session.baba_reveal_until = now + timedelta(
        seconds=BABA_WORD_EXPLOSION_SECONDS
    )
    session.baba_reveal_mode = "timeout"
    session.turn_started_at = now
    session.save(
        update_fields=[
            "current_turn_order",
            "is_finished",
            "baba_challenger",
            "baba_guess_preview",
            "baba_reveal_correct",
            "baba_reveal_until",
            "baba_reveal_mode",
            "turn_started_at",
        ]
    )
    if session.is_finished:
        grant_result_rewards(session)


def _refresh_game_clock(session):
    with transaction.atomic():
        locked_session = GameSession.objects.select_for_update().get(pk=session.pk)
        _tick_game_clock(locked_session)
    return locked_session


def _get_accessible_session(request, room_id=None):
    room_id = (room_id or request.GET.get("room_id", "")).strip().upper()
    if not room_id:
        return None, None

    room = get_object_or_404(Room, room_id=room_id, is_started=True)
    session = ensure_game_session(room)
    player = session.players.filter(user=request.user).first()
    if player is None:
        return room, None
    return room, session


def _finalize_baba_reveal_if_due(session):
    if not session.baba_reveal_until or session.baba_reveal_until > timezone.now():
        return False
    session.baba_challenger = None
    session.baba_guess_preview = ""
    session.baba_reveal_correct = None
    session.baba_reveal_until = None
    session.baba_reveal_mode = ""
    session.turn_started_at = timezone.now()
    session.save(
        update_fields=[
            "baba_challenger",
            "baba_guess_preview",
            "baba_reveal_correct",
            "baba_reveal_until",
            "baba_reveal_mode",
            "turn_started_at",
        ]
    )
    return True


def _serialize_game(session, request_user):
    _finalize_baba_reveal_if_due(session)
    players = list(session.players.order_by("turn_order"))
    customizations = get_equipped_customizations(
        [player.user_id for player in players]
    )
    for player in players:
        if player.user_id in customizations:
            player.title = customizations[player.user_id]["title_name"]
    words = list(
        session.words.select_related("player").order_by("turn_number", "id")
    )
    stamps = list(
        session.stamps.select_related("player").order_by("-id")[:20]
    )[::-1]
    baba_challenger = (
        session.players.filter(pk=session.baba_challenger_id).first()
        if session.baba_challenger_id
        else None
    )
    reveal_active = bool(session.baba_reveal_until)
    public_is_finished = session.is_finished and not reveal_active
    return {
        "is_finished": public_is_finished,
        "result_url": (
            f'{reverse("game:room_result")}?{urlencode({"room_id": session.room.room_id})}'
            if public_is_finished
            else ""
        ),
        "turn_number": session.turn_number,
        "current_turn_order": session.current_turn_order,
        "current_letter": session.current_letter,
        "accepted_start_letters": _accepted_start_letters(session.current_letter),
        "current_word": words[-1].word if words else session.current_letter,
        "baba_letter": session.baba_letter,
        "baba_challenge": (
            {
                "player_id": baba_challenger.id,
                "player_name": baba_challenger.display_name,
                "is_self": baba_challenger.user_id == request_user.id,
                "preview": session.baba_guess_preview,
            }
            if baba_challenger
            else None
        ),
        "baba_reveal": (
            {
                "active": True,
                "correct": session.baba_reveal_correct,
                "ends_at": session.baba_reveal_until.isoformat(),
                "mode": session.baba_reveal_mode or "guess",
            }
            if reveal_active
            else None
        ),
        "players": [
            {
                "id": player.id,
                "name": player.display_name,
                "title": player.title,
                "remaining_seconds": player.remaining_seconds,
                "is_alive": player.is_alive,
                "placement": player.placement,
                "is_current": player.turn_order == session.current_turn_order,
                "is_self": player.user_id == request_user.id,
            }
            for player in players
        ],
        "words": [
            {
                "word": game_word.word,
                "player_id": game_word.player_id,
                "player_name": game_word.player.display_name,
                "turn_number": game_word.turn_number,
            }
            for game_word in words
        ],
        "stamps": [
            {
                "id": stamp.id,
                "player_id": stamp.player_id,
                "name": stamp.stamp_name,
                "icon": stamp.stamp_icon,
                "image_url": (
                    static(ITEM_IMAGE_PATHS[stamp.stamp_code])
                    if stamp.stamp_code in ITEM_IMAGE_PATHS
                    else ""
                ),
            }
            for stamp in stamps
        ],
    }


@login_required(login_url="rooms:login")
def game(request):
    room, session = _get_accessible_session(request)
    if room is None:
        return redirect("rooms:match")
    if session is None:
        return HttpResponseForbidden("このゲームには参加していません。")
    session = _refresh_game_clock(session)
    _finalize_baba_reveal_if_due(session)
    if session.is_finished and not session.baba_reveal_until:
        result_query = urlencode({"room_id": room.room_id})
        return redirect(f'{reverse("game:room_result")}?{result_query}')

    players = list(session.players.select_related("user").order_by("turn_order"))
    customizations = get_equipped_customizations(
        [player.user_id for player in players]
    )
    for player in players:
        customization = customizations.get(player.user_id)
        if customization:
            player.avatar = customization["avatar_icon"]
            player.avatar_image_path = customization["avatar_image_path"]
            player.avatar_class = "avatar-equipped"
            player.frame_class = customization["frame_class"]
            player.frame_image_path = customization["frame_image_path"]
            player.title = customization["title_name"]
        else:
            avatar, avatar_class = AVATARS[player.turn_order % len(AVATARS)]
            player.avatar = avatar
            player.avatar_image_path = ""
            player.avatar_class = avatar_class
            player.frame_class = "frame-sky"
            player.frame_image_path = ""
        player.is_current = player.turn_order == session.current_turn_order
        player.is_self = player.user_id == request.user.id

    alive_players = [player for player in players if player.is_alive]
    current_player = next((player for player in players if player.is_current), None)
    self_player = next((player for player in players if player.is_self), None)
    baba_challenger = next(
        (player for player in players if player.id == session.baba_challenger_id),
        None,
    )
    words = list(session.words.select_related("player").order_by("turn_number", "id"))
    ensure_default_owned_items(request.user)
    owned_items = list(OwnedItem.objects.filter(user=request.user))
    for item in owned_items:
        item.image_path = ITEM_IMAGE_PATHS.get(item.item_code, "")
    latest_stamp_id = session.stamps.order_by("-id").values_list("id", flat=True).first() or 0

    return render(
        request,
        "game/game.html",
        {
            "room": room,
            "session": session,
            "players": players,
            "alive_count": len(alive_players),
            "player_count": len(players),
            "current_player": current_player,
            "words": words,
            "current_word": words[-1].word if words else session.current_letter,
            "current_letter_display": "・".join(
                _accepted_start_letters(session.current_letter)
            ),
            "is_my_turn": bool(current_player and current_player.user_id == request.user.id),
            "can_submit_word": bool(
                current_player
                and current_player.user_id == request.user.id
                and not baba_challenger
            ),
            "can_guess_baba": bool(
                self_player and self_player.is_alive and not baba_challenger
            ),
            "baba_challenger": baba_challenger,
            "is_baba_challenger": bool(
                self_player and self_player.id == session.baba_challenger_id
            ),
            "owned_stamps": [
                item
                for item in owned_items
                if item.item_type == "stamp" and item.is_equipped
            ],
            "owned_game_items": [
                item for item in owned_items if item.item_type != "stamp"
            ],
            "latest_stamp_id": latest_stamp_id,
        },
    )


@login_required(login_url="rooms:login")
def room_result(request):
    room, session = _get_accessible_session(request)
    if room is None:
        return redirect("rooms:match")
    if session is None:
        return HttpResponseForbidden("このゲームには参加していません。")
    if not session.is_finished:
        game_query = urlencode({"room_id": room.room_id})
        return redirect(f'{reverse("game:game")}?{game_query}')

    with transaction.atomic():
        session = GameSession.objects.select_for_update().get(pk=session.pk)
        grant_result_rewards(session)

    players = list(
        session.players.annotate(word_count=Count("words")).order_by(
            "placement",
            "turn_order",
        )
    )
    current_player = next(
        (player for player in players if player.user_id == request.user.id),
        None,
    )
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    rank_data = None
    rank_change_class = "neutral"
    if room.is_ranked and current_player:
        from rooms.views import _get_rank_data

        result_rating = current_player.rating_after
        if result_rating is None:
            result_rating = profile.rating
        rank_data = _get_rank_data(result_rating)
        if current_player.rating_change > 0:
            rank_change_class = "positive"
        elif current_player.rating_change < 0:
            rank_change_class = "negative"
    return render(
        request,
        "rooms/result/room_result.html",
        {
            "room": room,
            "players": players,
            "current_player": current_player,
            "player_count": len(players),
            "is_winner": bool(current_player and current_player.placement == 1),
            "coin_reward": (
                coin_reward_for_placement(current_player.placement)
                if current_player
                else 0
            ),
            "coin_balance": profile.coins,
            "is_ranked": room.is_ranked,
            "rank_data": rank_data,
            "rank_rating_change": (
                current_player.rating_change if current_player else 0
            ),
            "rank_change_class": rank_change_class,
        },
    )


@login_required(login_url="rooms:login")
def game_players_status(request):
    room, session = _get_accessible_session(request)
    if room is None:
        return JsonResponse({"error": "room_id is required"}, status=400)
    if session is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    session = _refresh_game_clock(session)
    return JsonResponse(_serialize_game(session, request.user))


@require_POST
@login_required(login_url="rooms:login")
def send_stamp(request):
    room_id = request.POST.get("room_id", "").strip().upper()
    stamp_code = request.POST.get("stamp_code", "").strip()
    room, session = _get_accessible_session(request, room_id)
    if room is None:
        return JsonResponse({"error": "ルームが見つかりません。"}, status=404)
    if session is None:
        return JsonResponse({"error": "このゲームには参加していません。"}, status=403)
    if session.is_finished:
        return JsonResponse({"error": "このゲームは終了しています。"}, status=409)

    player = session.players.filter(user=request.user).first()
    stamp_item = OwnedItem.objects.filter(
        user=request.user,
        item_code=stamp_code,
        item_type="stamp",
        is_equipped=True,
    ).first()
    if player is None or stamp_item is None:
        return JsonResponse({"error": "このスタンプは使用できません。"}, status=404)

    stamp = GameStamp.objects.create(
        session=session,
        player=player,
        stamp_code=stamp_item.item_code,
        stamp_name=stamp_item.name,
        stamp_icon=stamp_item.icon,
    )
    return JsonResponse(
        {
            "stamp": {
                "id": stamp.id,
                "player_id": player.id,
                "name": stamp.stamp_name,
                "icon": stamp.stamp_icon,
                "image_url": (
                    static(ITEM_IMAGE_PATHS[stamp.stamp_code])
                    if stamp.stamp_code in ITEM_IMAGE_PATHS
                    else ""
                ),
            }
        }
    )


@require_POST
@login_required(login_url="rooms:login")
def start_baba_challenge(request):
    room_id = request.POST.get("room_id", "").strip().upper()
    room, accessible_session = _get_accessible_session(request, room_id)
    if room is None:
        return JsonResponse({"error": "ルームが見つかりません。"}, status=404)
    if accessible_session is None:
        return JsonResponse({"error": "このゲームには参加していません。"}, status=403)

    with transaction.atomic():
        session = GameSession.objects.select_for_update().get(
            pk=accessible_session.pk
        )
        _tick_game_clock(session)
        _finalize_baba_reveal_if_due(session)
        if session.is_finished:
            return JsonResponse({"error": "このゲームは終了しています。"}, status=409)
        player = session.players.filter(user=request.user, is_alive=True).first()
        if player is None:
            return JsonResponse({"error": "脱落後は挑戦できません。"}, status=403)
        if session.baba_challenger_id not in (None, player.id):
            return JsonResponse(
                {"error": "ほかのプレイヤーが挑戦中です。"},
                status=409,
            )
        if session.baba_challenger_id is None:
            session.baba_challenger = player
            session.baba_guess_preview = ""
            session.baba_reveal_correct = None
            session.baba_reveal_until = None
            session.baba_reveal_mode = ""
            session.save(
                update_fields=[
                    "baba_challenger",
                    "baba_guess_preview",
                    "baba_reveal_correct",
                    "baba_reveal_until",
                    "baba_reveal_mode",
                ]
            )

    return JsonResponse(_serialize_game(session, request.user))


@require_POST
@login_required(login_url="rooms:login")
def update_baba_preview(request):
    room_id = request.POST.get("room_id", "").strip().upper()
    preview = _to_hiragana(
        unicodedata.normalize("NFKC", request.POST.get("preview", "")).strip()
    )
    room, accessible_session = _get_accessible_session(request, room_id)
    if room is None:
        return JsonResponse({"error": "ルームが見つかりません。"}, status=404)
    if accessible_session is None:
        return JsonResponse({"error": "このゲームには参加していません。"}, status=403)
    if preview and (len(preview) != 1 or not HIRAGANA_PATTERN.fullmatch(preview)):
        return JsonResponse({"error": "ひらがな1文字を入力してください。"}, status=400)

    with transaction.atomic():
        session = GameSession.objects.select_for_update().get(
            pk=accessible_session.pk
        )
        player = session.players.filter(user=request.user, is_alive=True).first()
        if player is None or session.baba_challenger_id != player.id:
            return JsonResponse({"error": "BABAに挑戦していません。"}, status=403)
        session.baba_guess_preview = preview
        session.save(update_fields=["baba_guess_preview"])

    return JsonResponse({"preview": preview})


@require_POST
@login_required(login_url="rooms:login")
def guess_baba(request):
    room_id = request.POST.get("room_id", "").strip().upper()
    guessed_letter = _to_hiragana(
        unicodedata.normalize("NFKC", request.POST.get("baba_letter", "")).strip()
    )
    room, accessible_session = _get_accessible_session(request, room_id)
    if room is None:
        return JsonResponse({"error": "ルームが見つかりません。"}, status=404)
    if accessible_session is None:
        return JsonResponse({"error": "このゲームには参加していません。"}, status=403)
    if len(guessed_letter) != 1 or guessed_letter not in room.baba_characters:
        return JsonResponse(
            {"error": "ババの範囲から、ひらがな1文字を入力してください。"},
            status=400,
        )

    with transaction.atomic():
        session = GameSession.objects.select_for_update().get(
            pk=accessible_session.pk
        )
        if session.is_finished:
            return JsonResponse(
                {
                    "error": "このゲームは終了しています。",
                    **_serialize_game(session, request.user),
                },
                status=409,
            )

        player = session.players.filter(user=request.user, is_alive=True).first()
        if player is None:
            return JsonResponse({"error": "脱落後は挑戦できません。"}, status=403)
        if session.baba_challenger_id != player.id:
            return JsonResponse(
                {"error": "先に「挑戦する」を押してください。"},
                status=409,
            )

        alive_players = list(
            session.players.filter(is_alive=True).order_by("turn_order")
        )
        is_correct = guessed_letter == session.baba_letter

        if is_correct:
            player.placement = 1
            player.is_alive = False
            player.save(update_fields=["placement", "is_alive"])
            other_players = [item for item in alive_players if item.pk != player.pk]
            if len(other_players) <= 1:
                if other_players:
                    other_players[0].placement = _best_remaining_placement(session)
                    other_players[0].save(update_fields=["placement"])
                session.is_finished = True
            elif player.turn_order == session.current_turn_order:
                later_players = [
                    item
                    for item in other_players
                    if item.turn_order > player.turn_order
                ]
                session.current_turn_order = (
                    later_players[0] if later_players else other_players[0]
                ).turn_order
        else:
            player.placement = _elimination_placement(session)
            player.is_alive = False
            player.save(update_fields=["placement", "is_alive"])
            remaining_players = [item for item in alive_players if item.pk != player.pk]

            if len(remaining_players) <= 1:
                if remaining_players:
                    remaining_players[0].placement = _best_remaining_placement(
                        session
                    )
                    remaining_players[0].save(update_fields=["placement"])
                session.is_finished = True
            elif player.turn_order == session.current_turn_order:
                later_players = [
                    item
                    for item in remaining_players
                    if item.turn_order > player.turn_order
                ]
                session.current_turn_order = (
                    later_players[0] if later_players else remaining_players[0]
                ).turn_order

        session.baba_guess_preview = guessed_letter
        session.baba_reveal_correct = is_correct
        session.baba_reveal_until = timezone.now() + timedelta(
            seconds=BABA_REVEAL_SECONDS
        )
        session.baba_reveal_mode = "guess"
        session.save(
            update_fields=[
                "current_turn_order",
                "is_finished",
                "baba_guess_preview",
                "baba_reveal_correct",
                "baba_reveal_until",
                "baba_reveal_mode",
            ]
        )
        if session.is_finished:
            grant_result_rewards(session)

    return JsonResponse(
        {
            "correct": is_correct,
            "message": (
                f"正解です。「{guessed_letter}」がババでした！1位確定です。"
                if is_correct
                else f"「{guessed_letter}」はババではありません。脱落です。"
            ),
            **_serialize_game(session, request.user),
        }
    )


@require_POST
@login_required(login_url="rooms:login")
def submit_word(request):
    room_id = request.POST.get("room_id", "").strip().upper()
    word = unicodedata.normalize("NFKC", request.POST.get("answer", "")).strip()

    room, accessible_session = _get_accessible_session(request, room_id)
    if room is None:
        return JsonResponse({"error": "ルームが見つかりません。"}, status=404)
    if accessible_session is None:
        return JsonResponse({"error": "このゲームには参加していません。"}, status=403)
    if not word:
        return JsonResponse({"error": "言葉を入力してください。"}, status=400)
    if len(word) > 30:
        return JsonResponse({"error": "言葉は30文字以内で入力してください。"}, status=400)
    if not HIRAGANA_PATTERN.fullmatch(word):
        return JsonResponse({"error": "ひらがなのみ入力できます。"}, status=400)

    normalized_word = _to_hiragana(word)

    with transaction.atomic():
        session = GameSession.objects.select_for_update().get(pk=accessible_session.pk)
        _tick_game_clock(session)
        if session.is_finished:
            return JsonResponse(
                {
                    "error": "このゲームは終了しています。",
                    **_serialize_game(session, request.user),
                },
                status=409,
            )
        if session.baba_challenger_id:
            return JsonResponse(
                {
                    "error": "BABAの挑戦中は言葉を送信できません。",
                    **_serialize_game(session, request.user),
                },
                status=409,
            )
        player = session.players.filter(user=request.user, is_alive=True).first()
        if player is None:
            return JsonResponse({"error": "回答できるプレイヤーではありません。"}, status=403)
        if player.turn_order != session.current_turn_order:
            return JsonResponse({"error": "まだあなたの番ではありません。"}, status=409)
        if not _matches_current_letter(normalized_word, session.current_letter):
            unvoiced_letter = _remove_kana_voice_mark(session.current_letter)
            allowed_letters = (
                f"「{session.current_letter}」または「{unvoiced_letter}」"
                if unvoiced_letter != session.current_letter
                else f"「{session.current_letter}」"
            )
            return JsonResponse(
                {"error": f"{allowed_letters}から始まる言葉を入力してください。"},
                status=400,
            )
        if session.words.filter(word=word).exists():
            return JsonResponse({"error": "その言葉はすでに使われています。"}, status=409)

        try:
            GameWord.objects.create(
                session=session,
                player=player,
                word=word,
                turn_number=session.turn_number,
            )
        except IntegrityError:
            return JsonResponse({"error": "その言葉はすでに使われています。"}, status=409)

        ending_letter = _next_letter(normalized_word)
        hit_baba_letter = session.baba_letter
        baba_hit = normalized_word[-1] == hit_baba_letter
        if baba_hit:
            player.placement = _elimination_placement(session)
            player.is_alive = False
            player.save(update_fields=["is_alive", "placement"])
            session.baba_letter = choose_baba_letter(
                session.room,
                previous_letter=hit_baba_letter,
            )
            session.baba_challenger = player
            session.baba_guess_preview = hit_baba_letter
            session.baba_reveal_correct = False
            session.baba_reveal_until = timezone.now() + timedelta(
                seconds=BABA_WORD_EXPLOSION_SECONDS
            )
            session.baba_reveal_mode = "word"

        session.current_letter = ending_letter
        alive_orders = list(
            session.players.filter(is_alive=True)
            .order_by("turn_order")
            .values_list("turn_order", flat=True)
        )
        if baba_hit and len(alive_orders) <= 1:
            last_player = session.players.filter(
                is_alive=True,
                placement__isnull=True,
            ).first()
            if last_player:
                last_player.placement = _best_remaining_placement(session)
                last_player.save(update_fields=["placement"])
            session.is_finished = True
            grant_result_rewards(session)

        if not alive_orders:
            session.current_turn_order = player.turn_order
        elif baba_hit:
            later_orders = [
                turn_order
                for turn_order in alive_orders
                if turn_order > session.current_turn_order
            ]
            session.current_turn_order = (
                later_orders[0] if later_orders else alive_orders[0]
            )
        else:
            current_index = alive_orders.index(session.current_turn_order)
            session.current_turn_order = alive_orders[
                (current_index + 1) % len(alive_orders)
            ]
        session.turn_number += 1
        session.turn_started_at = timezone.now()
        session.save(
            update_fields=[
                "current_letter",
                "current_turn_order",
                "turn_number",
                "baba_letter",
                "is_finished",
                "coin_rewards_granted",
                "turn_started_at",
                "baba_challenger",
                "baba_guess_preview",
                "baba_reveal_correct",
                "baba_reveal_until",
                "baba_reveal_mode",
            ]
        )

    return JsonResponse(
        {
            "message": (
                f"「{hit_baba_letter}」がババでした。あなたは脱落です。ババを再抽選しました。"
                if baba_hit
                else f"「{word}」を送信しました。"
            ),
            "baba_hit": baba_hit,
            **_serialize_game(session, request.user),
        }
    )
