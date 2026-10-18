"""All dynamic match text: challenge cards, scoreboard, move prompts, event captions (HTML)."""
from __future__ import annotations

from html import escape

from services import rules
from services.match_engine import MatchSnap, PlayerSnap, TurnSnap
from services.rules import Move

LINE = "━━━━━━━━━━━━━━━━━━"
MAX_HP = rules.MAX_HP


def esc(text: str | None) -> str:
    return escape(text or "", quote=False)


def hp_bar(hp: int, width: int = 10) -> str:
    filled = round(width * max(hp, 0) / MAX_HP)
    return "▰" * filled + "▱" * (width - filled)


def _n(snap: MatchSnap, user_id: int) -> str:
    p = snap.player(user_id)
    return esc(p.name) if p else "Unknown Superstar"


# ---------------------------------------------------------------- challenge flow

def challenge_text(challenger_name: str, group_title: str | None, timeout: int) -> str:
    return (f"🥊 <b>WWE ARENA — OPEN CHALLENGE</b>\n\n{LINE}\n\n"
            f"👤 Challenger: <b>{esc(challenger_name)}</b>\n❤️ Health: 100 HP\n"
            f"🏟️ Arena: {esc(group_title) or 'This Group'}\n\n"
            f"One ring. Two fighters. Only one winner.\n\n🔥 Who is brave enough to step into the ring?\n\n"
            f"{LINE}\n⏳ Expires in {timeout}s")


def challenge_closed_text(snap: MatchSnap, why: str) -> str:
    return f"🥊 <b>WWE ARENA — CHALLENGE CLOSED</b>\n\n{LINE}\n\n👤 {_n(snap, snap.challenger_id)}\n{why}"


def accepted_text(snap: MatchSnap) -> str:
    a, b = snap.players[0], snap.players[1]
    return (f"🔔 <b>CHALLENGE ACCEPTED!</b>\n\n🥊 <b>{esc(a.name)}</b> vs <b>{esc(b.name)}</b>\n\n"
            f"❤️ {esc(a.name)} — {a.hp} HP\n❤️ {esc(b.name)} — {b.hp} HP\n\nThe bell is about to ring!")


def dm_required_text(snap: MatchSnap, missing: list[int]) -> str:
    names = ", ".join(f"<b>{_n(snap, u)}</b>" for u in missing)
    return (f"📩 <b>Private chat needed</b>\n\n{names} must open the bot privately and press <b>Start</b> — "
            f"moves are chosen in DM so your opponent can't peek.\n\nThe match begins as soon as everyone is ready.")


def live_text(snap: MatchSnap) -> str:
    a, b = snap.players[0], snap.players[1]
    return (f"🔔 <b>THE MATCH IS LIVE!</b>\n\n🥊 <b>{esc(a.name)}</b> vs <b>{esc(b.name)}</b>\n\n"
            f"❤️ {esc(a.name)}: {a.hp}/{MAX_HP}\n❤️ {esc(b.name)}: {b.hp}/{MAX_HP}\n\n"
            f"🔥 Fight smart. Watch your opponent. Save your Finisher.\n\n"
            f"The first turn begins now — <b>{_n(snap, snap.active_player_id)}</b> attacks first.")


def scoreboard_text(snap: MatchSnap) -> str:
    colors = ["🔴", "🔵"]
    blocks = []
    for i, p in enumerate(snap.players):
        blocks.append(f"{colors[i % 2]} <b>{esc(p.name)}</b>\n❤️ HP: {p.hp}/{MAX_HP} {hp_bar(p.hp)}\n"
                      f"🔥 Finishers left: {p.finishers_left}/{rules.MAX_FINISHERS}\n"
                      f"🛡️ Reversals left: {p.reversals_left}\n"
                      f"🎴 Wild Draw: {'ready' if p.wild_draws_left else 'used'}")
    if snap.status == "active" and snap.active_player_id:
        footer = f"⚡ Current Turn: <b>{_n(snap, snap.active_player_id)}</b>\n🎯 Match Status: LIVE"
    elif snap.status == "paused":
        footer = "⏸️ Match Status: PAUSED"
    elif snap.status == "completed":
        footer = f"🏆 Winner: <b>{_n(snap, snap.winner_id)}</b>\n🎯 Match Status: FINISHED"
    else:
        footer = f"🎯 Match Status: {esc(snap.status.upper())}"
    return f"🥊 <b>WWE ARENA — LIVE MATCH</b>\n\n{LINE}\n\n" + "\n\n".join(blocks) + f"\n\n{LINE}\n\n{footer}"


