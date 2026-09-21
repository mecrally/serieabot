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

TEST_JUVE_TRASFERTA = (
    os.getenv("TEST_JUVE_TRASFERTA", "false").lower() == "true"
)

NOTIFIED_FILE = "notified.json"

# Finestra prepartita: quanto al massimo in anticipo può arrivare l'avviso.
# L'affidabilità del TIMING non dipende più da questo margine, ma dal fatto
# di far scattare il workflow con un trigger esterno affidabile (vedi sotto)
# invece che con lo `schedule:` nativo di GitHub, che salta spesso per ore.
NOTIFY_WINDOW_BEFORE = int(os.getenv("NOTIFY_WINDOW_BEFORE_MIN", "30"))  # minuti prima del fischio d'inizio
NOTIFY_WINDOW_AFTER = int(os.getenv("NOTIFY_WINDOW_AFTER_MIN", "10"))   # piccola tolleranza dopo


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
    """Riconosce la Juventus anche se il provider cambia leggermente il nome."""
    normalized = normalize_name(name)
    if normalized == "juventus" or normalized.startswith("juventus "):
        return True
    short_name, _ = get_team_info(name)
    return short_name == "Juventus"


JUVENTUS_FOOTBALL_DATA_ID = "109"


def is_juventus_team(team) -> bool:
    """Riconoscimento robusto per gli oggetti team di football-data.org."""
    if isinstance(team, dict):
        if str(team.get("id", "")) == JUVENTUS_FOOTBALL_DATA_ID:
            return True
        if str(team.get("tla", "")).upper() == "JUV":
            return True
        for key in ("name", "shortName"):
            if is_juventus(str(team.get(key, ""))):
                return True
        return False
    return is_juventus(str(team or ""))


# ============================================================
# FUNZIONI TEMPO E FORMATTAZIONE (MODIFICATE)
# ============================================================

