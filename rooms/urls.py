from django.urls import path
from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.home, name="home"),
    path("match/", views.match, name="match"),
    path("match/normal/", views.normal_match, name="normal_match"),
    path("match/normal/<str:room_id>/join/", views.join_normal_room, name="join_normal_room"),
    path("create/", views.create, name="create"),
    path("join/", views.join, name="join"),
    path("rank/", views.rank, name="rank"),
    path("wait/", views.wait, name="wait"),
    path("profile/", views.profile, name="profile"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("logout/", views.logout_page, name="logout"),
    path("shop/", views.shop, name="shop"),
    path("ai/", views.ai, name="ai"),
    path("rule/", views.rule, name="rule"),
]