# --------------------------------------------------------------------- DM prompts

def move_prompt_text(snap: MatchSnap, viewer_id: int) -> str:
    me, opp = snap.player(viewer_id), snap.other(viewer_id)
    return (f"🥊 <b>YOUR TURN — CHOOSE YOUR MOVE</b>\n\n❤️ Your Health: {me.hp}/{MAX_HP}\n"
            f"🎯 Opponent: <b>{esc(opp.name)}</b>\n💔 Opponent Health: {opp.hp}/{MAX_HP}\n\n{LINE}\n\n"
            f"🔥 <b>FINISHER — 40 DMG</b>\nUses remaining: {me.finishers_left}/{rules.MAX_FINISHERS}\n\n"
            f"💣 F5 — 30 DMG\n💥 SPEAR — 25 DMG\n⚡ SUPER KICK — 10 DMG\n💢 DDT — 5 DMG\n\n"
            f"🛡️ <b>REVERSAL — {int(rules.REVERSAL_CHANCE * 100)}% chance</b>\nTry to reflect an incoming attack. "
            f"Every use costs one charge. Charges left: {me.reversals_left}.\n\n"
            f"🎴 <b>WILD DRAW</b> — {'ready' if me.wild_draws_left else 'already used'}\n"
            f"A random move (it can even be a bonus Reversal!). Skips the no-repeat rule.\n\n"
            f"{LINE}\n\n⚠️ No consecutive repeats of the same attacking move.\n⏳ You have {_secs(snap)}s.")


def _secs(snap: MatchSnap) -> str:
    from models import utcnow
    if snap.deadline_at is None:
        return "—"
    return str(max(0, int((snap.deadline_at - utcnow()).total_seconds())))


def waiting_text(snap: MatchSnap, viewer_id: int) -> str:
    me, opp = snap.player(viewer_id), snap.other(viewer_id)
    return (f"⏳ <b>Waiting for {esc(opp.name)}…</b>\n\n❤️ You: {me.hp}/{MAX_HP}\n💔 {esc(opp.name)}: {opp.hp}/{MAX_HP}\n\n"
            f"Get ready to counter — a Reversal could turn the fight around.")


def attack_sent_text(move: Move) -> str:
    return f"✅ <b>{rules.MOVE_EMOJI[move]} {rules.MOVE_NAMES[move]}</b> locked in. Waiting for your opponent's response…"


def wild_attack_text(move: Move) -> str:
    return (f"🎴 <b>WILD DRAW!</b>\n\nThe card turned into <b>{rules.MOVE_EMOJI[move]} {rules.MOVE_NAMES[move]}</b> — "
            f"locked in. Waiting for your opponent's response…")


def wild_reversal_text() -> str:
    return ("🎴 <b>WILD DRAW!</b>\n\nThe card turned into a <b>🛡️ REVERSAL</b> — you gained a bonus Reversal charge!\n"
            "You still get to attack this turn…")


def incoming_text(snap: MatchSnap, viewer_id: int, move: Move | None, window: int) -> str:
    me, att = snap.player(viewer_id), snap.other(viewer_id)
    what = (f"<b>{rules.MOVE_EMOJI[move]} {rules.MOVE_NAMES[move]}</b>" if move else "<b>an unknown move</b>")
    return (f"⚠️ <b>INCOMING ATTACK!</b>\n\n<b>{esc(att.name)}</b> is coming at you with {what}!\n\n"
            f"❤️ Your Health: {me.hp}/{MAX_HP}\n🛡️ Reversals left: {me.reversals_left}\n\n"
            f"A Reversal has a {int(rules.REVERSAL_CHANCE * 100)}% chance to reflect the damage back at them — it always works. "
            f"Using it costs one charge.\n"
            f"Choose within {window}s!")


