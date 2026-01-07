from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import json
import unicodedata

# -------------------------------------------------------------------
# APP SETUP
# -------------------------------------------------------------------

app = Flask(__name__)

# Autorise uniquement ton GitHub Pages
CORS(app, origins=["https://lucasveiga02.github.io"])

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PLAYERS_FILE = DATA_DIR / "players.json"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.json"
STATE_FILE = DATA_DIR / "state.json"


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------

def normalize(text: str) -> str:
    """Normalise une chaîne pour comparaison fiable (accents / casse)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -------------------------------------------------------------------
# HEALTH CHECK (TEST API)
# -------------------------------------------------------------------

@app.get("/")
def health():
    return "Backend is running"


# -------------------------------------------------------------------
# GET /api/players
# → utilisé pour l’autocomplete (accueil + accusation)
# -------------------------------------------------------------------

@app.get("/api/players")
def get_players():
    players = load_json(PLAYERS_FILE, [])
    return jsonify(players)


# -------------------------------------------------------------------
# GET /api/mission?player=<display>
# → récupération mission + cible
# -------------------------------------------------------------------

@app.get("/api/mission")
def get_mission():
    player_display = request.args.get("player")

    if not player_display:
        return jsonify(ok=False, error="Missing player parameter"), 400

    assignments = load_json(ASSIGNMENTS_FILE, [])
    state = load_json(STATE_FILE, {})

    norm_input = normalize(player_display)

    for a in assignments:
        if normalize(a["killer"]) == norm_input:
            killer_name = a["killer"]

            # état du joueur (créé si absent)
            player_state = state.setdefault(killer_name, {
                "mission_done": False,
                "guess": None,
                "points": 0,
                "discovered_by_target": False
            })

            save_json(STATE_FILE, state)

            return jsonify(
                ok=True,
                player={
                    "id": a.get("killer_id"),
                    "display": killer_name
                },
                mission={
                    "text": a["mission"]
                },
                target={
                    "display": a["target"]
                },
                mission_done=player_state["mission_done"]
            )

    return jsonify(ok=False, error="Player not found"), 404


# -------------------------------------------------------------------
# POST /api/mission_done
# → bouton "J’ai effectué ma mission"
# -------------------------------------------------------------------

@app.post("/api/mission_done")
def mission_done():
    data = request.get_json() or {}
    player_display = data.get("player_display")

    if not player_display:
        return jsonify(ok=False, error="Missing player_display"), 400

    state = load_json(STATE_FILE, {})
    entry = state.setdefault(player_display, {
        "mission_done": False,
        "guess": None,
        "points": 0,
        "discovered_by_target": False
    })

    entry["mission_done"] = True
    save_json(STATE_FILE, state)

    return jsonify(ok=True, mission_done=True)


# -------------------------------------------------------------------
# POST /api/guess
# → "J’ai trouvé la mission dont j’étais la cible"
# -------------------------------------------------------------------

@app.post("/api/guess")
def submit_guess():
    data = request.get_json() or {}

    player_id = data.get("player_id")
    accused_id = data.get("accused_killer_id")
    accused_display = data.get("accused_killer_display")
    guessed_mission = data.get("guessed_mission")

    if not all([accused_display, guessed_mission]):
        return jsonify(ok=False, error="Incomplete guess"), 400

    state = load_json(STATE_FILE, {})
    player_entry = state.setdefault(player_id or "unknown", {
        "mission_done": False,
        "guess": None,
        "points": 0,
        "discovered_by_target": False
    })

    player_entry["guess"] = {
        "killer_id": accused_id,
        "killer_display": accused_display,
        "mission": guessed_mission
    }

    save_json(STATE_FILE, state)
    return jsonify(ok=True)


# -------------------------------------------------------------------
# GET /api/leaderboard
# → écran admin (Lucas Veiga)
# -------------------------------------------------------------------

@app.get("/api/leaderboard")
def leaderboard():
    players = load_json(PLAYERS_FILE, [])
    state = load_json(STATE_FILE, {})

    rows = []

    for p in players:
        display = p["display"]
        s = state.get(display, {})

        guess = s.get("guess") or {}

        rows.append({
            "display": display,
            "points": s.get("points", 0),
            "mission_done": s.get("mission_done", False),
            "discovered_by_target": s.get("discovered_by_target", False),
            "found_killer": bool(guess),
            "guess_killer_display": guess.get("killer_display"),
            "guess_mission": guess.get("mission")
        })

    return jsonify(rows)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
