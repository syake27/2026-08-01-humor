from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rooms.models import Room, UserProfile

from .models import GamePlayer, GameSession
from .services import coin_reward_for_placement
from .views import _matches_current_letter


class GameResultFlowTests(TestCase):
    def test_coin_rewards_match_each_placement(self):
        self.assertEqual(coin_reward_for_placement(1), 100)
        self.assertEqual(coin_reward_for_placement(2), 75)
        self.assertEqual(coin_reward_for_placement(3), 50)
        self.assertEqual(coin_reward_for_placement(4), 25)

    def test_voiced_current_letter_accepts_unvoiced_start(self):
        self.assertTrue(_matches_current_letter("かめ", "が"))
        self.assertTrue(_matches_current_letter("さる", "ざ"))
        self.assertTrue(_matches_current_letter("はと", "ば"))
        self.assertTrue(_matches_current_letter("はな", "ぱ"))
        self.assertFalse(_matches_current_letter("がく", "か"))

    def test_baba_hit_finishes_two_player_game_and_assigns_placements(self):
        user_model = get_user_model()
        first_user = user_model.objects.create_user("first-player", password="test")
        second_user = user_model.objects.create_user("second-player", password="test")
        room = Room.objects.create(
            room_id="TEST",
            host=first_user,
            max_players=2,
            is_started=True,
            baba_characters="ご",
        )
        session = GameSession.objects.create(
            room=room,
            current_letter="り",
            baba_letter="ご",
        )
        first_player = GamePlayer.objects.create(
            session=session,
            user=first_user,
            display_name=first_user.username,
            turn_order=0,
        )
        second_player = GamePlayer.objects.create(
            session=session,
            user=second_user,
            display_name=second_user.username,
            turn_order=1,
        )

        self.client.force_login(first_user)
        response = self.client.post(
            reverse("game:submit_word"),
            {"room_id": room.room_id, "answer": "りんご"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_finished"])
        self.assertIn(reverse("game:room_result"), response.json()["result_url"])
        first_player.refresh_from_db()
        second_player.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(first_player.placement, 2)
        self.assertFalse(first_player.is_alive)
        self.assertEqual(second_player.placement, 1)
        self.assertTrue(session.is_finished)
        self.assertTrue(session.coin_rewards_granted)
        self.assertEqual(UserProfile.objects.get(user=first_user).coins, 75)
        self.assertEqual(UserProfile.objects.get(user=second_user).coins, 100)

        result_response = self.client.get(response.json()["result_url"])
        self.assertEqual(result_response.status_code, 200)
        self.assertTemplateUsed(result_response, "rooms/base.html")
        self.assertTemplateUsed(result_response, "rooms/result/room_result.html")
        self.assertEqual(result_response.context["current_player"].placement, 2)
        self.assertEqual(result_response.context["coin_reward"], 75)
        self.client.get(response.json()["result_url"])
        self.assertEqual(UserProfile.objects.get(user=first_user).coins, 75)
