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
    return render(request, "rooms/waiting_room.html")

def profile(request):
    return render(request, "rooms/profile.html")

def shop(request):
    return render(request, "rooms/shop.html")

def ai(request):
    return render(request, "rooms/taisengamenn.html")

def rule(request):
    return render(request, "rooms/rule.html")

