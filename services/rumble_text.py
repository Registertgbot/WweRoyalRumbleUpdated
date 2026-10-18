"""All Royal Rumble text (HTML): lobby, live ring board, event captions and DM prompts."""
from __future__ import annotations

from config import get_settings
from services import rules
from services import rumble_rules as rr
from services.rules import Move
from services.rumble_engine import REvent, RPlayerSnap, RumbleSnap
from services.scoreboard import LINE, esc

COLORS = ["🔴", "🔵", "🟢", "🟡", "🟣", "🟠", "⚪", "🟤", "⚫", "🔶", "🔷", "💠"]


def _c(p: RPlayerSnap) -> str:
    return COLORS[(p.entry_order - 1) % len(COLORS)] if p.entry_order else "👤"


def _n(snap: RumbleSnap, user_id: int | None) -> str:
    p = snap.player(user_id)
    return f"<b>{esc(p.name)}</b>" if p else "<b>Unknown Superstar</b>"


def _fmt_move(move: str) -> str:
    m = Move(move)
    return f"{rules.MOVE_EMOJI[m]} {rules.MOVE_NAMES[m]}"


# ------------------------------------------------------------------------ lobby

def lobby_text(snap: RumbleSnap) -> str:
    s = get_settings()
    names = "\n".join(f"{i}. {esc(p.name)}" for i, p in enumerate(snap.players, start=1))
    return (f"🔔 <b>ROYAL RUMBLE — ENTER THE RING!</b>\n\n{LINE}\n\n"
            f"👑 Host: {_n(snap, snap.host_id)}\n"
            f"👥 Wrestlers ({len(snap.players)}/{s.rumble_max_players}):\n{names}\n\n"
            f"Two start in the ring. A new wrestler walks in every {s.rumble_entry_interval}s.\n"
            f"❤️ {rr.RUMBLE_HP} HP each • eliminate someone to recover +{rr.ADRENALINE_HEAL} HP\n"
            f"🏆 Last one standing wins!\n\n{LINE}\n"
            f"⏳ Lobby closes in {s.rumble_lobby_timeout}s • minimum {s.rumble_min_players} wrestlers\n"
            f"📩 You must press Start in the bot's private chat to play.")


def lobby_closed_text(snap: RumbleSnap, why: str) -> str:
    return f"🔔 <b>ROYAL RUMBLE</b>\n\n{LINE}\n{why}"


def rules_text() -> str:
    s = get_settings()
    return (f"🔔 <b>ROYAL RUMBLE — RULES</b>\n\n"
            f"• /rumble opens a lobby; {s.rumble_min_players}-{s.rumble_max_players} wrestlers\n"
            f"• Two start in the ring, then one more enters every {s.rumble_entry_interval}s\n"
            f"• Everyone has {rr.RUMBLE_HP} HP, 1 Finisher and {rules.MAX_REVERSALS} Reversals\n"
            f"• On your turn pick a move, then a target. The target may Reversal (always works) to bounce the damage back\n"
            f"• Knock someone out and you heal +{rr.ADRENALINE_HEAL} HP\n"
            f"• Idle for {rr.AFK_LIMIT} turns in a row and you're eliminated\n"
            f"• Last wrestler standing wins 🏆")


# --------------------------------------------------------------------- live board

def _row(p: RPlayerSnap, active: bool) -> str:
    mark = "🎯" if active else "▫️"
    return (f"{mark} <b>#{p.entry_order}</b> {_c(p)} {esc(p.name)}\n"
            f"      ❤️ {p.hp}/{rr.RUMBLE_HP} {rr.hp_bar(p.hp)}  🔥{p.finishers_left} 🛡️{p.reversals_left}"
            f"  💀{p.eliminations}")


