import secrets

from django.db import transaction

from .models import GamePlayer, GameSession
from rooms.models import DEFAULT_BABA_CHARACTERS


DEFAULT_PLAYER_TITLE = "はじめての一歩"


def ensure_game_session(room):
    with transaction.atomic():
        session, _ = GameSession.objects.get_or_create(room=room)
        if not session.baba_letter:
            candidates = room.baba_characters or DEFAULT_BABA_CHARACTERS
            session.baba_letter = secrets.choice(candidates)
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
