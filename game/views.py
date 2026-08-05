import re
import unicodedata

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rooms.models import Room

from .models import GamePlayer, GameSession, GameWord
from .services import ensure_game_session


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


def _to_hiragana(text):
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
        for char in normalized
    ).translate(SMALL_KANA)


def _next_letter(normalized_word):
    if normalized_word[-1] != "ー":
        return normalized_word[-1]

    return next(
        (char for char in reversed(normalized_word[:-1]) if char != "ー"),
        "",
    )


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
        "turn_number": session.turn_number,
        "current_turn_order": session.current_turn_order,
        "current_letter": session.current_letter,
        "current_word": words[-1].word if words else session.current_letter,
        "players": [
            {
                "id": player.id,
                "name": player.display_name,
                "title": player.title,
                "remaining_seconds": player.remaining_seconds,
                "is_alive": player.is_alive,
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
            "is_my_turn": bool(current_player and current_player.user_id == request.user.id),
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
        player = session.players.filter(user=request.user, is_alive=True).first()
        if player is None:
            return JsonResponse({"error": "回答できるプレイヤーではありません。"}, status=403)
        if player.turn_order != session.current_turn_order:
            return JsonResponse({"error": "まだあなたの番ではありません。"}, status=409)
        if not normalized_word.startswith(session.current_letter):
            return JsonResponse(
                {"error": f"「{session.current_letter}」から始まる言葉を入力してください。"},
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
        baba_hit = ending_letter == session.baba_letter
        if baba_hit:
            player.is_alive = False
            player.save(update_fields=["is_alive"])

        session.current_letter = ending_letter
        alive_orders = list(
            session.players.filter(is_alive=True)
            .order_by("turn_order")
            .values_list("turn_order", flat=True)
        )
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
        session.save(update_fields=["current_letter", "current_turn_order", "turn_number"])

    return JsonResponse(
        {
            "message": (
                f"「{ending_letter}」がババでした。あなたは脱落です。"
                if baba_hit
                else f"「{word}」を送信しました。"
            ),
            "baba_hit": baba_hit,
            **_serialize_game(session, request.user),
        }
    )
