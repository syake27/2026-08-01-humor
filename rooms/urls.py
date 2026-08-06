from django.urls import path
from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.home, name="home"),
    path("match/", views.match, name="match"),
    path("match/normal/", views.normal_match, name="normal_match"),
    path("match/normal/status/", views.normal_match_status, name="normal_match_status"),
    path("match/normal/<str:room_id>/join/", views.join_normal_room, name="join_normal_room"),
    path("match/normal/<str:room_id>/leave/", views.leave_normal_room, name="leave_normal_room"),
    path("room/<str:room_id>/start/", views.start_room, name="start_room"),
    path("create/", views.create, name="create"),
    path("join/", views.join, name="join"),
    path("rank/", views.rank, name="rank"),
    path("wait/", views.wait, name="wait"),
    path("room/<str:room_id>/status/", views.room_status, name="room_status"),
    path("profile/", views.profile, name="profile"),
    path("profile/stats/", views.battle_stats, name="battle_stats"),
    path("profile/ranks/", views.rank_rates, name="rank_rates"),
    path("profile/items/", views.inventory, name="inventory"),
    path("profile/items/equip/", views.equip_item, name="equip_item"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("logout/", views.logout_page, name="logout"),
    path("shop/", views.shop, name="shop"),
    path("ai/", views.ai, name="ai"),
    path("rule/", views.rule, name="rule"),
]