def board_text(snap: RumbleSnap) -> str:
    head = "🏆 <b>ROYAL RUMBLE — FINISHED</b>" if snap.status == "completed" else "🔔 <b>ROYAL RUMBLE — LIVE</b>"
    ring = snap.ring
    lines = [head, "", LINE, f"🥊 <b>In the ring ({len(ring)})</b>"]
    lines += [_row(p, p.user_id == snap.active_player_id) for p in ring] or ["(empty)"]
    waiting = snap.waiting
    if waiting:
        lines += ["", f"🚪 <b>Still to enter:</b> {len(waiting)} (next: #{waiting[0].entry_order})"]
    out = snap.out
    if out:
        lines += ["", f"💀 <b>Eliminated ({len(out)})</b>"]
        lines += [f"{p.placement}. {esc(p.name)}" for p in out[:6]]
        if len(out) > 6:
            lines.append(f"… and {len(out) - 6} more")
    if snap.status == "completed" and snap.winner_id:
        lines += ["", f"👑 Champion: {_n(snap, snap.winner_id)}"]
    elif snap.status == "active" and snap.active_player_id:
        lines += ["", LINE, f"🎯 Turn {snap.turn_number}: {_n(snap, snap.active_player_id)}"]
    return "\n".join(lines)


# --------------------------------------------------------------- group captions

def started_caption(snap: RumbleSnap) -> str:
    order = " • ".join(f"#{p.entry_order} {esc(p.name)}" for p in sorted(snap.players, key=lambda x: x.entry_order))
    return (f"🔔 <b>THE ROYAL RUMBLE BEGINS!</b>\n\n{LINE}\n"
            f"📋 Entry order: {order}\n\n"
            f"Two wrestlers start. The clock is ticking for the rest!")


def entry_caption(snap: RumbleSnap, ev: REvent) -> str:
    left = len(snap.waiting)
    tail = f"\n🚪 {left} more to come" if left else "\n🚪 That's everyone — no more entrants!"
    return (f"🚪 <b>#{ev.number} ENTERS THE RING!</b>\n\n{_c(snap.player(ev.user_id))} "
            f"{_n(snap, ev.user_id)} — ❤️ {rr.RUMBLE_HP} HP{tail}")


def turn_caption(snap: RumbleSnap, ev: REvent) -> str:
    a, d = _n(snap, ev.user_id), _n(snap, ev.other_id)
    move = _fmt_move(ev.move)
    note = "\n⏱️ No Reversal in time!" if ev.auto else ""
    if ev.reversed:
        return (f"🛡️ <b>REVERSAL!</b>{note}\n\n{d} turned {a}'s {move} around!\n"
                f"💥 {ev.reflected} damage back to {a} → ❤️ {ev.hp_attacker}/{rr.RUMBLE_HP}")
    return (f"{move}!{note}\n\n{a} hits {d} for <b>{ev.damage}</b>\n"
            f"❤️ {d}: {ev.hp_defender}/{rr.RUMBLE_HP} {rr.hp_bar(ev.hp_defender)}")


def skip_caption(snap: RumbleSnap, ev: REvent) -> str:
    return f"💤 {_n(snap, ev.user_id)} froze in the ring and lost their turn!"


def elimination_caption(snap: RumbleSnap, ev: REvent) -> str:
    victim = _n(snap, ev.user_id)
    left = snap.alive_count
    if ev.reason == "afk":
        return f"🚪 {victim} was too slow and is <b>eliminated</b> for inactivity!\n\n🧍 {left} remaining"
    killer = _n(snap, ev.other_id)
    how = "THROWN OVER THE TOP ROPE" if ev.finisher_kill else "ELIMINATED"
    heal = f"\n💚 {killer} recovers +{ev.healed} HP" if ev.healed else ""
    return (f"💀 <b>{how}!</b>\n\n{victim} is out — finished <b>#{ev.placement}</b>\n"
            f"👊 Eliminated by {killer}{heal}\n\n🧍 {left} remaining")


def final_two_caption(snap: RumbleSnap) -> str:
    names = " vs ".join(f"<b>{esc(p.name)}</b>" for p in snap.players if not p.eliminated)
    return f"🔥 <b>FINAL TWO!</b>\n\n{names}\n\nWho will be the last one standing?"


