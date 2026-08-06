from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("", views.game, name="game"),
    path("result/", views.room_result, name="room_result"),
    path("players/status/", views.game_players_status, name="players_status"),
    path("answer/", views.submit_word, name="submit_word"),
]