def status_alert(snap: MatchSnap, viewer_id: int) -> str:
    me, opp = snap.player(viewer_id), snap.other(viewer_id)
    turn_of = _plain(snap, snap.active_player_id)
    return (f"Turn {snap.turn_number} • {turn_of}'s move\n"
            f"You: {me.hp} HP • F {me.finishers_left}/{rules.MAX_FINISHERS} • R {me.reversals_left} • 🎴 {me.wild_draws_left}\n"
            f"{_plain(snap, opp.user_id)}: {opp.hp} HP • F {opp.finishers_left}/{rules.MAX_FINISHERS} • R {opp.reversals_left} • 🎴 {opp.wild_draws_left}")[:200]


def _plain(snap: MatchSnap, uid: int | None) -> str:
    p = snap.player(uid) if uid else None
    return (p.name if p else "—")[:24]


# ------------------------------------------------------------------ event captions

STYLE: dict[str, tuple[str, str]] = {
    "spear": ("💥 <b>SPEAR! SPEAR! SPEAR!</b>", "🔥 The fight continues!"),
    "f5": ("💣 <b>F5! WHAT A SLAM!</b>", "🔥 The crowd erupts!"),
    "superkick": ("⚡ <b>SUPER KICK! LIGHTS OUT!</b>", "🔥 Sweet chin music!"),
    "ddt": ("💢 <b>DDT! HEAD FIRST!</b>", "🔥 The fight continues!"),
}


def event_caption(snap: MatchSnap, t: TurnSnap) -> str:
    att, dfn = snap.player(t.attacker_id), snap.player(t.defender_id)
    an, dn = esc(att.name), esc(dfn.name)
    move = Move(t.move)
    mname = rules.MOVE_NAMES[move]
    prefix = f"🎴 <b>WILD DRAW — {mname}!</b>\n\n" if t.wild else ""
    gamble = (f"🛡️❌ <b>{dn}</b> gambled on a Reversal — it <b>FAILED</b>!\n\n"
              if t.reversal_attempted and not t.reversed else "")
    if t.reversed:
        return (f"{prefix}🛡️ <b>COUNTERED! — REVERSAL</b>\n\n{LINE}\n\n🎯 <b>{dn}</b> reversed <b>{an}</b>'s {mname}!\n\n"
                f"↩️ {t.damage_to_attacker} damage reflected.\n\n💔 {an}: {att.hp}/{MAX_HP} HP\n❤️ {dn}: {dfn.hp}/{MAX_HP} HP\n\n"
                f"🛡️ Reversals remaining for {dn}: {dfn.reversals_left}\n\n"
                f"What a counter! The momentum has shifted.")
    if move == Move.FINISHER:
        return (f"{prefix}🔥 <b>FINISHER CONNECTS!</b>\n\n{gamble}💀 <b>{an}</b> unleashed a devastating Finisher on <b>{dn}</b>!\n\n"
                f"💥 Damage: {t.damage_to_defender} HP\n\n❤️ {an}: {att.hp}/{MAX_HP}\n💔 {dn}: {dfn.hp}/{MAX_HP}\n\n"
                f"⚠️ Finisher uses remaining: {att.finishers_left}/{rules.MAX_FINISHERS}\n\nThe crowd is on its feet!")
    title, flavor = STYLE[t.move]
    return (f"{prefix}{title}\n\n{gamble}{LINE}\n\n👊 Attacker: <b>{an}</b>\n🎯 Target: <b>{dn}</b>\n💥 Damage: {t.damage_to_defender} HP\n\n"
            f"❤️ {an}: {att.hp}/{MAX_HP}\n💔 {dn}: {dfn.hp}/{MAX_HP}\n\n{LINE}\n\n{flavor}")


