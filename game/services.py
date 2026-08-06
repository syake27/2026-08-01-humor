import secrets

from django.db import transaction
from django.db.models import F

from .models import GamePlayer, GameSession
from rooms.models import DEFAULT_BABA_CHARACTERS, UserProfile


DEFAULT_PLAYER_TITLE = "はじめての一歩"
COIN_REWARDS = {1: 100, 2: 75, 3: 50, 4: 25}


def choose_baba_letter(room, previous_letter=""):
    candidates = list(room.baba_characters or DEFAULT_BABA_CHARACTERS)
    different_candidates = [
        character for character in candidates if character != previous_letter
    ]
    return secrets.choice(different_candidates or candidates)


def coin_reward_for_placement(placement):
    return COIN_REWARDS.get(placement, 0)


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


def ensure_game_session(room):
    with transaction.atomic():
        session, _ = GameSession.objects.get_or_create(room=room)
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
                    title=DEFAULT_PLAYER_TITLE,
                    remaining_seconds=room.time_limit,
                    turn_order=index,
                )
                for index, user in enumerate(users)
            ]
        )
        return session
