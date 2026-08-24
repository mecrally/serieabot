"""
Bot Telegram per i risultati della Serie A.

Fonte dati: football-data.org
Il bot gira tramite GitHub Actions.

Funzionamento normale:
- controlla le partite di Serie A della stagione corrente;
- quando trova una partita FINISHED non ancora notificata,
  invia il risultato su Telegram;
- salva l'ID della partita in notified.json.

Modalità test:
- TEST_LAST_FINISHED=true invia su Telegram
  l'ultima partita conclusa della Serie A corrente.
"""

import json
import os
from datetime import datetime, timezone

import requests


FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TEST_LAST_FINISHED = (
    os.getenv("TEST_LAST_FINISHED", "false").lower() == "true"
)

NOTIFIED_FILE = "notified.json"

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
SERIE_A_CODE = "SA"

HEADERS = {
    "X-Auth-Token": FOOTBALL_DATA_TOKEN,
}


def load_notified() -> set:
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))

    return set()


def save_notified(notified: set) -> None:
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(notified), f, indent=2)


def get_finished_matches() -> list:
    """
    Recupera le partite FINISHED della stagione corrente di Serie A.
    Non specifichiamo season: football-data.org usa automaticamente
    la stagione attiva.
    """

    response = requests.get(
        f"{FOOTBALL_DATA_BASE}/competitions/{SERIE_A_CODE}/matches",
        headers=HEADERS,
        params={
            "status": "FINISHED",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("matches", [])


def get_latest_finished_match():
    matches = get_finished_matches()

    if not matches:
        return None

    return max(
        matches,
        key=lambda match: match["utcDate"],
    )


def format_match_message(match: dict, test: bool = False) -> str:
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]

    score = match.get("score", {}).get("fullTime", {})

    home_score = score.get("home")
    away_score = score.get("away")

    matchday = match.get("matchday")

    utc_date = match.get("utcDate", "")

    lines = []

    if test:
        lines.extend([
            "🧪 TEST SERIE A – STAGIONE ATTUALE",
            "",
        ])

    lines.append("⚽️ Serie A – Finale")

    lines.append(
        f"{home} {home_score}-{away_score} {away}"
    )

    if matchday:
        lines.append(f"📅 Giornata {matchday}")

    if utc_date:
        try:
            dt = datetime.fromisoformat(
                utc_date.replace("Z", "+00:00")
            )

            italian_time = dt.astimezone()

            lines.append(
                "🕒 "
                + italian_time.strftime("%d/%m/%Y %H:%M")
            )
        except ValueError:
            pass

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
        },
        timeout=20,
    )

    response.raise_for_status()


def run_last_match_test() -> None:
    """
    Test completo:
    football-data.org -> Serie A corrente ->
    ultima partita finita -> Telegram.
    """

    match = get_latest_finished_match()

    if match is None:
        send_telegram_message(
            "🧪 TEST FOOTBALL-DATA.ORG\n\n"
            "✅ API collegata correttamente.\n"
            "Non risultano ancora partite concluse "
            "nella Serie A corrente."
        )
        return

    message = format_match_message(
        match,
        test=True,
    )

    send_telegram_message(message)


def main() -> None:

    # TEST MANUALE
    if TEST_LAST_FINISHED:
        run_last_match_test()
        return

    # FUNZIONAMENTO NORMALE
    notified = load_notified()

    matches = get_finished_matches()

    # Ordiniamo cronologicamente.
    matches.sort(
        key=lambda match: match["utcDate"]
    )

    changed = False

    for match in matches:
        match_id = match["id"]

        if match_id in notified:
            continue

        message = format_match_message(match)

        send_telegram_message(message)

        notified.add(match_id)
        changed = True

    if changed:
        save_notified(notified)


if __name__ == "__main__":
    main()