def _summary_lines(snap: MatchSnap, t: TurnSnap) -> str:
    s = t.summary
    if s is None:
        return ""
    rows = [f"• Total turns: {s.total_turns}"]
    for p in snap.players:
        rows.append(f"• {esc(p.name)}: {s.damage_dealt.get(p.user_id, 0)} dmg dealt, "
                    f"{s.finishers.get(p.user_id, 0)} Finisher(s), {s.reversals.get(p.user_id, 0)} Reversal(s)")
    return "\n".join(rows)


def knockout_caption(snap: MatchSnap, t: TurnSnap) -> str:
    winner, loser = snap.player(t.winner_id), snap.other(t.winner_id)
    return (f"☠️ <b>KNOCKOUT! KNOCKOUT!</b>\n\n{LINE}\n\n🏆 WINNER: <b>{esc(winner.name)}</b>\n💀 DEFEATED: <b>{esc(loser.name)}</b>\n\n"
            f"❤️ Winner's remaining HP: {winner.hp}/{MAX_HP}\n\n📊 <b>Match Summary:</b>\n{_summary_lines(snap, t)}\n\n"
            f"👑 THE ARENA HAS A NEW WINNER!")


def forfeit_caption(snap: MatchSnap, t: TurnSnap) -> str:
    winner, loser = snap.player(t.winner_id), snap.other(t.winner_id)
    return (f"⏱️ <b>TIMEOUT VICTORY!</b>\n\n{LINE}\n\n🏆 WINNER: <b>{esc(winner.name)}</b>\n"
            f"🚪 <b>{esc(loser.name)}</b> didn't answer the bell in time.\n\n❤️ {esc(winner.name)}: {winner.hp}/{MAX_HP}\n"
            f"💔 {esc(loser.name)}: {loser.hp}/{MAX_HP}\n\n📊 <b>Match Summary:</b>\n{_summary_lines(snap, t)}")


def dm_result_text(snap: MatchSnap, t: TurnSnap, viewer_id: int) -> str:
    me, opp = snap.player(viewer_id), snap.other(viewer_id)
    mname = f"{rules.MOVE_EMOJI[Move(t.move)]} {rules.MOVE_NAMES[Move(t.move)]}"
    if t.reversed:
        line = (f"🛡️ <b>{esc(snap.player(t.defender_id).name)}</b> reversed {mname}! "
                f"{t.damage_to_attacker} damage reflected onto <b>{esc(snap.player(t.attacker_id).name)}</b>.")
    elif t.reversal_attempted:
        line = (f"🛡️❌ <b>{esc(snap.player(t.defender_id).name)}</b>'s Reversal FAILED! "
                f"{mname} hit for {t.damage_to_defender} HP.")
    else:
        line = f"{mname} hit <b>{esc(snap.player(t.defender_id).name)}</b> for {t.damage_to_defender} HP."
    if t.wild:
        line = "🎴 <b>WILD DRAW!</b> " + line
    return f"{line}\n\n❤️ You: {me.hp}/{MAX_HP}\n💔 {esc(opp.name)}: {opp.hp}/{MAX_HP}"


def final_dm_text(snap: MatchSnap, viewer_id: int) -> str:
    won = snap.winner_id == viewer_id
    return ("🏆 <b>VICTORY!</b> You are the champion of this ring." if won else
            "☠️ <b>DEFEAT.</b> You'll be back stronger. Use /match in a group to get revenge.")


def pause_text(snap: MatchSnap) -> str:
    return (f"⏸️ <b>MATCH PAUSED</b>\n\n<b>{_n(snap, snap.active_player_id)}</b> didn't pick a move in time.\n"
            f"Either fighter can press Resume to continue.")


def short_rules() -> str:
    return ("HP 100 • Finisher 40 (max 1) • F5 30 • Spear 25 • Super Kick 10 • DDT 5\n"
            "Reversal: 100% reflect (2 uses). Wild Draw: 1 random move. No repeating an attack.")
