"""
Bot Telegram per i risultati (con marcatori) della Serie A.

Usa l'API gratuita di API-Football (https://www.api-football.com/).
Pensato per girare periodicamente (es. via GitHub Actions), non come
processo sempre acceso: ogni esecuzione controlla le partite di Serie A
di oggi, e per quelle finite e non ancora notificate manda un messaggio
Telegram con il risultato e i marcatori.
"""

import json
import os
from datetime import date

import requests

API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SERIE_A_LEAGUE_ID = 135  # ID di API-Football per la Serie A italiana
NOTIFIED_FILE = "notified.json"

API_BASE = "https://v3.football.api-sports.io"
API_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

FINISHED_STATUSES = {"FT", "AET", "PEN"}  # finita, dopo supplementari, dopo rigori


def current_season() -> int:
    """API-Football usa l'anno di inizio stagione (es. 2026 per la 2026/27)."""
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def load_notified() -> set:
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_notified(notified: set) -> None:
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(sorted(notified), f)


def get_todays_fixtures() -> list:
    today_str = date.today().isoformat()
    resp = requests.get(
        f"{API_BASE}/fixtures",
        headers=API_HEADERS,
        params={
            "league": SERIE_A_LEAGUE_ID,
            "season": current_season(),
            "date": today_str,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_goal_events(fixture_id: int) -> list:
    resp = requests.get(
        f"{API_BASE}/fixtures/events",
        headers=API_HEADERS,
        params={"fixture": fixture_id},
        timeout=15,
    )
    resp.raise_for_status()
    events = resp.json().get("response", [])
    return [e for e in events if e.get("type") == "Goal"]


def format_message(fixture: dict, goals: list) -> str:
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    score_home = fixture["goals"]["home"]
    score_away = fixture["goals"]["away"]

    lines = ["⚽️ Serie A – Finale", f"{home} {score_home}-{score_away} {away}", ""]

    if goals:
        lines.append("Marcatori:")
        for g in goals:
            minute = g["time"]["elapsed"]
            extra = g["time"].get("extra")
            minute_str = f"{minute}+{extra}'" if extra else f"{minute}'"
            player = g["player"]["name"]
            team = g["team"]["name"]
            detail = g.get("detail", "")
            tag = (
                " (rig.)" if "Penalty" in detail
                else " (autogol)" if "Own Goal" in detail
                else ""
            )
            lines.append(f"{minute_str} {player} ({team}){tag}")

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )
    resp.raise_for_status()


def main() -> None:
    notified = load_notified()
    fixtures = get_todays_fixtures()
    changed = False

    for fixture in fixtures:
        fixture_id = fixture["fixture"]["id"]
        status = fixture["fixture"]["status"]["short"]

        if status not in FINISHED_STATUSES or fixture_id in notified:
            continue

        goals = get_goal_events(fixture_id)
        message = format_message(fixture, goals)
        send_telegram_message(message)

        notified.add(fixture_id)
        changed = True

    if changed:
        save_notified(notified)


if __name__ == "__main__":
    main()
