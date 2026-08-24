"""
Bot Telegram per i risultati (con marcatori) della Serie A.

Usa l'API gratuita di API-Football (https://www.api-football.com/).

Funzionamento normale:
- controlla le partite di Serie A di oggi;
- se una partita è terminata e non è già stata notificata,
  invia risultato e marcatori su Telegram.

Modalità test:
- se TEST_LAST_FINISHED=true, cerca l'ultima partita conclusa
  della stagione e la invia su Telegram senza modificarne lo stato
  in notified.json.
"""

import json
import os
from datetime import date

import requests


API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Attivato solo dal test manuale di GitHub Actions.
TEST_LAST_FINISHED = os.getenv("TEST_LAST_FINISHED", "false").lower() == "true"

SERIE_A_LEAGUE_ID = 135
NOTIFIED_FILE = "notified.json"

API_BASE = "https://v3.football.api-sports.io"
API_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

FINISHED_STATUSES = {"FT", "AET", "PEN"}


def current_season() -> int:
    """
    API-Football identifica la stagione con l'anno di inizio.
    Esempio: stagione 2026/27 -> season=2026.
    """
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def load_notified() -> set:
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))

    return set()


def save_notified(notified: set) -> None:
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(notified), f)


def get_todays_fixtures() -> list:
    """Recupera tutte le partite di Serie A previste per oggi."""

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

    data = resp.json()

    if data.get("errors"):
        raise RuntimeError(f"Errore API-Football: {data['errors']}")

    return data.get("response", [])


def get_latest_finished_fixture():
    """
    Recupera le partite della stagione e restituisce
    l'ultima partita conclusa.

    Questa funzione viene usata soltanto per il test manuale.
    """

    resp = requests.get(
        f"{API_BASE}/fixtures",
        headers=API_HEADERS,
        params={
            "league": SERIE_A_LEAGUE_ID,
            "season": current_season(),
        },
        timeout=15,
    )

    resp.raise_for_status()

    data = resp.json()

    if data.get("errors"):
        raise RuntimeError(f"Errore API-Football: {data['errors']}")

    fixtures = data.get("response", [])

    finished = [
        fixture
        for fixture in fixtures
        if fixture["fixture"]["status"]["short"] in FINISHED_STATUSES
    ]

    if not finished:
        return None

    return max(
        finished,
        key=lambda fixture: fixture["fixture"]["timestamp"]
    )


def get_goal_events(fixture_id: int) -> list:
    """Recupera gli eventi gol di una partita."""

    resp = requests.get(
        f"{API_BASE}/fixtures/events",
        headers=API_HEADERS,
        params={"fixture": fixture_id},
        timeout=15,
    )

    resp.raise_for_status()

    data = resp.json()

    if data.get("errors"):
        raise RuntimeError(f"Errore API-Football: {data['errors']}")

    events = data.get("response", [])

    return [
        event
        for event in events
        if event.get("type") == "Goal"
    ]


def format_message(fixture: dict, goals: list) -> str:
    """Crea il messaggio Telegram con risultato e marcatori."""

    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    score_home = fixture["goals"]["home"]
    score_away = fixture["goals"]["away"]

    lines = [
        "⚽️ Serie A – Finale",
        f"{home} {score_home}-{score_away} {away}",
        "",
    ]

    if goals:
        lines.append("⚽ Marcatori:")

        for goal in goals:
            minute = goal["time"]["elapsed"]
            extra = goal["time"].get("extra")

            if extra:
                minute_str = f"{minute}+{extra}'"
            else:
                minute_str = f"{minute}'"

            player = goal.get("player", {}).get("name") or "Sconosciuto"
            team = goal.get("team", {}).get("name") or ""

            detail = goal.get("detail", "")

            if "Penalty" in detail:
                tag = " (rig.)"
            elif "Own Goal" in detail:
                tag = " (autogol)"
            else:
                tag = ""

            lines.append(
                f"{minute_str} {player} ({team}){tag}"
            )

    else:
        lines.append("Nessun marcatore.")

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    """Invia un messaggio al bot Telegram."""

    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
        },
        timeout=15,
    )

    resp.raise_for_status()


def run_last_match_test() -> None:
    """
    Test completo:
    API-Football -> ultima partita conclusa -> marcatori -> Telegram.
    """

    fixture = get_latest_finished_fixture()

    if fixture is None:
        send_telegram_message(
            "🧪 TEST API-FOOTBALL\n\n"
            "✅ Collegamento API riuscito.\n"
            "Non risultano ancora partite di Serie A concluse "
            "nella stagione corrente."
        )
        return

    fixture_id = fixture["fixture"]["id"]

    goals = get_goal_events(fixture_id)

    message = format_message(fixture, goals)

    send_telegram_message(
        "🧪 TEST COMPLETO API-FOOTBALL\n\n"
        + message
    )


def main() -> None:

    # MODALITÀ TEST
    # Non modifica notified.json.
    if TEST_LAST_FINISHED:
        run_last_match_test()
        return

    # FUNZIONAMENTO NORMALE
    notified = load_notified()

    fixtures = get_todays_fixtures()

    changed = False

    for fixture in fixtures:

        fixture_id = fixture["fixture"]["id"]
        status = fixture["fixture"]["status"]["short"]

        # Ignora partite non concluse.
        if status not in FINISHED_STATUSES:
            continue

        # Ignora partite già inviate.
        if fixture_id in notified:
            continue

        goals = get_goal_events(fixture_id)

        message = format_message(
            fixture,
            goals,
        )

        send_telegram_message(message)

        notified.add(fixture_id)

        changed = True

    if changed:
        save_notified(notified)


if __name__ == "__main__":
    main()