def winner_caption(snap: RumbleSnap) -> str:
    w = snap.player(snap.winner_id)
    return (f"🏆 <b>{esc(w.name)} WINS THE ROYAL RUMBLE!</b>\n\n{LINE}\n"
            f"👑 Last one standing — ❤️ {w.hp}/{rr.RUMBLE_HP}\n💀 Eliminations: {w.eliminations}\n"
            f"💥 Damage dealt: {w.damage_dealt}\n\nWhat a performance!")


# ------------------------------------------------------------------- DM prompts

def move_prompt(snap: RumbleSnap, viewer_id: int) -> str:
    me = snap.player(viewer_id)
    foes = ", ".join(f"{esc(p.name)} ({p.hp})" for p in snap.ring if p.user_id != viewer_id)
    return (f"🎯 <b>YOUR TURN — Royal Rumble</b>\n\n❤️ You: {me.hp}/{rr.RUMBLE_HP} {rr.hp_bar(me.hp)}\n"
            f"🔥 Finisher: {me.finishers_left}/{rules.MAX_FINISHERS}  🛡️ Reversals: {me.reversals_left}/{rules.MAX_REVERSALS}\n\n"
            f"🥊 In the ring: {foes}\n\nPick your move, then your target.")


def target_prompt(snap: RumbleSnap) -> str:
    return f"🎯 <b>{_fmt_move(snap.pending_move)}</b> — who do you want to hit?"


def attack_sent_text(snap: RumbleSnap) -> str:
    return f"{_fmt_move(snap.pending_move)} sent at {_n(snap, snap.pending_target_id)}…"


def incoming_text(snap: RumbleSnap, viewer_id: int, window: int) -> str:
    me = snap.player(viewer_id)
    return (f"⚠️ <b>INCOMING ATTACK!</b>\n\n{_n(snap, snap.active_player_id)} is coming for you!\n"
            f"❤️ You: {me.hp}/{rr.RUMBLE_HP}\n\n"
            f"🛡️ Reversal: {int(rules.REVERSAL_CHANCE * 100)}% to bounce the damage back "
            f"({me.reversals_left} left)\n⏱️ {window}s to decide.")


def eliminated_dm(snap: RumbleSnap, ev: REvent) -> str:
    who = f" by {_n(snap, ev.other_id)}" if ev.other_id else " for inactivity"
    return f"💀 <b>You were eliminated{who}.</b>\n\nYou finished <b>#{ev.placement}</b> in the Royal Rumble. Well fought!"


def winner_dm(snap: RumbleSnap) -> str:
    return "🏆 <b>YOU WON THE ROYAL RUMBLE!</b>\n\nThe ring is yours, champion! 👑"


def status_alert(snap: RumbleSnap, viewer_id: int) -> str:
    me = snap.player(viewer_id)
    if me is None:
        return "🚫 You're not in this Rumble."
    where = "in the ring" if me.in_ring else ("eliminated" if me.eliminated else f"waiting (#{me.entry_order})")
    return (f"#{me.entry_order} {me.name[:20]} — {where}\n❤️ {me.hp}/{rr.RUMBLE_HP}  🔥 {me.finishers_left}  "
            f"🛡️ {me.reversals_left}\n💀 Eliminations: {me.eliminations}\n"
            f"Ring: {len(snap.ring)} • Waiting: {len(snap.waiting)} • Out: {len(snap.out)}")


def leaderboard_text(rows) -> str:
    if not rows:
        return "🏆 <b>ROYAL RUMBLE LEADERS</b>\n\nNo Rumble has finished yet. Start one with /rumble!"
    lines = [f"{i}. <b>{esc(n)}</b> — 🏆 {w} wins • 💀 {e} elims • {c} played" for i, (n, w, e, c) in enumerate(rows, 1)]
    return "🏆 <b>ROYAL RUMBLE LEADERS</b>\n\n" + "\n".join(lines)
