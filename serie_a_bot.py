"""
Bot Telegram per i risultati della Serie A.

Fonte principale:
- football-data.org -> risultati ufficiali della stagione corrente

Fonte secondaria gratuita:
- TheSportsDB -> tentativo di recuperare i marcatori

Il bot gira tramite GitHub Actions.
"""

import html
import json
import os
import re
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIGURAZIONE
# ============================================================

FOOTBALL_DATA_TOKEN = os.environ["FOOTBALL_DATA_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TEST_LAST_FINISHED = (
    os.getenv("TEST_LAST_FINISHED", "false").lower() == "true"
)

NOTIFIED_FILE = "notified.json"

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
SERIE_A_CODE = "SA"

FOOTBALL_DATA_HEADERS = {
    "X-Auth-Token": FOOTBALL_DATA_TOKEN,
}

# TheSportsDB
# La documentazione pubblica usa la chiave free "123".
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"

# ID Italian Serie A su TheSportsDB
SPORTSDB_SERIE_A_ID = "4332"


# ============================================================
# NOMI CORTI E COLORI SQUADRE
# ============================================================

TEAMS = [
    {
        "short": "Inter",
        "colors": "⚫🔵",
        "aliases": [
            "fc internazionale milano",
            "internazionale",
            "inter milan",
            "inter",
        ],
    },
    {
        "short": "Milan",
        "colors": "🔴⚫",
        "aliases": [
            "ac milan",
            "milan",
        ],
    },
    {
        "short": "Atalanta",
        "colors": "🔵⚫",
        "aliases": [
            "atalanta bc",
            "atalanta",
        ],
    },
    {
        "short": "Bologna",
        "colors": "🔴🔵",
        "aliases": [
            "bologna fc 1909",
            "bologna fc",
            "bologna",
        ],
    },
    {
        "short": "Cagliari",
        "colors": "🔴🔵",
        "aliases": [
            "cagliari calcio",
            "cagliari",
        ],
    },
    {
        "short": "Como",
        "colors": "🔵⚪",
        "aliases": [
            "como 1907",
            "como",
        ],
    },
    {
        "short": "Fiorentina",
        "colors": "🟣⚪",
        "aliases": [
            "acf fiorentina",
            "fiorentina",
        ],
    },
    {
        "short": "Frosinone",
        "colors": "🟡🔵",
        "aliases": [
            "frosinone calcio",
            "frosinone",
        ],
    },
    {
        "short": "Genoa",
        "colors": "🔴🔵",
        "aliases": [
            "genoa cfc",
            "genoa",
        ],
    },
    {
        "short": "Juventus",
        "colors": "⚪⚫",
        "aliases": [
            "juventus fc",
            "juventus",
        ],
    },
    {
        "short": "Lazio",
        "colors": "🔵⚪",
        "aliases": [
            "ss lazio",
            "lazio",
        ],
    },
    {
        "short": "Lecce",
        "colors": "🟡🔴",
        "aliases": [
            "us lecce",
            "lecce",
        ],
    },
    {
        "short": "Monza",
        "colors": "🔴⚪",
        "aliases": [
            "ac monza",
            "monza",
        ],
    },
    {
        "short": "Napoli",
        "colors": "🔵⚪",
        "aliases": [
            "ssc napoli",
            "napoli",
        ],
    },
    {
        "short": "Parma",
        "colors": "🟡🔵",
        "aliases": [
            "parma calcio 1913",
            "parma calcio",
            "parma",
        ],
    },
    {
        "short": "Roma",
        "colors": "🟡🔴",
        "aliases": [
            "as roma",
            "roma",
        ],
    },
    {
        "short": "Sassuolo",
        "colors": "🟢⚫",
        "aliases": [
            "us sassuolo calcio",
            "sassuolo calcio",
            "sassuolo",
        ],
    },
    {
        "short": "Torino",
        "colors": "🟤⚪",
        "aliases": [
            "torino fc",
            "torino",
        ],
    },
    {
        "short": "Udinese",
        "colors": "⚪⚫",
        "aliases": [
            "udinese calcio",
            "udinese",
        ],
    },
    {
        "short": "Venezia",
        "colors": "🟠🟢",
        "aliases": [
            "venezia fc",
            "venezia",
        ],
    },
]


def normalize_name(name: str) -> str:
    """Normalizza un nome per confrontarlo più facilmente."""

    name = (name or "").lower()

    name = re.sub(r"[^a-z0-9à-ÿ ]", " ", name)

    return " ".join(name.split())


def get_team_info(name: str) -> tuple[str, str]:
    """
    Restituisce:
    (nome corto, colori)
    """

    normalized = normalize_name(name)

    for team in TEAMS:
        for alias in team["aliases"]:
            if normalize_name(alias) == normalized:
                return team["short"], team["colors"]

    # Secondo tentativo più permissivo.
    for team in TEAMS:
        for alias in team["aliases"]:
            alias_normalized = normalize_name(alias)

            if alias_normalized in normalized:
                return team["short"], team["colors"]

    # Fallback
    return name, "⚽"


