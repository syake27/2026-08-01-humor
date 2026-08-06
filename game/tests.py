from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rooms.models import OwnedItem, Room, UserProfile

from .models import GamePlayer, GameSession, GameStamp
from .services import (
    ensure_game_session,
    coin_reward_for_placement,
    rank_rating_change_for_placement,
)
from .views import _matches_current_letter
from rooms.views import _get_rank_data


class GameResultFlowTests(TestCase):
    def test_new_game_uses_a_random_start_letter(self):
        room = Room.objects.create(room_id="RANDOM")

        with patch("game.services.choose_start_letter", return_value="さ"):
            session = ensure_game_session(room)

        self.assertEqual(session.current_letter, "さ")

    def test_current_player_explodes_and_is_eliminated_when_time_reaches_zero(self):
        user_model = get_user_model()
        users = [
            user_model.objects.create_user(f"timer-{index}", password="test")
            for index in range(3)
        ]
        room = Room.objects.create(
            room_id="TIMER",
            host=users[0],
            max_players=3,
            is_started=True,
        )
        session = GameSession.objects.create(room=room, current_turn_order=0)
        players = [
            GamePlayer.objects.create(
                session=session,
                user=user,
                display_name=user.username,
                remaining_seconds=1 if index == 0 else 30,
                turn_order=index,
            )
            for index, user in enumerate(users)
        ]
        GameSession.objects.filter(pk=session.pk).update(
            turn_started_at=timezone.now() - timedelta(seconds=2)
        )

        self.client.force_login(users[0])
        response = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["baba_reveal"]["mode"], "timeout")
        players[0].refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(players[0].remaining_seconds, 0)
        self.assertFalse(players[0].is_alive)
        self.assertEqual(players[0].placement, 3)
        self.assertEqual(session.current_turn_order, 1)

    def test_correct_baba_guess_secures_first_and_game_continues(self):
        user_model = get_user_model()
        users = [
            user_model.objects.create_user(f"guess-{index}", password="test")
            for index in range(3)
        ]
        room = Room.objects.create(
            room_id="GUESS",
            host=users[0],
            max_players=3,
            is_started=True,
            baba_characters="あいう",
        )
        session = GameSession.objects.create(room=room, baba_letter="い")
        players = [
            GamePlayer.objects.create(
                session=session,
                user=user,
                display_name=user.username,
                turn_order=index,
            )
            for index, user in enumerate(users)
        ]

        self.client.force_login(users[1])
        start_response = self.client.post(
            reverse("game:start_baba_challenge"),
            {"room_id": room.room_id},
        )
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(
            start_response.json()["baba_challenge"]["player_name"],
            users[1].username,
        )
        preview_response = self.client.post(
            reverse("game:update_baba_preview"),
            {"room_id": room.room_id, "preview": "い"},
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.json()["preview"], "い")
        self.client.force_login(users[0])
        status_response = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )
        self.assertFalse(status_response.json()["baba_challenge"]["is_self"])
        self.assertEqual(status_response.json()["baba_challenge"]["preview"], "い")
        blocked_answer = self.client.post(
            reverse("game:submit_word"),
            {"room_id": room.room_id, "answer": "きつね"},
        )
        self.assertEqual(blocked_answer.status_code, 409)
        self.assertIn("BABAの挑戦中", blocked_answer.json()["error"])
        self.client.force_login(users[1])
        response = self.client.post(
            reverse("game:guess_baba"),
            {"room_id": room.room_id, "baba_letter": "い"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["correct"])
        self.assertFalse(response.json()["is_finished"])
        self.assertTrue(response.json()["baba_reveal"]["active"])
        self.assertTrue(response.json()["baba_reveal"]["correct"])
        session.refresh_from_db()
        for player in players:
            player.refresh_from_db()
        self.assertFalse(session.is_finished)
        self.assertEqual(players[1].placement, 1)
        self.assertFalse(players[1].is_alive)
        self.assertIsNone(players[0].placement)
        self.assertIsNone(players[2].placement)
        self.assertTrue(players[0].is_alive)
        self.assertTrue(players[2].is_alive)
        self.assertFalse(UserProfile.objects.filter(user=users[1]).exists())

        session.baba_reveal_until = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["baba_reveal_until"])
        status_after_reveal = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )
        self.assertFalse(status_after_reveal.json()["is_finished"])
        self.assertIsNone(status_after_reveal.json()["baba_challenge"])

        self.client.force_login(users[0])
        second_challenge = self.client.post(
            reverse("game:start_baba_challenge"),
            {"room_id": room.room_id},
        )
        self.assertEqual(second_challenge.status_code, 200)
        final_guess = self.client.post(
            reverse("game:guess_baba"),
            {"room_id": room.room_id, "baba_letter": "あ"},
        )
        self.assertEqual(final_guess.status_code, 200)
        session.refresh_from_db()
        for player in players:
            player.refresh_from_db()
        self.assertTrue(session.is_finished)
        self.assertEqual(players[0].placement, 3)
        self.assertEqual(players[1].placement, 1)
        self.assertEqual(players[2].placement, 2)
        self.assertEqual(UserProfile.objects.get(user=users[1]).coins, 100)
        self.assertEqual(UserProfile.objects.get(user=users[2]).coins, 75)
        self.assertEqual(UserProfile.objects.get(user=users[0]).coins, 50)

    def test_wrong_baba_guess_eliminates_player_and_advances_turn(self):
        user_model = get_user_model()
        users = [
            user_model.objects.create_user(f"miss-{index}", password="test")
            for index in range(3)
        ]
        room = Room.objects.create(
            room_id="MISS",
            host=users[0],
            max_players=3,
            is_started=True,
            baba_characters="あいう",
        )
        session = GameSession.objects.create(
            room=room,
            baba_letter="い",
            current_turn_order=0,
        )
        player = GamePlayer.objects.create(
            session=session,
            user=users[0],
            display_name=users[0].username,
            turn_order=0,
        )
        for index, user in enumerate(users[1:], start=1):
            GamePlayer.objects.create(
                session=session,
                user=user,
                display_name=user.username,
                turn_order=index,
            )

        self.client.force_login(users[0])
        start_response = self.client.post(
            reverse("game:start_baba_challenge"),
            {"room_id": room.room_id},
        )
        self.assertEqual(start_response.status_code, 200)
        response = self.client.post(
            reverse("game:guess_baba"),
            {"room_id": room.room_id, "baba_letter": "あ"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["correct"])
        self.assertFalse(response.json()["is_finished"])
        player.refresh_from_db()
        session.refresh_from_db()
        self.assertFalse(player.is_alive)
        self.assertEqual(player.placement, 3)
        self.assertEqual(session.current_turn_order, 1)
        self.assertIn("脱落です", response.json()["message"])
        game_response = self.client.get(
            f'{reverse("game:game")}?room_id={room.room_id}'
        )
        self.assertEqual(game_response.status_code, 200)
        self.assertContains(game_response, 'id="baba-guess-modal"')
        self.assertContains(game_response, "外したらその場で")

    def test_owned_stamp_can_be_sent_to_every_player(self):
        user_model = get_user_model()
        user = user_model.objects.create_user("stamp-player", password="test")
        room = Room.objects.create(
            room_id="STAMP",
            host=user,
            max_players=2,
            is_started=True,
        )
        session = GameSession.objects.create(room=room)
        player = GamePlayer.objects.create(
            session=session,
            user=user,
            display_name=user.username,
            turn_order=0,
        )
        stamp_item = OwnedItem.objects.create(
            user=user,
            item_code="stamp_nice",
            item_type="stamp",
            name="ナイス！",
            icon="👍",
            is_equipped=True,
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("game:send_stamp"),
            {"room_id": room.room_id, "stamp_code": stamp_item.item_code},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stamp"]["player_id"], player.id)
        self.assertEqual(response.json()["stamp"]["icon"], "👍")
        self.assertEqual(GameStamp.objects.filter(session=session).count(), 1)

        status = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["stamps"][0]["name"], "ナイス！")

    def test_image_stamp_is_sent_with_its_static_image(self):
        user_model = get_user_model()
        user = user_model.objects.create_user("coconut-player", password="test")
        room = Room.objects.create(
            room_id="COCO",
            host=user,
            max_players=2,
            is_started=True,
        )
        session = GameSession.objects.create(room=room)
        GamePlayer.objects.create(
            session=session,
            user=user,
            display_name=user.username,
            turn_order=0,
        )
        OwnedItem.objects.create(
            user=user,
            item_code="stamp_coconut",
            item_type="stamp",
            name="ココナッツスタンプ",
            is_equipped=True,
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("game:send_stamp"),
            {"room_id": room.room_id, "stamp_code": "stamp_coconut"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["stamp"]["image_url"],
            "/static/rooms/images/stamps/stamp_coconut.png",
        )
        status = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )
        self.assertEqual(
            status.json()["stamps"][0]["image_url"],
            "/static/rooms/images/stamps/stamp_coconut.png",
        )

    def test_rating_resolves_current_and_next_rank(self):
        rank_data = _get_rank_data(1000)
        self.assertEqual(rank_data["current_rank"]["name"], "ビギナー I")
        self.assertEqual(rank_data["next_rank"]["name"], "ビギナー II")
        self.assertEqual(rank_data["rate_to_next"], 100)

    def test_coin_rewards_match_each_placement(self):
        self.assertEqual(coin_reward_for_placement(1), 100)
        self.assertEqual(coin_reward_for_placement(2), 75)
        self.assertEqual(coin_reward_for_placement(3), 50)
        self.assertEqual(coin_reward_for_placement(4), 25)

    def test_rank_match_result_updates_rating_once_and_displays_rank(self):
        user_model = get_user_model()
        users = [
            user_model.objects.create_user(
                f"rank-result-{index}",
                password="test",
            )
            for index in range(1, 5)
        ]
        room = Room.objects.create(
            room_id="RANKED",
            host=users[0],
            max_players=4,
            current_players=4,
            is_started=True,
            is_ranked=True,
        )
        session = GameSession.objects.create(room=room, is_finished=True)
        players = [
            GamePlayer.objects.create(
                session=session,
                user=user,
                display_name=user.username,
                placement=index,
                is_alive=index == 1,
                turn_order=index - 1,
            )
            for index, user in enumerate(users, start=1)
        ]

        self.client.force_login(users[0])
        result_url = f'{reverse("game:room_result")}?room_id={room.room_id}'
        response = self.client.get(result_url)

        self.assertEqual(response.status_code, 200)
        expected_ratings = [1050, 1020, 1000, 950]
        expected_changes = [50, 20, 0, -50]
        for user, player, rating, rating_change in zip(
            users,
            players,
            expected_ratings,
            expected_changes,
        ):
            player.refresh_from_db()
            self.assertEqual(UserProfile.objects.get(user=user).rating, rating)
            self.assertEqual(player.rating_before, 1000)
            self.assertEqual(player.rating_change, rating_change)
            self.assertEqual(player.rating_after, rating)

        self.assertTrue(response.context["is_ranked"])
        self.assertEqual(response.context["rank_rating_change"], 50)
        self.assertEqual(response.context["rank_data"]["rating"], 1050)
        self.assertContains(response, "ビギナー I")
        self.assertContains(response, "＋50")
        self.assertContains(response, "RATE 1050")
        self.assertContains(response, "RATE 1020")
        self.assertContains(response, "＋20")
        self.assertContains(response, "±0")
        self.assertContains(response, "-50")

        self.client.get(result_url)
        self.assertEqual(UserProfile.objects.get(user=users[0]).rating, 1050)

    def test_rank_rating_changes_match_each_placement(self):
        self.assertEqual(rank_rating_change_for_placement(1), 50)
        self.assertEqual(rank_rating_change_for_placement(2), 20)
        self.assertEqual(rank_rating_change_for_placement(3), 0)
        self.assertEqual(rank_rating_change_for_placement(4), -50)

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
        self.assertFalse(response.json()["is_finished"])
        self.assertEqual(response.json()["baba_reveal"]["mode"], "word")
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

        session.baba_reveal_until = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["baba_reveal_until"])
        status_response = self.client.get(
            f'{reverse("game:players_status")}?room_id={room.room_id}'
        )
        self.assertTrue(status_response.json()["is_finished"])
        result_url = status_response.json()["result_url"]
        self.assertIn(reverse("game:room_result"), result_url)

        result_response = self.client.get(result_url)
        self.assertEqual(result_response.status_code, 200)
        self.assertTemplateUsed(result_response, "rooms/base.html")
        self.assertTemplateUsed(result_response, "rooms/result/room_result.html")
        self.assertEqual(result_response.context["current_player"].placement, 2)
        self.assertEqual(result_response.context["coin_reward"], 75)
        self.client.get(result_url)
        self.assertEqual(UserProfile.objects.get(user=first_user).coins, 75)

        stats_response = self.client.get(reverse("rooms:battle_stats"))
        self.assertEqual(stats_response.status_code, 200)
        self.assertTemplateUsed(stats_response, "rooms/base.html")
        self.assertTemplateUsed(stats_response, "rooms/battle_stats.html")
        stats_context = next(
            context["battle_stats"]
            for context in stats_response.context
            if context.get("battle_stats") is not None
        )
        self.assertEqual(stats_context["battle_count"], 1)
        self.assertEqual(stats_context["win_count"], 0)
        self.assertEqual(stats_context["total_words"], 1)
        self.assertEqual(stats_context["rank_counts"][2], 1)

        inventory_response = self.client.get(reverse("rooms:inventory"))
        self.assertEqual(inventory_response.status_code, 200)
        self.assertTemplateUsed(inventory_response, "rooms/base.html")
        self.assertEqual(inventory_response.context["item_count"], 4)
        self.assertEqual(OwnedItem.objects.filter(user=first_user).count(), 4)

        avatar_response = self.client.get(
            f'{reverse("rooms:inventory")}?type=avatar'
        )
        self.assertEqual(avatar_response.status_code, 200)
        self.assertEqual(avatar_response.context["selected_type"], "avatar")
        self.assertEqual(avatar_response.context["page_title"], "アバター一覧")
        self.assertEqual(avatar_response.context["item_count"], 1)
        self.assertEqual(len(avatar_response.context["item_groups"]), 1)
        self.assertEqual(
            avatar_response.context["item_groups"][0]["key"],
            "avatar",
        )

        avatar_all_response = self.client.get(
            f'{reverse("rooms:inventory")}?type=avatar&include=1'
        )
        self.assertEqual(avatar_all_response.status_code, 200)
        self.assertTrue(avatar_all_response.context["include_unowned"])
        avatar_items = avatar_all_response.context["item_groups"][0]["items"]
        self.assertEqual(len(avatar_items), 5)
        self.assertEqual(sum(item["is_owned"] for item in avatar_items), 1)
        self.assertEqual(sum(not item["is_owned"] for item in avatar_items), 4)
        palm_avatar = next(
            item
            for item in avatar_items
            if item["item_code"] == "avatar_palm_limited"
        )
        self.assertEqual(
            palm_avatar["image_path"],
            "rooms/images/icons/avatar_palm_limited.png",
        )
        frame_all_response = self.client.get(
            f'{reverse("rooms:inventory")}?type=frame&include=1'
        )
        tropical_frame = next(
            item
            for item in frame_all_response.context["item_groups"][0]["items"]
            if item["item_code"] == "frame_tropical_beach"
        )
        self.assertEqual(
            tropical_frame["image_path"],
            "rooms/images/frames/frame_tropical_beach.png",
        )

        for item_type, page_title in (
            ("frame", "フレーム一覧"),
            ("stamp", "スタンプ一覧"),
        ):
            filtered_response = self.client.get(
                f'{reverse("rooms:inventory")}?type={item_type}'
            )
            self.assertEqual(filtered_response.status_code, 200)
            self.assertEqual(filtered_response.context["selected_type"], item_type)
            self.assertEqual(filtered_response.context["page_title"], page_title)
            self.assertEqual(filtered_response.context["item_count"], 1)

        customize_response = self.client.get(
            f'{reverse("rooms:inventory")}?type=customize'
        )
        self.assertEqual(customize_response.status_code, 200)
        self.assertEqual(customize_response.context["selected_type"], "customize")
        self.assertEqual(customize_response.context["page_title"], "カスタマイズ一覧")
        self.assertEqual(customize_response.context["item_count"], 4)
        self.assertEqual(
            [group["key"] for group in customize_response.context["item_groups"]],
            ["avatar", "frame", "stamp", "title"],
        )

        second_avatar = OwnedItem.objects.create(
            user=first_user,
            item_code="avatar_cat",
            item_type="avatar",
            name="ねこ",
            icon="🐱",
        )
        equip_response = self.client.post(
            reverse("rooms:equip_item"),
            {"item_code": second_avatar.item_code},
        )
        self.assertEqual(equip_response.status_code, 200)
        second_avatar.refresh_from_db()
        default_avatar = OwnedItem.objects.get(
            user=first_user,
            item_code="default_penguin",
        )
        self.assertTrue(second_avatar.is_equipped)
        self.assertFalse(default_avatar.is_equipped)

        locked_response = self.client.post(
            reverse("rooms:equip_item"),
            {"item_code": "avatar_robot"},
        )
        self.assertEqual(locked_response.status_code, 404)

        rank_response = self.client.get(reverse("rooms:rank_rates"))
        self.assertEqual(rank_response.status_code, 200)
        self.assertTemplateUsed(rank_response, "rooms/base.html")
        self.assertTemplateUsed(rank_response, "rooms/rank_rates.html")
        self.assertEqual(rank_response.context["rank_data"]["rating"], 1000)
        self.assertEqual(
            rank_response.context["rank_data"]["current_rank"]["name"],
            "ビギナー I",
        )
