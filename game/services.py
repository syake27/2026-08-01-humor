import secrets

from django.db import transaction
from django.db.models import F

from .models import GamePlayer, GameSession
from rooms.models import DEFAULT_BABA_CHARACTERS, UserProfile
from rooms.services import get_equipped_customization, grant_rank_titles


DEFAULT_PLAYER_TITLE = "はじめての一歩"
COIN_REWARDS = {1: 100, 2: 75, 3: 50, 4: 25}
RANK_RATING_CHANGES = {1: 50, 2: 20, 3: 0, 4: -50}
START_LETTERS = DEFAULT_BABA_CHARACTERS.replace("を", "").replace("ん", "")


def choose_start_letter():
    """単語を始めやすいひらがなからゲーム開始文字を選ぶ。"""
    return secrets.choice(START_LETTERS)


def choose_baba_letter(room, previous_letter=""):
    candidates = list(room.baba_characters or DEFAULT_BABA_CHARACTERS)
    different_candidates = [
        character for character in candidates if character != previous_letter
    ]
    return secrets.choice(different_candidates or candidates)


def coin_reward_for_placement(placement):
    return COIN_REWARDS.get(placement, 0)


def rank_rating_change_for_placement(placement):
    return RANK_RATING_CHANGES.get(placement, 0)


def grant_coin_rewards(session):
    if not session.is_finished or session.coin_rewards_granted:
        return False

    players = session.players.exclude(user=None).exclude(placement=None)
    for player in players:
        reward = coin_reward_for_placement(player.placement)
        if not reward:
            continue
        profile, _ = UserProfile.objects.get_or_create(user_id=player.user_id)
        UserProfile.objects.filter(pk=profile.pk).update(coins=F("coins") + reward)

    session.coin_rewards_granted = True
    session.save(update_fields=["coin_rewards_granted"])
    return True


def grant_rank_rating_rewards(session):
    if (
        not session.is_finished
        or not session.room.is_ranked
        or session.rating_rewards_granted
    ):
        return False

    players = session.players.exclude(user=None).exclude(placement=None)
    for player in players:
        profile, _ = UserProfile.objects.get_or_create(user_id=player.user_id)
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        rating_before = profile.rating
        rating_change = rank_rating_change_for_placement(player.placement)
        if player.placement == 1 and player.rate_boost_active:
            rating_change = round(rating_change * 1.3)
        rating_after = max(0, rating_before + rating_change)

        profile.rating = rating_after
        profile.save(update_fields=["rating"])
        grant_rank_titles(player.user, rating_after)
        player.rating_before = rating_before
        player.rating_change = rating_change
        player.rating_after = rating_after
        player.save(
            update_fields=["rating_before", "rating_change", "rating_after"]
        )

    session.rating_rewards_granted = True
    session.save(update_fields=["rating_rewards_granted"])
    return True


def grant_result_rewards(session):
    coin_granted = grant_coin_rewards(session)
    rating_granted = grant_rank_rating_rewards(session)
    return coin_granted or rating_granted


def ensure_game_session(room):
    with transaction.atomic():
        session, _ = GameSession.objects.get_or_create(
            room=room,
            defaults={"current_letter": choose_start_letter()},
        )
        if not session.baba_letter:
            session.baba_letter = choose_baba_letter(room)
            session.save(update_fields=["baba_letter"])

        if session.players.exists():
            # 以前はルーム作成者の称号を強制的に変更していたため、
            # プロフィールで設定されている通常の称号へ戻す。
            session.players.filter(title="ルームマスター").update(
                title=DEFAULT_PLAYER_TITLE
            )
            return session

        users = []
        seen_user_ids = set()

        if room.host_id:
            users.append(room.host)
            seen_user_ids.add(room.host_id)

        for participant in room.participants.select_related("user").order_by("joined_at"):
            if participant.user_id not in seen_user_ids:
                users.append(participant.user)
                seen_user_ids.add(participant.user_id)

        GamePlayer.objects.bulk_create(
            [
                GamePlayer(
                    session=session,
                    user=user,
                    display_name=user.username,
                    title=get_equipped_customization(user)["title_name"],
                    remaining_seconds=room.time_limit,
                    turn_order=index,
                )
                for index, user in enumerate(users)
            ]
        )
        return session
