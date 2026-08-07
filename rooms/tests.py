from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import GamePlayer, GameSession

from .models import (
    DEFAULT_BABA_CHARACTERS,
    OwnedItem,
    RankMatchEntry,
    Room,
    RoomParticipant,
    ShopPurchaseHistory,
    UserProfile,
)
from .services import ensure_default_owned_items


class ShopPurchaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shop_player",
            password="pass",
        )
        self.client.force_login(self.user)
        self.profile = UserProfile.objects.create(user=self.user, coins=1000)

    def test_item_purchase_deducts_coins_and_adds_owned_item(self):
        response = self.client.post(
            reverse("rooms:purchase_shop_item"),
            {"item_code": "avatar_palm_limited"},
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 200)
        item = OwnedItem.objects.get(
            user=self.user,
            item_code="avatar_palm_limited",
        )
        self.assertEqual(item.item_type, "avatar")
        self.assertEqual(item.name, "トロピカルパーム")
        self.assertEqual(response.json()["coin_balance"], 200)
        history = ShopPurchaseHistory.objects.get(user=self.user)
        self.assertEqual(history.item_code, "avatar_palm_limited")
        self.assertEqual(history.item_name, "トロピカルパーム")
        self.assertEqual(history.quantity, 1)
        self.assertEqual(history.coins_spent, 800)

        duplicate_response = self.client.post(
            reverse("rooms:purchase_shop_item"),
            {"item_code": "avatar_palm_limited"},
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 200)
        self.assertEqual(
            OwnedItem.objects.filter(
                user=self.user,
                item_code="avatar_palm_limited",
            ).count(),
            1,
        )

    def test_purchase_is_rejected_when_coins_are_insufficient(self):
        self.profile.coins = 100
        self.profile.save(update_fields=["coins"])

        response = self.client.post(
            reverse("rooms:purchase_shop_item"),
            {"item_code": "card_help_limited"},
        )

        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 100)
        self.assertFalse(
            OwnedItem.objects.filter(
                user=self.user,
                item_code="card_help_limited",
            ).exists()
        )
        self.assertFalse(ShopPurchaseHistory.objects.filter(user=self.user).exists())

    def test_card_can_be_purchased_repeatedly_up_to_99(self):
        for expected_quantity in (1, 2):
            response = self.client.post(
                reverse("rooms:purchase_shop_item"),
                {"item_code": "card_skip"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["quantity"], expected_quantity)

        card = OwnedItem.objects.get(
            user=self.user,
            item_code="card_skip",
        )
        self.assertEqual(card.quantity, 2)
        self.assertEqual(
            OwnedItem.objects.filter(
                user=self.user,
                item_code="card_skip",
            ).count(),
            1,
        )

    def test_card_purchase_is_rejected_at_99(self):
        OwnedItem.objects.create(
            user=self.user,
            item_code="card_skip",
            item_type="card",
            name="スキップカード",
            quantity=99,
        )

        response = self.client.post(
            reverse("rooms:purchase_shop_item"),
            {"item_code": "card_skip"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["quantity"], 99)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.coins, 1000)

    def test_shop_marks_owned_products_as_purchased(self):
        OwnedItem.objects.create(
            user=self.user,
            item_code="frame_tropical_beach",
            item_type="frame",
            name="トロピカルビーチ",
            icon="◯",
        )

        response = self.client.get(reverse("rooms:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "所持済み")
        self.assertContains(response, 'id="purchase-modal"')
        self.assertContains(response, 'id="purchase-history-modal"')
        self.assertContains(response, "商品詳細")
        self.assertContains(response, "購入する")
        self.assertIn(
            "frame_tropical_beach",
            response.context["owned_item_codes"],
        )

    def test_equipped_customization_is_used_on_profile(self):
        ensure_default_owned_items(self.user)
        items = [
            OwnedItem.objects.create(
                user=self.user,
                item_code="avatar_palm_limited",
                item_type="avatar",
                name="トロピカルパーム",
            ),
            OwnedItem.objects.create(
                user=self.user,
                item_code="frame_tropical_beach",
                item_type="frame",
                name="トロピカルビーチ",
                icon="◯",
            ),
            OwnedItem.objects.create(
                user=self.user,
                item_code="stamp_coconut",
                item_type="stamp",
                name="ココナッツスタンプ",
            ),
            OwnedItem.objects.create(
                user=self.user,
                item_code="title_baba_hunter",
                item_type="title",
                name="ババハンター",
                icon="◆",
            ),
        ]
        for item in items:
            response = self.client.post(
                reverse("rooms:equip_item"),
                {"item_code": item.item_code},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("rooms:profile"))
        customization = response.context["customization"]
        self.assertEqual(
            customization["avatar_image_path"],
            "rooms/images/icons/avatar_palm_limited.png",
        )
        self.assertEqual(customization["frame_class"], "frame-tropical-beach")
        self.assertEqual(
            customization["frame_image_path"],
            "rooms/images/frames/frame_tropical_beach.png",
        )
        self.assertEqual(
            customization["stamp_image_path"],
            "rooms/images/stamps/stamp_coconut_good.png",
        )
        self.assertEqual(customization["title_name"], "ババハンター")
        self.assertContains(response, "avatar_palm_limited.png")
        self.assertContains(response, "stamp_coconut_good.png")
        self.assertContains(response, "ババハンター")

    def test_card_cannot_be_equipped(self):
        card = OwnedItem.objects.create(
            user=self.user,
            item_code="card_help_limited",
            item_type="card",
            name="レートブースト",
            icon="⚡",
        )

        response = self.client.post(
            reverse("rooms:equip_item"),
            {"item_code": card.item_code},
        )

        self.assertEqual(response.status_code, 400)
        card.refresh_from_db()
        self.assertFalse(card.is_equipped)

    def test_stamps_allow_up_to_six_equipped_items(self):
        stamps = [
            OwnedItem.objects.create(
                user=self.user,
                item_code=f"stamp_test_{index}",
                item_type="stamp",
                name=f"テストスタンプ{index}",
            )
            for index in range(7)
        ]

        for stamp in stamps[:6]:
            response = self.client.post(
                reverse("rooms:equip_item"),
                {"item_code": stamp.item_code},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("rooms:equip_item"),
            {"item_code": stamps[6].item_code},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            OwnedItem.objects.filter(
                user=self.user,
                item_type="stamp",
                is_equipped=True,
            ).count(),
            6,
        )
        stamps[6].refresh_from_db()
        self.assertFalse(stamps[6].is_equipped)

    def test_equipped_stamp_can_be_unequipped(self):
        stamp = OwnedItem.objects.create(
            user=self.user,
            item_code="stamp_toggle",
            item_type="stamp",
            name="解除テストスタンプ",
            is_equipped=True,
        )

        response = self.client.post(
            reverse("rooms:equip_item"),
            {"item_code": stamp.item_code},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_equipped"])
        self.assertIn("装備を解除", response.json()["message"])
        stamp.refresh_from_db()
        self.assertFalse(stamp.is_equipped)

    def test_equipped_avatar_frame_and_title_are_used_in_game(self):
        ensure_default_owned_items(self.user)
        OwnedItem.objects.filter(
            user=self.user,
            item_type__in=["avatar", "frame", "title"],
        ).update(is_equipped=False)
        OwnedItem.objects.create(
            user=self.user,
            item_code="avatar_palm_limited",
            item_type="avatar",
            name="トロピカルパーム",
            is_equipped=True,
        )
        OwnedItem.objects.create(
            user=self.user,
            item_code="frame_tropical_beach",
            item_type="frame",
            name="トロピカルビーチ",
            icon="◯",
            is_equipped=True,
        )
        OwnedItem.objects.create(
            user=self.user,
            item_code="title_baba_hunter",
            item_type="title",
            name="ババハンター",
            icon="◆",
            is_equipped=True,
        )
        OwnedItem.objects.create(
            user=self.user,
            item_code="card_skip",
            item_type="card",
            name="スキップカード",
            quantity=2,
        )
        room = Room.objects.create(
            room_id="EQUIP",
            host=self.user,
            max_players=2,
            is_started=True,
        )
        session = GameSession.objects.create(room=room)
        GamePlayer.objects.create(
            session=session,
            user=self.user,
            display_name=self.user.username,
            turn_order=0,
        )

        response = self.client.get(
            f'{reverse("game:game")}?room_id={room.room_id}'
        )

        self.assertEqual(response.status_code, 200)
        player = response.context["players"][0]
        self.assertEqual(
            player.avatar_image_path,
            "rooms/images/icons/avatar_palm_limited.png",
        )
        self.assertEqual(player.frame_class, "frame-tropical-beach")
        self.assertEqual(
            player.frame_image_path,
            "rooms/images/frames/frame_tropical_beach.png",
        )
        self.assertEqual(player.title, "ババハンター")
        self.assertEqual(
            [item.item_code for item in response.context["owned_game_items"]],
            ["card_skip"],
        )
        self.assertEqual(response.context["owned_game_items"][0].quantity, 2)
        self.assertContains(response, "avatar_palm_limited.png")
        self.assertContains(response, "frame_tropical_beach.png")
        self.assertContains(response, "card_skip.png")


class CreateRoomTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="room_creator",
            password="pass",
        )
        self.client.force_login(self.user)

    def test_create_page_uses_60_second_slider_default(self):
        response = self.client.get(reverse("rooms:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="range"')
        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="90"')
        self.assertContains(response, 'value="60"')

    def test_room_accepts_any_time_between_1_and_90_seconds(self):
        response = self.client.post(
            reverse("rooms:create"),
            {
                "members": "4",
                "time": "17",
                "baba_characters": DEFAULT_BABA_CHARACTERS,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Room.objects.get(host=self.user).time_limit, 17)

    def test_room_time_is_clamped_to_slider_range(self):
        for submitted, expected in (("0", 1), ("91", 90)):
            response = self.client.post(
                reverse("rooms:create"),
                {
                    "members": "4",
                    "time": submitted,
                    "baba_characters": DEFAULT_BABA_CHARACTERS,
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                Room.objects.filter(host=self.user).latest("id").time_limit,
                expected,
            )


class RankMatchTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.users = [
            user_model.objects.create_user(
                username=f"rank_player_{index}",
                password="pass",
            )
            for index in range(1, 5)
        ]
        self.clients = []
        for user in self.users:
            client = Client()
            client.force_login(user)
            self.clients.append(client)

    def test_four_waiting_players_are_matched_into_one_rank_room(self):
        for client in self.clients[:3]:
            response = client.get(reverse("rooms:rank"))
            self.assertEqual(response.status_code, 200)

        self.assertEqual(Room.objects.filter(is_ranked=True).count(), 0)
        response = self.clients[3].get(reverse("rooms:rank"))
        self.assertEqual(response.status_code, 200)

        room = Room.objects.get(is_ranked=True)
        self.assertEqual(room.max_players, 4)
        self.assertEqual(room.current_players, 4)
        self.assertEqual(RoomParticipant.objects.filter(room=room).count(), 4)
        self.assertEqual(
            RankMatchEntry.objects.filter(room=room).count(),
            4,
        )

    def test_countdown_starts_the_game_for_every_player(self):
        for client in self.clients:
            client.get(reverse("rooms:rank"))

        room = Room.objects.get(is_ranked=True)
        RankMatchEntry.objects.filter(room=room).update(
            matched_at=timezone.now() - timedelta(seconds=5)
        )
        response = self.clients[0].get(reverse("rooms:rank_match_status"))
        state = response.json()

        room.refresh_from_db()
        self.assertTrue(state["matched"])
        self.assertTrue(state["is_started"])
        self.assertIn(room.room_id, state["game_url"])
        self.assertTrue(room.is_started)
        session = GameSession.objects.get(room=room)
        self.assertEqual(session.players.count(), 4)

    def test_player_can_leave_before_match_is_fixed(self):
        self.clients[0].get(reverse("rooms:rank"))
        response = self.clients[0].post(reverse("rooms:leave_rank_match"))

        self.assertRedirects(response, reverse("rooms:match"))
        self.assertFalse(
            RankMatchEntry.objects.filter(user=self.users[0]).exists()
        )
