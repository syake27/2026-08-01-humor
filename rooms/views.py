import re
import secrets
import string
from datetime import timedelta
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

from .models import DEFAULT_BABA_CHARACTERS, Room, RoomParticipant, UserProfile


def _clean_baba_characters(value):
    """50音から選ばれた文字を、重複のない文字列として保存する。"""
    selected = []
    for character in value:
        if character in DEFAULT_BABA_CHARACTERS and character not in selected:
            selected.append(character)
    return "".join(selected) or DEFAULT_BABA_CHARACTERS


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
        if time_limit not in (30, 60, 90):
            time_limit = 60

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
    return render(request, "rooms/rank_match.html")


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
    if request.user.is_authenticated:
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        coin_balance = user_profile.coins
    return render(
        request,
        "rooms/profile.html",
        {"coin_balance": coin_balance},
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
    if request.user.is_authenticated:
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        coin_balance = user_profile.coins
    return render(request, "rooms/shop.html", {"coin_balance": coin_balance})


def ai(request):
    return render(request, "rooms/ai.html")
