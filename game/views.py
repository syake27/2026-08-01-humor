import re
import unicodedata
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from rooms.models import Room, UserProfile

from .models import GamePlayer, GameSession, GameWord
from .services import (
    choose_baba_letter,
    coin_reward_for_placement,
    ensure_game_session,
    grant_coin_rewards,
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


def _serialize_game(session, request_user):
    players = list(session.players.order_by("turn_order"))
    words = list(
        session.words.select_related("player").order_by("turn_number", "id")
    )
    return {
        "is_finished": session.is_finished,
        "result_url": (
            f'{reverse("game:room_result")}?{urlencode({"room_id": session.room.room_id})}'
            if session.is_finished
            else ""
        ),
        "turn_number": session.turn_number,
        "current_turn_order": session.current_turn_order,
        "current_letter": session.current_letter,
        "accepted_start_letters": _accepted_start_letters(session.current_letter),
        "current_word": words[-1].word if words else session.current_letter,
        "baba_letter": session.baba_letter,
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
    }


@login_required(login_url="rooms:login")
def game(request):
    room, session = _get_accessible_session(request)
    if room is None:
        return redirect("rooms:match")
    if session is None:
        return HttpResponseForbidden("このゲームには参加していません。")
    if session.is_finished:
        result_query = urlencode({"room_id": room.room_id})
        return redirect(f'{reverse("game:room_result")}?{result_query}')

    players = list(session.players.select_related("user").order_by("turn_order"))
    for player in players:
        avatar, avatar_class = AVATARS[player.turn_order % len(AVATARS)]
        player.avatar = avatar
        player.avatar_class = avatar_class
        player.is_current = player.turn_order == session.current_turn_order
        player.is_self = player.user_id == request.user.id

    alive_players = [player for player in players if player.is_alive]
    current_player = next((player for player in players if player.is_current), None)
    words = list(session.words.select_related("player").order_by("turn_number", "id"))

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
        grant_coin_rewards(session)

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
        },
    )


@login_required(login_url="rooms:login")
def game_players_status(request):
    room, session = _get_accessible_session(request)
    if room is None:
        return JsonResponse({"error": "room_id is required"}, status=400)
    if session is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    return JsonResponse(_serialize_game(session, request.user))


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
            player.placement = session.players.filter(is_alive=True).count()
            player.is_alive = False
            player.save(update_fields=["is_alive", "placement"])
            session.baba_letter = choose_baba_letter(
                session.room,
                previous_letter=hit_baba_letter,
            )

        session.current_letter = ending_letter
        alive_orders = list(
            session.players.filter(is_alive=True)
            .order_by("turn_order")
            .values_list("turn_order", flat=True)
        )
        if baba_hit and len(alive_orders) <= 1:
            session.players.filter(
                is_alive=True,
                placement__isnull=True,
            ).update(placement=1)
            session.is_finished = True
            grant_coin_rewards(session)

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
        session.save(
            update_fields=[
                "current_letter",
                "current_turn_order",
                "turn_number",
                "baba_letter",
                "is_finished",
                "coin_rewards_granted",
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
