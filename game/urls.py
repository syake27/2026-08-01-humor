from django.urls import path

from . import views

app_name = "game"

urlpatterns = [
    path("", views.game, name="game"),
    path("result/", views.room_result, name="room_result"),
    path("players/status/", views.game_players_status, name="players_status"),
    path("stamp/", views.send_stamp, name="send_stamp"),
    path("baba/start/", views.start_baba_challenge, name="start_baba_challenge"),
    path("baba/preview/", views.update_baba_preview, name="update_baba_preview"),
    path("baba/guess/", views.guess_baba, name="guess_baba"),
    path("answer/", views.submit_word, name="submit_word"),
]
