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
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Room


def home(request):
    return render(request, "rooms/home.html")


def match(request):
    return render(request, "rooms/match.html")


@login_required(login_url="rooms:login")
def normal_match(request):
    active_since = timezone.now() - timedelta(hours=2)
    search_query = request.GET.get("q", "").strip().upper()[:8]
    rooms = Room.objects.filter(
        is_active=True,
        created_at__gte=active_since,
    ).select_related("host")
    if search_query:
        rooms = rooms.filter(room_id__icontains=search_query)
    return render(
        request,
        "rooms/normal_match.html",
        {"rooms": rooms, "search_query": search_query},
    )


@login_required(login_url="rooms:login")
def join_normal_room(request, room_id):
    active_since = timezone.now() - timedelta(hours=2)
    room = get_object_or_404(
        Room,
        room_id=room_id.upper(),
        is_active=True,
        created_at__gte=active_since,
    )

    if room.current_players >= room.max_players:
        return redirect("rooms:normal_match")

    access_key = f"room_access_{room.room_id}"
    if not room.has_password:
        request.session[access_key] = True
        query = urlencode(
            {"room_id": room.room_id, "members": room.max_players, "source": "normal"}
        )
        return redirect(f"/wait/?{query}")

    error = ""
    if request.method == "POST":
        password = request.POST.get("password", "")
        if check_password(password, room.password_hash):
            request.session[access_key] = True
            query = urlencode(
                {"room_id": room.room_id, "members": room.max_players, "source": "normal"}
            )
            return redirect(f"/wait/?{query}")
        error = "合言葉が違います。"

    return render(
        request,
        "rooms/room_password.html",
        {"room": room, "error": error},
    )


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
        room = Room.objects.create(
            room_id=room_id,
            host=request.user if request.user.is_authenticated else None,
            max_players=max_players,
            time_limit=time_limit,
            theme=request.POST.get("theme", "").strip()[:80],
            has_password=bool(room_password),
            password_hash=make_password(room_password) if room_password else "",
        )
        request.session[f"room_access_{room.room_id}"] = True
        query = urlencode({"room_id": room.room_id, "members": room.max_players})
        return redirect(f"/wait/?{query}")

    return render(request, "rooms/create_room.html")


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
        if room.has_password and not request.session.get(f"room_access_{room.room_id}"):
            return redirect("rooms:join_normal_room", room_id=room.room_id)
        max_players = room.max_players
        current_players = room.current_players
    else:
        current_players = 1

    return render(
        request,
        "rooms/waiting_room.html",
        {
            "current_players": current_players,
            "max_players": max_players,
            "room_id": room_id,
            "back_to_normal": back_to_normal,
        },
    )

def rule(request):
    return render(request, "rooms/rules.html")
def profile(request):
    return render(request, "rooms/profile.html")

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
    return render(request, "rooms/shop.html")

def ai(request):
    return render(request, "rooms/ai.html")
