"""Static screens and stats formatting."""
from __future__ import annotations

from datetime import datetime

from services.scoreboard import LINE, esc

WELCOME = (
    "🥊 <b>WELCOME TO WWE ARENA</b>\n\nThe ring is ready. The crowd is waiting. Are you ready to fight?\n\n"
    "🔥 Challenge real players\n💥 Execute powerful WWE moves\n🛡️ Reverse attacks and make comebacks\n"
    "🏆 Climb the leaderboard\n👑 Become the champion of the arena\n\nChoose your destination below.")

WELCOME_GROUP = ("🥊 <b>WWE ARENA</b> is open!\n\nSend /play for the arena menu with every game mode (or /match for a quick 1v1). "
                 "Moves are chosen privately — open me in DM and press Start first.")

HELP = (
    "📜 <b>WWE ARENA — RULEBOOK</b>\n\n❤️ Starting Health: 100 HP\n🔥 Finisher: 40 damage, only 1 use per match\n"
    "💣 F5: 30 damage\n💥 Spear: 25 damage\n⚡ Super Kick: 10 damage\n💢 DDT: 5 damage\n"
    "🛡️ Reversal: 100% guaranteed — reflects the incoming damage back. 2 uses per match\n"
    "🎴 Wild Draw: once per match, draw a random move (F5, Spear, Super Kick, DDT, Finisher) or a bonus Reversal\n\n"
    "⚠️ You cannot repeat the same attacking move on consecutive turns (a Wild Draw move ignores this).\n\n"
    "🔁 After every move, Reversal or not, the turn passes to the other fighter.\n\n"
    "☠️ First player to reach 0 HP loses.\n\nChoose your moves wisely. Every turn can change the fight.\n\n"
    "<b>Commands</b>\n/match — challenge the group\n/cancelmatch — cancel your challenge / match\n/rumble — Royal Rumble (3-12 players)\n/tag [2-4] — Tag Team (🦁 vs 🐯), e.g. /tag 3\n/mitb [8|16|32] [slow] — Money in the Bank 💼\n/briefcase • /mitbboard • /cancelmitb\n"
    "/rumbleboard • /tagboard • /cancelrumble • /canceltag\n/profile • /mystats • /history\n"
    "/leaderboard • /id")


def fmt_rate(rate: int | None) -> str:
    return "—" if rate is None else f"{rate}%"


def profile_text(name: str, wins: int, losses: int, total: int, knockouts: int, dealt: int,
                 rate: int | None) -> str:
    tail = "Keep fighting. Build your legacy." if total else "No completed matches yet — step into the ring with /match!"
    return (f"👑 <b>WWE SUPERSTAR PROFILE</b>\n\n{LINE}\n\n👤 Name: <b>{esc(name)}</b>\n🏆 Wins: {wins}\n"
            f"💔 Losses: {losses}\n🥊 Matches: {total}\n☠️ Knockouts: {knockouts}\n💥 Total Damage Dealt: {dealt}\n\n"
            f"{LINE}\n\n🔥 Win Rate: {fmt_rate(rate)}\n\n{tail}")


def mystats_text(name: str, s: dict) -> str:
    return (f"📊 <b>DETAILED STATS — {esc(name)}</b>\n\n{LINE}\n\n🏆 Wins: {s['wins']}\n💔 Losses: {s['losses']}\n"
            f"🥊 Completed matches: {s['total']}\n☠️ Knockouts: {s['knockouts']}\n💥 Damage dealt: {s['dealt']}\n"
            f"🩹 Damage received: {s['received']}\n🔥 Finishers used: {s['finishers']}\n🛡️ Reversals performed: {s['reversals']}\n"
            f"🔥 Win rate: {fmt_rate(s['rate'])}\n\n{LINE}\n\nSee /history for your recent matches.")


def leaderboard_text(rows: list[tuple[str, int]], page: int, page_size: int, total_pages: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    if not rows:
        body = "No champions yet. Be the first — use /match in a group!"
    else:
        lines = []
        for i, (name, wins) in enumerate(rows, start=page * page_size + 1):
            lines.append(f"{medals.get(i, f'▫️')} {i}. {esc(name)} — {wins} WIN{'S' if wins != 1 else ''}")
        body = "\n".join(lines)
    return (f"🏆 <b>WWE ARENA — CHAMPIONS BOARD</b>\n\n{LINE}\n\n{body}\n\n🔥 Fight your way to the top!\n\n{LINE}\n"
            f"Page {page + 1}/{max(total_pages, 1)} • ranked by wins, then win rate, then matches played")


def history_text(items: list[dict], page: int, total_pages: int) -> str:
    if not items:
        return "📜 <b>MATCH HISTORY</b>\n\nNo completed matches yet. Use /match in a group to get started!"
    out = []
    for it in items:
        icon = "🏆 WIN" if it["won"] else "💔 LOSS"
        when = it["when"].strftime("%Y-%m-%d %H:%M UTC") if isinstance(it["when"], datetime) else "—"
        how = {"timeout": " (timeout)", "knockout": " (KO)"}.get(it["reason"], "")
        out.append(f"{icon}{how} vs <b>{esc(it['opponent'])}</b>\n🕒 {when}\n🔢 Turns: {it['turns']} • 💥 Damage: {it['damage']} • "
                   f"🔥 Finishers: {it['finishers']} • 🛡️ Reversals: {it['reversals']}")
    return (f"📜 <b>MATCH HISTORY</b>\n\n{LINE}\n\n" + f"\n\n{LINE}\n\n".join(out) +
            f"\n\n{LINE}\nPage {page + 1}/{max(total_pages, 1)}")
