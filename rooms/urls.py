from django.urls import path
from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.home, name="home"),
    path("match/", views.match, name="match"),
    path("create/", views.create, name="create"),
    path("join/", views.join, name="join"),
    path("rank/", views.rank, name="rank"),
    path("wait/", views.wait, name="wait"),
    path("profile/", views.profile, name="profile"),
    path("shop/", views.shop, name="shop"),
    path("rule/", views.rule, name="rule")
]
