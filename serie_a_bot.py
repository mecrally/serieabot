import html
import json
import os
import re
from datetime import datetime, timezone, timedelta

# Proviamo ad importare ZoneInfo per convertire l'orario in quello italiano (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
    ITALY_TZ = ZoneInfo("Europe/Rome")
except ImportError:
    ITALY_TZ = None

import requests


# ============================================================
# SECRETS / CONFIGURAZIONE
# ============================================================

FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
FOOTBALLDATA_IO_KEY = os.getenv("FOOTBALLDATA_IO_KEY", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TEST_LAST_FINISHED = (
    os.getenv("TEST_LAST_FINISHED", "false").lower() == "true"
)

TEST_JUVE_EUROPA = (
    os.getenv("TEST_JUVE_EUROPA", "false").lower() == "true"
)

TEST_JUVE_COPPA = (
    os.getenv("TEST_JUVE_COPPA", "false").lower() == "true"
)

NOTIFIED_FILE = "notified.json"


# ============================================================
# API
# ============================================================

# Serie A
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

FOOTBALL_DATA_HEADERS = {
    "X-Auth-Token": FOOTBALL_DATA_TOKEN,
}

# Europa League
FDIO_BASE = "https://footballdata.io/api/v1"

FDIO_HEADERS = {
    "Authorization": f"Bearer {FOOTBALLDATA_IO_KEY}",
}

# Coppa Italia
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"

# ID Coppa Italia su TheSportsDB
COPPA_ITALIA_ID = "4506"


# ============================================================
# NOMI CORTI + COLORI
# ============================================================

TEAM_MAP = {
    "atalanta": ("Atalanta", "🔵⚫"),
    "atalanta bc": ("Atalanta", "🔵⚫"),
    "bologna": ("Bologna", "🔴🔵"),
    "bologna fc 1909": ("Bologna", "🔴🔵"),
    "cagliari": ("Cagliari", "🔴🔵"),
    "cagliari calcio": ("Cagliari", "🔴🔵"),
    "como": ("Como", "🔵⚪"),
    "como 1907": ("Como", "🔵⚪"),
    "fiorentina": ("Fiorentina", "🟣⚪"),
    "acf fiorentina": ("Fiorentina", "🟣⚪"),
    "frosinone": ("Frosinone", "🟡🔵"),
    "frosinone calcio": ("Frosinone", "🟡🔵"),
    "genoa": ("Genoa", "🔴🔵"),
    "genoa cfc": ("Genoa", "🔴🔵"),
    "inter": ("Inter", "⚫🔵"),
    "inter milan": ("Inter", "⚫🔵"),
    "internazionale": ("Inter", "⚫🔵"),
    "fc internazionale milano": ("Inter", "⚫🔵"),
    "juventus": ("Juventus", "⚪⚫"),
    "juventus fc": ("Juventus", "⚪⚫"),
    "lazio": ("Lazio", "🔵⚪"),
    "ss lazio": ("Lazio", "🔵⚪"),
    "lecce": ("Lecce", "🟡🔴"),
    "us lecce": ("Lecce", "🟡🔴"),
    "milan": ("Milan", "🔴⚫"),
    "ac milan": ("Milan", "🔴⚫"),
    "monza": ("Monza", "🔴⚪"),
    "ac monza": ("Monza", "🔴⚪"),
    "napoli": ("Napoli", "🔵⚪"),
    "ssc napoli": ("Napoli", "🔵⚪"),
    "parma": ("Parma", "🟡🔵"),
    "parma calcio": ("Parma", "🟡🔵"),
    "parma calcio 1913": ("Parma", "🟡🔵"),
    "roma": ("Roma", "🟡🔴"),
    "as roma": ("Roma", "🟡🔴"),
    "sassuolo": ("Sassuolo", "🟢⚫"),
    "sassuolo calcio": ("Sassuolo", "🟢⚫"),
    "us sassuolo calcio": ("Sassuolo", "🟢⚫"),
    "torino": ("Torino", "🟤⚪"),
    "torino fc": ("Torino", "🟤⚪"),
    "udinese": ("Udinese", "⚪⚫"),
    "udinese calcio": ("Udinese", "⚪⚫"),
    "venezia": ("Venezia", "🟠🟢"),
    "venezia fc": ("Venezia", "🟠🟢"),
    
    # Avversarie europee...
    "olympique de marseille": ("Marseille", "🔵⚪"),
    "marseille": ("Marseille", "🔵⚪"),
    "bayer leverkusen": ("Leverkusen", "🔴⚫"),
    "bayer 04 leverkusen": ("Leverkusen", "🔴⚫"),
    "real sociedad": ("Real Sociedad", "🔵⚪"),
    "rennes": ("Rennes", "🔴⚫"),
    "stade rennais": ("Rennes", "🔴⚫"),
    "celta": ("Celta", "🔵⚪"),
    "celta vigo": ("Celta", "🔵⚪"),
    "crystal palace": ("Crystal Palace", "🔴🔵"),
    "bournemouth": ("Bournemouth", "🔴⚫"),
    "afc bournemouth": ("Bournemouth", "🔴⚫"),
    "sunderland": ("Sunderland", "🔴⚪"),
    "hoffenheim": ("Hoffenheim", "🔵⚪"),
    "az": ("AZ", "🔴⚪"),
    "az alkmaar": ("AZ", "🔴⚪"),
    "benfica": ("Benfica", "🔴⚪"),
    "sl benfica": ("Benfica", "🔴⚪"),
    "anderlecht": ("Anderlecht", "🟣⚪"),
    "salzburg": ("Salzburg", "🔴⚪"),
    "red bull salzburg": ("Salzburg", "🔴⚪"),
    "besiktas": ("Beşiktaş", "⚫⚪"),
    "ferencvaros": ("Ferencváros", "🟢⚪"),
}


def normalize_name(value: str) -> str:
    value = (value or "").lower()
    replacements = {
        "à": "a", "á": "a", "ä": "a", "è": "e", "é": "e", "ë": "e",
        "ì": "i", "í": "i", "ò": "o", "ó": "o", "ö": "o", "ù": "u",
        "ú": "u", "ü": "u", "ş": "s", "š": "s", "ć": "c", "č": "c", "ž": "z",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    return " ".join(value.split())

NORMALIZED_TEAM_MAP = {
    normalize_name(name): info
    for name, info in TEAM_MAP.items()
}

def get_team_info(name: str) -> tuple[str, str]:
    normalized = normalize_name(name)
    if normalized in NORMALIZED_TEAM_MAP:
        return NORMALIZED_TEAM_MAP[normalized]
    return name, "⚽"

def is_juventus(name: str) -> bool:
    short_name, _ = get_team_info(name)
    return short_name == "Juventus"


# ============================================================
# FUNZIONI TEMPO E FORMATTAZIONE (MODIFICATE)
# ============================================================

def is_starting_soon(utc_date_string: str, max_minutes: int = 45) -> bool:
    """Controlla se la partita inizia nei prossimi 'max_minutes' minuti."""
    if not utc_date_string:
        return False
    try:
        clean_date = utc_date_string.replace("Z", "+00:00")
        match_time = datetime.fromisoformat(clean_date)
        now = datetime.now(timezone.utc)
        delta = match_time - now
        return timedelta(minutes=0) <= delta <= timedelta(minutes=max_minutes)
    except Exception:
        return False

def format_prematch(
    title: str,
    home_name: str,
    away_name: str,
    utc_date_string: str = None,
    detail: str = None,
    attribution: str = None,
) -> str:
    home, home_colors = get_team_info(home_name)
    away, away_colors = get_team_info(away_name)

    orario = "a breve"
    if utc_date_string:
        try:
            clean_date = utc_date_string.replace("Z", "+00:00")
            match_time = datetime.fromisoformat(clean_date)
            # Converte l'orario nel fuso orario di Roma (Italia)
            if ITALY_TZ:
                match_time = match_time.astimezone(ITALY_TZ)
                orario = match_time.strftime("%H:%M")
            else:
                orario = match_time.strftime("%H:%M (UTC)")
        except:
            pass

    lines = [
        title,
        "",
        f"{home_colors} <b>{html.escape(home)} - {html.escape(away)}</b> {away_colors}",
        f"⏳ <i>Calcio d'inizio alle {orario}</i>",
    ]

    if detail:
        lines.extend(["", html.escape(detail)])
    if attribution:
        lines.extend(["", f"<i>{html.escape(attribution)}</i>"])

    return "\n".join(lines)


# ============================================================
# NOTIFIED.JSON
# ============================================================

def load_notified() -> set:
    if not os.path.exists(NOTIFIED_FILE):
        return set()
    with open(NOTIFIED_FILE, "r", encoding="utf-8") as file:
        return {str(item) for item in json.load(file)}

def save_notified(notified: set) -> None:
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as file:
        json.dump(sorted(notified), file, indent=2, ensure_ascii=False)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()


# ============================================================
# SERIE A - PREPARTITA JUVENTUS
# ============================================================

def get_serie_a_matches(date_string=None) -> list:
    params = {}
    if date_string:
        params["dateFrom"] = date_string
        params["dateTo"] = date_string

    response = requests.get(
        f"{FOOTBALL_DATA_BASE}/competitions/SA/matches",
        headers=FOOTBALL_DATA_HEADERS,
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("matches", [])

def notify_serie_a(notified: set) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    matches = get_serie_a_matches(today)
    changed = False

    for match in matches:
        home_name = match["homeTeam"]["name"]
        away_name = match["awayTeam"]["name"]

        # Filtro: Solo Juventus
        if not (is_juventus(home_name) or is_juventus(away_name)):
            continue

        match_id = str(match["id"])
        key = f"sa_pre:{match_id}"

        if key in notified:
            continue

        utc_date = match.get("utcDate")
        if not is_starting_soon(utc_date, max_minutes=45):
            continue

        detail = f"📅 Giornata {match['matchday']}" if match.get("matchday") else None

        message = format_prematch(
            "⚽️ <b>SERIE A</b>",
            home_name,
            away_name,
            utc_date,
            detail,
        )

        send_telegram_message(message)
        notified.add(key)
        changed = True

    return changed


def test_last_serie_a() -> None:
    # Test adattato per inviare una notifica finta di prepartita della Juve
    matches = get_serie_a_matches()
    juve_matches = [
        m for m in matches 
        if is_juventus(m["homeTeam"]["name"]) or is_juventus(m["awayTeam"]["name"])
    ]

    if not juve_matches:
        send_telegram_message(
            "🧪 <b>TEST SERIE A</b>\n\n✅ API collegata.\nNessuna partita della Juventus in calendario trovata."
        )
        return

    # Prendi la prossima o l'ultima
    match = juve_matches[-1]
    detail = f"📅 Giornata {match['matchday']}" if match.get("matchday") else None

    send_telegram_message(
        format_prematch(
            "🧪 <b>TEST • SERIE A</b>",
            match["homeTeam"]["name"],
            match["awayTeam"]["name"],
            match.get("utcDate"),
            detail,
        )
    )


# ============================================================
# JUVENTUS EUROPA LEAGUE - PREPARTITA
# ============================================================

def extract_footballdata_matches(payload: dict) -> list:
    data = payload.get("data", [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("matches", "fixtures", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []

def footballdata_team_name(team) -> str:
    if isinstance(team, dict):
        return team.get("team_name") or team.get("name") or ""
    return str(team or "")

def is_europa_league(match: dict) -> bool:
    league = match.get("league", {})
    if isinstance(league, dict):
        text = " ".join(
            str(league.get(key, ""))
            for key in ("name", "competition_name", "league_name")
        )
    else:
        text = str(league)
    text = normalize_name(text)
    return "europa league" in text and "conference" not in text

def get_juventus_europa_matches(date_string: str) -> list:
    if not FOOTBALLDATA_IO_KEY:
        return []

    # Cerchiamo nei 'fixtures' generici invece che nei risultati
    response = requests.get(
        f"{FDIO_BASE}/fixtures",
        headers=FDIO_HEADERS,
        params={"date": date_string, "limit": 100},
        timeout=20,
    )
    
    # Se la rotta /fixtures normale non esiste, fallback sulla vecchia
    if response.status_code != 200:
        response = requests.get(
            f"{FDIO_BASE}/fixtures/results",
            headers=FDIO_HEADERS,
            params={"date": date_string, "limit": 100},
            timeout=20,
        )

    response.raise_for_status()
    matches = []

    for match in extract_footballdata_matches(response.json()):
        home = footballdata_team_name(match.get("home_team"))
        away = footballdata_team_name(match.get("away_team"))

        if not is_europa_league(match):
            continue
        if not (is_juventus(home) or is_juventus(away)):
            continue

        matches.append(match)

    return matches


def notify_juventus_europa(notified: set, force=False) -> bool:
    weekday = datetime.now(timezone.utc).weekday()

    # Limitiamo le chiamate a martedì(1), mercoledì(2), giovedì(3)
    if not force and weekday not in {1, 2, 3}:
        return False

    today = datetime.now(timezone.utc).date().isoformat()
    matches = get_juventus_europa_matches(today)

    if force and not matches:
        send_telegram_message(
            "🧪 <b>TEST • EUROPA LEAGUE JUVENTUS</b>\n\n"
            "✅ Footballdata.io collegato.\n"
            "Nessuna partita Juventus trovata per oggi."
        )
        return False

    changed = False

    for match in matches:
        match_id = match.get("match_id") or match.get("id")
        if match_id is None:
            continue

        key = f"uel_pre:{match_id}"
        if key in notified:
            continue

        home = footballdata_team_name(match.get("home_team"))
        away = footballdata_team_name(match.get("away_team"))

        # In footballdata.io, la data può essere su starting_at, date, o utcDate
        utc_date = match.get("starting_at") or match.get("date") or match.get("utc_date")
        
        if not is_starting_soon(utc_date, max_minutes=45):
            continue

        round_name = match.get("round") or match.get("game_week")
        detail = f"📅 {round_name}" if round_name else None

        message = format_prematch(
            "🏆 <b>EUROPA LEAGUE</b>",
            home,
            away,
            utc_date,
            detail,
            "Dati: Footballdata.io",
        )

        send_telegram_message(message)
        notified.add(key)
        changed = True

    return changed


# ============================================================
# JUVENTUS COPPA ITALIA - PREPARTITA
# ============================================================

def is_juventus_coppa_event(event: dict) -> bool:
    if str(event.get("idLeague", "")) != COPPA_ITALIA_ID:
        return False
    home = event.get("strHomeTeam", "")
    away = event.get("strAwayTeam", "")
    return is_juventus(home) or is_juventus(away)

def get_juventus_coppa_events(date_string: str) -> list:
    found = {}
    
    # Tentativo 1
    try:
        response = requests.get(
            f"{SPORTSDB_BASE}/searchevents.php",
            params={"e": "Juventus", "d": date_string},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        events = data.get("event") or data.get("events") or []
        for event in events:
            if is_juventus_coppa_event(event):
                event_id = str(event.get("idEvent", ""))
                found[event_id] = event
    except (requests.RequestException, ValueError):
        pass

    # Tentativo 2
    try:
        response = requests.get(
            f"{SPORTSDB_BASE}/eventsday.php",
            params={"d": date_string, "l": COPPA_ITALIA_ID},
            timeout=15,
        )
        response.raise_for_status()
        events = response.json().get("events") or []
        for event in events:
            if is_juventus_coppa_event(event):
                event_id = str(event.get("idEvent", ""))
                found[event_id] = event
    except (requests.RequestException, ValueError):
        pass

    return list(found.values())


def notify_juventus_coppa(notified: set, force=False) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    events = get_juventus_coppa_events(today)

    if force and not events:
        send_telegram_message(
            "🧪 <b>TEST • COPPA ITALIA JUVENTUS</b>\n\n"
            "✅ TheSportsDB raggiungibile.\n"
            "Nessuna partita Juventus trovata oggi."
        )
        return False

    changed = False

    for event in events:
        event_id = event.get("idEvent")
        if not event_id:
            continue

        key = f"coppa_pre:{event_id}"
        if key in notified:
            continue

        # TheSportsDB salva la data in UTC in strTimestamp
        utc_date = event.get("strTimestamp")
        
        if not is_starting_soon(utc_date, max_minutes=45):
            continue

        round_name = event.get("strRound") or event.get("intRound")
        detail = f"📅 {round_name}" if round_name else None

        message = format_prematch(
            "🇮🇹 <b>COPPA ITALIA</b>",
            event.get("strHomeTeam", ""),
            event.get("strAwayTeam", ""),
            utc_date,
            detail,
        )

        send_telegram_message(message)
        notified.add(key)
        changed = True

    return changed


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # Test
    if TEST_LAST_FINISHED:
        test_last_serie_a()
        return

    if TEST_JUVE_EUROPA:
        notify_juventus_europa(set(), force=True)
        return

    if TEST_JUVE_COPPA:
        notify_juventus_coppa(set(), force=True)
        return

    # Funzionamento automatico
    notified = load_notified()
    changed = False

    if notify_serie_a(notified):
        changed = True

    if notify_juventus_europa(notified):
        changed = True

    if notify_juventus_coppa(notified):
        changed = True

    if changed:
        save_notified(notified)

if __name__ == "__main__":
    main()
