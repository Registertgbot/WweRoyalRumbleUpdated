"""SQLAlchemy models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        String, UniqueConstraint, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite returns naive values)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class MatchStatus:
    PENDING = "pending"          # open challenge in a group
    WAITING_DM = "waiting_dm"    # accepted, waiting for both players to press Start in DM
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    OPEN = (PENDING, WAITING_DM, ACTIVE, PAUSED)
    ALL = (PENDING, WAITING_DM, ACTIVE, PAUSED, COMPLETED, CANCELLED, EXPIRED)


class Phase:
    AWAIT_ATTACK = "await_attack"
    AWAIT_REVERSAL = "await_reversal"


class RStatus:
    LOBBY = "lobby"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OPEN = (LOBBY, ACTIVE)


class RPhase:
    AWAIT_MOVE = "await_move"
    AWAIT_TARGET = "await_target"
    AWAIT_REVERSAL = "await_reversal"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user ID
    username: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(128))
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    dm_started: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    total_matches: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    knockouts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        CheckConstraint("wins >= 0 AND losses >= 0 AND total_matches >= 0", name="ck_users_counts_nonneg"),
        Index("ix_users_wins", "wins"),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_title: Mapped[str | None] = mapped_column(String(256))
    challenger_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    opponent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default=MatchStatus.PENDING)
    phase: Mapped[str | None] = mapped_column(String(16))
    active_player_id: Mapped[int | None] = mapped_column(BigInteger)
    turn_number: Mapped[int] = mapped_column(Integer, default=1)
    pending_move: Mapped[str | None] = mapped_column(String(16))
    pending_wild: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    end_reason: Mapped[str | None] = mapped_column(String(24))
    cancel_requested_by: Mapped[int | None] = mapped_column(BigInteger)
    challenge_message_id: Mapped[int | None] = mapped_column(Integer)
    scoreboard_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    players: Mapped[list["MatchPlayer"]] = relationship(
        lazy="selectin", order_by="MatchPlayer.id", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','waiting_dm','active','paused','completed','cancelled','expired')",
            name="ck_matches_status"),
        Index("ix_matches_status_deadline", "status", "deadline_at"),
    )


class MatchPlayer(Base):
    """Per-player state inside a match (HP and move usage). Survives restarts."""

    __tablename__ = "match_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    finishers_used: Mapped[int] = mapped_column(Integer, default=0)
    reversals_used: Mapped[int] = mapped_column(Integer, default=0)      # attempts, successful or not
    bonus_reversals: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wild_draws_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_attack: Mapped[str | None] = mapped_column(String(16))
    prompt_message_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_match_player"),
        CheckConstraint("hp >= 0 AND hp <= 100", name="ck_match_players_hp"),
        CheckConstraint("finishers_used >= 0 AND finishers_used <= 2", name="ck_match_players_finishers"),
        CheckConstraint("reversals_used >= 0 AND reversals_used <= 4", name="ck_match_players_reversals"),
        # A user may be in at most one open match at any time (DB-level guarantee).
        Index("uq_match_players_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


class MatchTurn(Base):
    __tablename__ = "match_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    turn_number: Mapped[int] = mapped_column(Integer)
    attacker_id: Mapped[int] = mapped_column(BigInteger)
    target_id: Mapped[int] = mapped_column(BigInteger)
    move: Mapped[str] = mapped_column(String(16))
    original_damage: Mapped[int] = mapped_column(Integer)
    reversed: Mapped[bool] = mapped_column(Boolean, default=False)      # a Reversal that SUCCEEDED
    reversal_attempted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    wild: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    damage_to_target: Mapped[int] = mapped_column(Integer, default=0)      # actually applied to the defender
    damage_to_attacker: Mapped[int] = mapped_column(Integer, default=0)    # reflected, actually applied
    attacker_hp_after: Mapped[int] = mapped_column(Integer)
    target_hp_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    # Hard guarantee that a turn can be resolved only once.
    __table_args__ = (UniqueConstraint("match_id", "turn_number", name="uq_match_turn_number"),)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    event_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    local_path: Mapped[str] = mapped_column(String(256))
    telegram_file_id: Mapped[str | None] = mapped_column(String(256))


class BotSetting(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(128))


# ------------------------------------------------------------------ Royal Rumble

class Rumble(Base):
    """A multiplayer Royal Rumble in one group. Separate from 1v1 matches."""

    __tablename__ = "rumbles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_title: Mapped[str | None] = mapped_column(String(256))
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(12), default=RStatus.LOBBY)
    phase: Mapped[str | None] = mapped_column(String(16))
    active_player_id: Mapped[int | None] = mapped_column(BigInteger)
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    last_actor_order: Mapped[int] = mapped_column(Integer, default=0)
    pending_move: Mapped[str | None] = mapped_column(String(16))
    pending_target_id: Mapped[int | None] = mapped_column(BigInteger)
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)      # lobby close / turn / reversal window
    next_entry_at: Mapped[datetime | None] = mapped_column(UTCDateTime)    # next wrestler walks in
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    end_reason: Mapped[str | None] = mapped_column(String(24))
    lobby_message_id: Mapped[int | None] = mapped_column(Integer)
    board_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    players: Mapped[list["RumblePlayer"]] = relationship(
        lazy="selectin", order_by="RumblePlayer.id", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('lobby','active','completed','cancelled')", name="ck_rumbles_status"),
        Index("ix_rumbles_status_deadline", "status", "deadline_at"),
    )


class RumblePlayer(Base):
    __tablename__ = "rumble_players"

    # Same field names as MatchPlayer so services.rules can resolve attacks on these rows directly.
    bonus_reversals = 0

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rumble_id: Mapped[int] = mapped_column(Integer, ForeignKey("rumbles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    entry_order: Mapped[int] = mapped_column(Integer, default=0)       # 0 until the Rumble starts
    hp: Mapped[int] = mapped_column(Integer, default=150)
    in_ring: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    eliminated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    placement: Mapped[int | None] = mapped_column(Integer)             # 1 = winner
    eliminations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    finishers_used: Mapped[int] = mapped_column(Integer, default=0)
    reversals_used: Mapped[int] = mapped_column(Integer, default=0)
    last_attack: Mapped[str | None] = mapped_column(String(16))
    afk_strikes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    prompt_message_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("rumble_id", "user_id", name="uq_rumble_player"),
        CheckConstraint("hp >= 0 AND hp <= 150", name="ck_rumble_players_hp"),
        Index("uq_rumble_players_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


# ------------------------------------------------------------------ Tag Team (2v2)

class TagMatch(Base):
    """A 2v2 Tag Team match: team 1 = Lions, team 2 = Tigers."""

    __tablename__ = "tag_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_title: Mapped[str | None] = mapped_column(String(256))
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    team_size: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    status: Mapped[str] = mapped_column(String(12), default=RStatus.LOBBY)
    phase: Mapped[str | None] = mapped_column(String(16))
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    active_team: Mapped[int | None] = mapped_column(Integer)
    active_player_id: Mapped[int | None] = mapped_column(BigInteger)
    pending_move: Mapped[str | None] = mapped_column(String(16))
    pending_target_id: Mapped[int | None] = mapped_column(BigInteger)
    t1_tag_lock: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    t2_tag_lock: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    winner_team: Mapped[int | None] = mapped_column(Integer)
    end_reason: Mapped[str | None] = mapped_column(String(24))
    lobby_message_id: Mapped[int | None] = mapped_column(Integer)
    board_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    players: Mapped[list["TagPlayer"]] = relationship(
        lazy="selectin", order_by="TagPlayer.id", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('lobby','active','completed','cancelled')", name="ck_tag_matches_status"),
        Index("ix_tag_matches_status_deadline", "status", "deadline_at"),
    )


class TagPlayer(Base):
    __tablename__ = "tag_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag_matches.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    team: Mapped[int] = mapped_column(Integer)                       # 1 = Lions, 2 = Tigers
    slot: Mapped[int] = mapped_column(Integer, default=0)            # 0 starts in the ring, 1 on the apron
    in_ring: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    eliminated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    hp: Mapped[int] = mapped_column(Integer, default=100)
    finishers_used: Mapped[int] = mapped_column(Integer, default=0)
    reversals_used: Mapped[int] = mapped_column(Integer, default=0)
    bonus_reversals: Mapped[int] = mapped_column(Integer, default=0, server_default="0")   # handicap for the smaller team
    last_attack: Mapped[str | None] = mapped_column(String(16))
    afk_strikes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tags_made: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    eliminations: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    prompt_message_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("match_id", "user_id", name="uq_tag_player"),
        CheckConstraint("team IN (1, 2)", name="ck_tag_players_team"),
        CheckConstraint("hp >= 0 AND hp <= 100", name="ck_tag_players_hp"),
        Index("uq_tag_players_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


# ------------------------------------------------------- Money in the Bank tournament

class MitbEvent(Base):
    """A Money in the Bank tournament: 1v1 qualifier rounds, then a ladder match for the briefcase."""

    __tablename__ = "mitb_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_title: Mapped[str | None] = mapped_column(String(256))
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(6), default="fast")           # fast | slow
    capacity: Mapped[int] = mapped_column(Integer, default=8)
    status: Mapped[str] = mapped_column(String(12), default="lobby")       # lobby|qualifier|ladder|completed|cancelled
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str | None] = mapped_column(String(16))                  # ladder phase
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    ladder_turns: Mapped[int] = mapped_column(Integer, default=0)
    active_player_id: Mapped[int | None] = mapped_column(BigInteger)
    pending_move: Mapped[str | None] = mapped_column(String(16))
    pending_target_id: Mapped[int | None] = mapped_column(BigInteger)
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)      # lobby close / ladder turn
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    end_reason: Mapped[str | None] = mapped_column(String(24))
    lobby_message_id: Mapped[int | None] = mapped_column(Integer)
    board_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    players: Mapped[list["MitbPlayer"]] = relationship(
        lazy="selectin", order_by="MitbPlayer.id", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('lobby','qualifier','ladder','completed','cancelled')", name="ck_mitb_events_status"),
        Index("ix_mitb_events_status_deadline", "status", "deadline_at"),
    )


class MitbPlayer(Base):
    __tablename__ = "mitb_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("mitb_events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="alive")       # alive|out|ladder|dq|champion
    had_bye: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    out_round: Mapped[int | None] = mapped_column(Integer)
    # ladder-match state (same field names as MatchPlayer so services.rules works on these rows)
    rung: Mapped[int] = mapped_column(Integer, default=0)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    finishers_used: Mapped[int] = mapped_column(Integer, default=0)
    reversals_used: Mapped[int] = mapped_column(Integer, default=0)
    bonus_reversals: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_attack: Mapped[str | None] = mapped_column(String(16))
    afk_strikes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stun: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ladder_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    prompt_message_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_mitb_player"),
        CheckConstraint("hp >= 0 AND hp <= 100", name="ck_mitb_players_hp"),
        CheckConstraint("rung >= 0 AND rung <= 5", name="ck_mitb_players_rung"),
        Index("uq_mitb_players_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


class Briefcase(Base):
    """The Money in the Bank briefcase: one active per holder, valid for 7 days, cash-in once."""

    __tablename__ = "briefcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    event_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(8), default="active")       # active|won|lost|expired
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        Index("uq_briefcases_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),
    )


class MitbDuel(Base):
    """A 1v1 duel: a qualifier match, or a briefcase cash-in match."""

    __tablename__ = "mitb_duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("mitb_events.id", ondelete="CASCADE"), index=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(8), default="bracket")        # bracket | cashin
    mode: Mapped[str] = mapped_column(String(6), default="fast")
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    briefcase_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("briefcases.id"))
    status: Mapped[str] = mapped_column(String(10), default="active")      # active | completed
    phase: Mapped[str | None] = mapped_column(String(16))
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    active_user_id: Mapped[int | None] = mapped_column(BigInteger)
    pending_move: Mapped[str | None] = mapped_column(String(16))
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime)      # current turn / reversal window
    cap_at: Mapped[datetime | None] = mapped_column(UTCDateTime)           # hard time limit for the whole duel
    winner_id: Mapped[int | None] = mapped_column(BigInteger)
    end_reason: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    players: Mapped[list["MitbDuelPlayer"]] = relationship(
        lazy="selectin", order_by="MitbDuelPlayer.id", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_mitb_duels_status_deadline", "status", "deadline_at"),)


class MitbDuelPlayer(Base):
    __tablename__ = "mitb_duel_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    duel_id: Mapped[int] = mapped_column(Integer, ForeignKey("mitb_duels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    finishers_used: Mapped[int] = mapped_column(Integer, default=0)
    reversals_used: Mapped[int] = mapped_column(Integer, default=0)
    bonus_reversals: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_attack: Mapped[str | None] = mapped_column(String(16))
    afk_strikes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    prompt_message_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("duel_id", "user_id", name="uq_mitb_duel_player"),
        CheckConstraint("hp >= 0 AND hp <= 100", name="ck_mitb_duel_players_hp"),
        Index("uq_mitb_duel_players_one_active_per_user", "user_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


class CashinOffer(Base):
    """A 20-second window after a 1v1 match in which the briefcase holder may cash in on the winner."""

    __tablename__ = "cashin_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    briefcase_id: Mapped[int] = mapped_column(Integer, ForeignKey("briefcases.id"), index=True)
    group_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_user_id: Mapped[int] = mapped_column(BigInteger)
    target_hp: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(8), default="open")         # open|taken|expired
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    message_id: Mapped[int | None] = mapped_column(Integer)