def same_team(name1: str, name2: str) -> bool:
    short1, _ = get_team_info(name1)
    short2, _ = get_team_info(name2)

    return normalize_name(short1) == normalize_name(short2)


# ============================================================
# NOTIFIED.JSON
# ============================================================

def load_notified() -> set:
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))

    return set()


def save_notified(notified: set) -> None:
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(notified), f, indent=2)


# ============================================================
# FOOTBALL-DATA.ORG
# ============================================================

def get_finished_matches() -> list:
    """
    Recupera tutte le partite FINISHED della stagione corrente.
    Serve anche per il test dell'ultima partita.
    """

    response = requests.get(
        f"{FOOTBALL_DATA_BASE}/competitions/{SERIE_A_CODE}/matches",
        headers=FOOTBALL_DATA_HEADERS,
        params={
            "status": "FINISHED",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("matches", [])


def get_todays_finished_matches() -> list:
    """
    Nel funzionamento normale controlliamo soltanto
    le partite concluse oggi.
    """

    today = datetime.now(timezone.utc).date().isoformat()

    response = requests.get(
        f"{FOOTBALL_DATA_BASE}/competitions/{SERIE_A_CODE}/matches",
        headers=FOOTBALL_DATA_HEADERS,
        params={
            "status": "FINISHED",
            "dateFrom": today,
            "dateTo": today,
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


# ============================================================
# THESPORTSDB - MARCATORI GRATIS
# ============================================================

def find_sportsdb_event(match: dict):
    """
    Cerca su TheSportsDB la stessa partita recuperata
    da football-data.org.
    """

    full_home = match["homeTeam"]["name"]
    full_away = match["awayTeam"]["name"]

    home, _ = get_team_info(full_home)
    away, _ = get_team_info(full_away)

    date_event = match["utcDate"][:10]

    # Prima proviamo la ricerca diretta per nome.
    searches = [
        f"{home}_vs_{away}",
        f"{full_home}_vs_{full_away}",
    ]

    for event_name in searches:
        try:
            response = requests.get(
                f"{SPORTSDB_BASE}/searchevents.php",
                params={
                    "e": event_name,
                    "d": date_event,
                },
                timeout=15,
            )

            response.raise_for_status()

            data = response.json()

            events = (
                data.get("event")
                or data.get("events")
                or []
            )

            for event in events:
                if str(event.get("idLeague")) != SPORTSDB_SERIE_A_ID:
                    continue

                event_home = event.get("strHomeTeam", "")
                event_away = event.get("strAwayTeam", "")

                if (
                    same_team(event_home, home)
                    and same_team(event_away, away)
                ):
                    return event

        except (requests.RequestException, ValueError):
            pass

    # Fallback: cerchiamo le partite di Serie A di quel giorno.
    try:
        response = requests.get(
            f"{SPORTSDB_BASE}/eventsday.php",
            params={
                "d": date_event,
                "l": SPORTSDB_SERIE_A_ID,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        events = data.get("events") or []

        for event in events:
            event_home = event.get("strHomeTeam", "")
            event_away = event.get("strAwayTeam", "")

            if (
                same_team(event_home, home)
                and same_team(event_away, away)
            ):
                return event

    except (requests.RequestException, ValueError):
        pass

    return None


def get_sportsdb_timeline(event_id: str) -> list:
    """Scarica la timeline della partita."""

    try:
        response = requests.get(
            f"{SPORTSDB_BASE}/lookuptimeline.php",
            params={
                "id": event_id,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("timeline") or []

    except (requests.RequestException, ValueError):
        return []


def player_short_name(player: str) -> str:
    """
    Davide Frattesi -> Frattesi
    Giovanni Di Lorenzo -> Di Lorenzo
    Kevin De Bruyne -> De Bruyne
    """

    if not player:
        return "Marcatore"

    parts = player.strip().split()

    if len(parts) <= 1:
        return player

    prefixes = {
        "de",
        "di",
        "da",
        "del",
        "della",
        "van",
        "von",
        "der",
        "la",
        "le",
        "lo",
        "dos",
        "do",
    }

    if len(parts) >= 2 and parts[-2].lower() in prefixes:
        return " ".join(parts[-2:])

    return parts[-1]


def minute_sort_value(value: str) -> int:
    """Serve solo per ordinare cronologicamente i gol."""

    if value is None:
        return 999

    match = re.search(r"\d+", str(value))

    if not match:
        return 999

    return int(match.group())


def get_goal_scorers(match: dict) -> list:
    """
    Cerca i marcatori su TheSportsDB.

    IMPORTANTE:
    nel piano gratuito la timeline può essere limitata.

    Mostriamo i marcatori soltanto se il numero di gol
    recuperato coincide con il risultato finale.
    In questo modo non mostriamo mai una lista incompleta.
    """

    score = match.get("score", {}).get("fullTime", {})

    home_score = score.get("home")
    away_score = score.get("away")

    if home_score is None or away_score is None:
        return []

    expected_goals = home_score + away_score

    if expected_goals == 0:
        return []

    event = find_sportsdb_event(match)

    if not event:
        return []

    event_id = event.get("idEvent")

    if not event_id:
        return []

    timeline = get_sportsdb_timeline(event_id)

    home_name = match["homeTeam"]["name"]
    away_name = match["awayTeam"]["name"]

    _, home_colors = get_team_info(home_name)
    _, away_colors = get_team_info(away_name)

    goals = []

    for item in timeline:

        timeline_type = str(
            item.get("strTimeline", "")
        ).lower()

        detail = str(
            item.get("strTimelineDetail", "")
        )

        # Di solito TheSportsDB usa strTimeline = Goal.
        if (
            timeline_type != "goal"
            and "goal" not in detail.lower()
        ):
            continue

        player = item.get("strPlayer")

        if not player:
            continue

        minute = str(
            item.get("intTime") or ""
        ).strip()

        str_home = str(
            item.get("strHome", "")
        ).lower()

        if str_home == "yes":
            colors = home_colors

        elif str_home == "no":
            colors = away_colors

        else:
            _, colors = get_team_info(
                item.get("strTeam", "")
            )

        tag = ""

        detail_lower = detail.lower()

        if "penalty" in detail_lower:
            tag = " rig."

        elif "own goal" in detail_lower:
            tag = " aut."

        goals.append(
            {
                "minute": minute,
                "player": player_short_name(player),
                "colors": colors,
                "tag": tag,
            }
        )

    goals.sort(
        key=lambda goal: minute_sort_value(
            goal["minute"]
        )
    )

    # Se TheSportsDB ci ha dato solo parte dei gol,
    # non mostriamo una lista incompleta.
    if len(goals) != expected_goals:
        return []

    return goals


# ============================================================
# FORMATTAZIONE TELEGRAM
# ============================================================

def format_minute(minute: str) -> str:
    if not minute:
        return ""

    minute = str(minute).strip()

    if minute.endswith("'"):
        return minute

    return f"{minute}'"


def format_match_message(
    match: dict,
    goals: list,
    test: bool = False,
) -> str:

    full_home = match["homeTeam"]["name"]
    full_away = match["awayTeam"]["name"]

    home, home_colors = get_team_info(full_home)
    away, away_colors = get_team_info(full_away)

    score = match.get("score", {}).get(
        "fullTime",
        {},
    )

    home_score = score.get("home")
    away_score = score.get("away")

    matchday = match.get("matchday")

    home = html.escape(str(home))
    away = html.escape(str(away))

    lines = []

    if test:
        lines.extend(
            [
                "🧪 <b>TEST • STAGIONE ATTUALE</b>",
                "",
            ]
        )

    lines.extend(
        [
            "⚽️ <b>SERIE A</b>",
            "",
            (
                f"{home_colors} "
                f"<b>{home}-{away} "
                f"{home_score}-{away_score}</b> "
                f"{away_colors}"
            ),
        ]
    )

    if goals:
        lines.append("")

        for goal in goals:

            minute = format_minute(
                goal["minute"]
            )

            player = html.escape(
                goal["player"]
            )

            tag = goal["tag"]

            lines.append(
                f"{goal['colors']} "
                f"{minute} {player}{tag}"
            )

    if matchday:
        lines.extend(
            [
                "",
                f"📅 Giornata {matchday}",
            ]
        )

    return "\n".join(lines)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(text: str) -> None:

    response = requests.post(
        (
            "https://api.telegram.org/"
            f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        ),
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=20,
    )

    response.raise_for_status()


# ============================================================
# TEST
# ============================================================

def run_last_match_test() -> None:
    """
    Test completo:

    football-data.org
        ↓
    ultima partita Serie A
        ↓
    TheSportsDB (marcatori se disponibili)
        ↓
    Telegram
    """

    match = get_latest_finished_match()

    if match is None:
        send_telegram_message(
            "🧪 <b>TEST SERIE A</b>\n\n"
            "✅ API collegata correttamente.\n"
            "Nessuna partita conclusa trovata."
        )
        return

    goals = get_goal_scorers(match)

    message = format_match_message(
        match,
        goals,
        test=True,
    )

    send_telegram_message(message)


# ============================================================
# BOT NORMALE
# ============================================================

def main() -> None:

    # TEST MANUALE
    if TEST_LAST_FINISHED:
        run_last_match_test()
        return

    notified = load_notified()

    # Nel funzionamento normale ci interessano
    # soltanto le partite concluse oggi.
    matches = get_todays_finished_matches()

    matches.sort(
        key=lambda match: match["utcDate"]
    )

    changed = False

    for match in matches:

        match_id = match["id"]

        if match_id in notified:
            continue

        goals = get_goal_scorers(match)

        message = format_match_message(
            match,
            goals,
        )

        send_telegram_message(message)

        notified.add(match_id)

        changed = True

    if changed:
        save_notified(notified)


if __name__ == "__main__":
    main()