def is_starting_soon(utc_date_string: str, max_minutes: int = 45, grace_minutes: int = 0) -> bool:
    """Controlla se la partita inizia entro 'max_minutes' minuti da adesso.

    'grace_minutes' concede una tolleranza anche DOPO il calcio d'inizio:
    serve perché le run schedulate di GitHub Actions non sono affidabili
    (possono saltare per ore), quindi la prima run utile potrebbe capitare
    a partita già iniziata da pochi minuti.
    """
    if not utc_date_string:
        return False
    try:
        clean_date = utc_date_string.replace("Z", "+00:00")
        match_time = datetime.fromisoformat(clean_date)
        now = datetime.now(timezone.utc)
        delta = match_time - now
        return timedelta(minutes=-grace_minutes) <= delta <= timedelta(minutes=max_minutes)
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
    # Usiamo la data italiana: è il calendario che interessa all'utente.
    now_utc = datetime.now(timezone.utc)
    today = (now_utc.astimezone(ITALY_TZ).date() if ITALY_TZ else now_utc.date()).isoformat()
    matches = get_serie_a_matches(today)
    changed = False

    print(f"[SERIE A] Data controllo: {today} - partite ricevute: {len(matches)}")

    for match in matches:
        home_team = match.get("homeTeam", {})
        away_team = match.get("awayTeam", {})
        home_name = home_team.get("name", "")
        away_name = away_team.get("name", "")

        juve_home = is_juventus_team(home_team)
        juve_away = is_juventus_team(away_team)

        print(
            f"[SERIE A] {match.get('id')} | {home_name} - {away_name} | "
            f"Juve casa={juve_home} trasferta={juve_away} | utc={match.get('utcDate')}"
        )

        # Stessa identica regola sia in casa sia in trasferta.
        if not (juve_home or juve_away):
            continue

        match_id = str(match["id"])
        key = f"sa_pre:{match_id}"

        if key in notified:
            print(f"[SERIE A] {key} già notificata")
            continue

        utc_date = match.get("utcDate")
        if not is_starting_soon(utc_date, max_minutes=NOTIFY_WINDOW_BEFORE, grace_minutes=NOTIFY_WINDOW_AFTER):
            print(f"[SERIE A] {key} fuori dalla finestra prepartita")
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
        print(f"[SERIE A] Notifica inviata: {key}")

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

    # /fixtures da solo non esiste nell'API di footballdata.io: cadeva sempre
    # sul fallback "/fixtures/results", che però contiene solo partite GIA' finite
    # (per questo non trovava mai la partita di oggi non ancora iniziata).
    # L'endpoint corretto per "le partite di oggi" e' /fixtures/today.
    response = requests.get(
        f"{FDIO_BASE}/fixtures/today",
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
        print("[EUROPA LEAGUE] Salto il controllo: oggi non è nella finestra mar/mer/gio")
        return False

    today = datetime.now(timezone.utc).date().isoformat()
    matches = get_juventus_europa_matches(today)

    print(f"[EUROPA LEAGUE] Data controllo: {today} - partite Juventus trovate: {len(matches)}")

    if force and not matches:
        send_telegram_message(
            "🧪 <b>TEST • EUROPA LEAGUE JUVENTUS</b>\n\n"
            "✅ Footballdata.io collegato.\n"
            "Nessuna partita Juventus trovata per oggi."
        )
        return False

    changed = False
    any_in_window = False

    for match in matches:
        match_id = match.get("match_id") or match.get("id")
        home = footballdata_team_name(match.get("home_team"))
        away = footballdata_team_name(match.get("away_team"))

        # In footballdata.io, la data può essere su starting_at, date, o utcDate
        utc_date = match.get("starting_at") or match.get("date") or match.get("utc_date")
        in_window = is_starting_soon(utc_date, max_minutes=NOTIFY_WINDOW_BEFORE, grace_minutes=NOTIFY_WINDOW_AFTER)

        print(
            f"[EUROPA LEAGUE] {match_id} | {home} - {away} | "
            f"finestra 45min={in_window} | utc={utc_date}"
        )

        if match_id is None:
            continue

        key = f"uel_pre:{match_id}"
        if key in notified:
            continue
        if not in_window:
            continue

        any_in_window = True
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

    # Test forzato: la partita è stata trovata ma è fuori dalla finestra dei 45 minuti
    # (già iniziata, o troppo lontana) -> altrimenti il test restava muto e sembrava rotto.
    if force and matches and not any_in_window:
        lines = [
            "🧪 <b>TEST • EUROPA LEAGUE JUVENTUS</b>",
            "",
            "✅ Footballdata.io collegato. Partita trovata, ma fuori dalla finestra prepartita (45 min):",
        ]
        for match in matches:
            home = footballdata_team_name(match.get("home_team"))
            away = footballdata_team_name(match.get("away_team"))
            utc_date = match.get("starting_at") or match.get("date") or match.get("utc_date")
            lines.append(f"• {home} - {away} (orario: {utc_date})")
        send_telegram_message("\n".join(lines))

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
        
        if not is_starting_soon(utc_date, max_minutes=NOTIFY_WINDOW_BEFORE, grace_minutes=NOTIFY_WINDOW_AFTER):
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
# TEST DETERMINISTICO: JUVENTUS IN TRASFERTA
# ============================================================

def test_juve_trasferta_all() -> None:
    """
    Test manuale indipendente dalle API e dal calendario reale.
    Verifica che la Juventus venga riconosciuta come squadra OSPITE
    in Serie A, Europa League e Coppa Italia e invia 3 messaggi Telegram.
    Se uno dei controlli fallisce, il workflow termina con errore.
    """
    fake_time = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()

    # 1) SERIE A: forma dati football-data.org
    serie_a_match = {
        "id": 990001,
        "homeTeam": {"id": 471, "name": "US Sassuolo Calcio", "shortName": "Sassuolo", "tla": "SAS"},
        "awayTeam": {"id": 109, "name": "Juventus Turin", "shortName": "Juventus", "tla": "JUV"},
        "utcDate": fake_time,
        "matchday": 99,
    }
    home_sa = serie_a_match["homeTeam"]
    away_sa = serie_a_match["awayTeam"]
    assert not is_juventus_team(home_sa), "Serie A: la squadra di casa è stata riconosciuta erroneamente come Juventus"
    assert is_juventus_team(away_sa), "Serie A: Juventus ospite NON riconosciuta"
    assert is_starting_soon(fake_time, max_minutes=45), "Serie A: test finestra 45 minuti fallito"
    send_telegram_message(
        format_prematch(
            "🧪 <b>TEST TRASFERTA • SERIE A</b>",
            home_sa["name"],
            away_sa["name"],
            fake_time,
            "✅ Juventus riconosciuta come squadra ospite",
        )
    )

    # 2) EUROPA LEAGUE: forma dati footballdata.io
    europa_match = {
        "id": 990002,
        "home_team": {"team_name": "Olympique de Marseille"},
        "away_team": {"team_name": "Juventus FC"},
        "league": {"name": "UEFA Europa League"},
        "starting_at": fake_time,
        "round": "Test trasferta",
    }
    home_el = footballdata_team_name(europa_match["home_team"])
    away_el = footballdata_team_name(europa_match["away_team"])
    assert is_europa_league(europa_match), "Europa League: competizione non riconosciuta"
    assert not is_juventus(home_el), "Europa League: la squadra di casa è stata riconosciuta erroneamente come Juventus"
    assert is_juventus(away_el), "Europa League: Juventus ospite NON riconosciuta"
    assert is_starting_soon(fake_time, max_minutes=45), "Europa League: test finestra 45 minuti fallito"
    send_telegram_message(
        format_prematch(
            "🧪 <b>TEST TRASFERTA • EUROPA LEAGUE</b>",
            home_el,
            away_el,
            fake_time,
            "✅ Juventus riconosciuta come squadra ospite",
            "Test locale, nessuna chiamata API partita",
        )
    )

    # 3) COPPA ITALIA: forma dati TheSportsDB
    coppa_event = {
        "idEvent": "990003",
        "idLeague": COPPA_ITALIA_ID,
        "strHomeTeam": "Inter",
        "strAwayTeam": "Juventus FC",
        "strTimestamp": fake_time,
        "strRound": "Test trasferta",
    }
    assert not is_juventus(coppa_event["strHomeTeam"]), "Coppa Italia: la squadra di casa è stata riconosciuta erroneamente come Juventus"
    assert is_juventus_coppa_event(coppa_event), "Coppa Italia: Juventus ospite NON riconosciuta"
    assert is_starting_soon(fake_time, max_minutes=45), "Coppa Italia: test finestra 45 minuti fallito"
    send_telegram_message(
        format_prematch(
            "🧪 <b>TEST TRASFERTA • COPPA ITALIA</b>",
            coppa_event["strHomeTeam"],
            coppa_event["strAwayTeam"],
            fake_time,
            "✅ Juventus riconosciuta come squadra ospite",
        )
    )

    print("[TEST TRASFERTA] OK: Serie A, Europa League e Coppa Italia")


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # Test
    if TEST_JUVE_TRASFERTA:
        test_juve_trasferta_all()
        return

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
