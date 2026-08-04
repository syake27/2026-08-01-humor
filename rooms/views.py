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

def rule(request):
    return render(request, "rooms/rules.html")