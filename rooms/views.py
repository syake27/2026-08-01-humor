from django.shortcuts import render


def home(request):
    return render(request, "rooms/home.html")


def match(request):
    return render(request, "rooms/match.html")


def create(request):
    return render(request, "rooms/create_room.html")


def join(request):
    return render(request, "rooms/join_room.html")


def rank(request):
    return render(request, "rooms/rank.html")


def wait(request):
    try:
        max_players = int(request.GET.get("members", 4))
    except (TypeError, ValueError):
        max_players = 4

    max_players = max(2, min(4, max_players))
    room_id = request.GET.get("room_id", "A7K9").strip().upper()[:8] or "A7K9"

    return render(
        request,
        "rooms/waiting_room.html",
        {
            "current_players": 1,
            "max_players": max_players,
            "room_id": room_id,
        },
    )

def rule(request):
    return render(request, "rooms/rules.html")
def profile(request):
    return render(request, "rooms/profile.html")

def shop(request):
    return render(request, "rooms/shop.html")

def ai(request):
    return render(request, "rooms/taisengamenn.html")
