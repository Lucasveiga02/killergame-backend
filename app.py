from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import json
import unicodedata

# -------------------------------------------------------------------
# APP SETUP
# -------------------------------------------------------------------

app = Flask(__name__)

# Autorise ton GitHub Pages
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_player_state(state: dict, player_id: str) -> dict:
    """Crée l'entrée state pour un joueur si absente. ID = nom."""
    if player_id not in state:
        state[player_id] = {
            "mission_done": False,
            "guess": None,
            "points": 0,
            "discovered_by_target": False
        }
    return state[player_id]


# -------------------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------------------

@app.get("/")
def health():
    return "Backend is running"


# -------------------------------------------------------------------
# GET /api/players
# -> utilisé pour autocomplete (accueil + accusation)
# -------------------------------------------------------------------

@app.get("/api/players")
def get_players():
    players = load_json(PLAYERS_FILE, [])
    return jsonify(players)


# -------------------------------------------------------------------
# GET /api/mission?player=<display>
# -> récup mission + cible + statut mission_done
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
        if normalize(a.get("killer", "")) == norm_input:
            killer_name = a["killer"]

            player_state = ensure_player_state(state, killer_name)
            save_json(STATE_FILE, state)

            return jsonify(
                ok=True,
                player={"id": killer_name, "display": killer_name},
                mission={"text": a.get("mission", "—")},
                target={"display": a.get("target", "—")},
                mission_done=bool(player_state.get("mission_done", False))
            )

    return jsonify(ok=False, error="Player not found"), 404


# -------------------------------------------------------------------
# POST /api/mission_done
# body: { player_id: "<nom>" }  (ou player_display)
# -> valide "J’ai effectué ma mission"
# -------------------------------------------------------------------

@app.post("/api/mission_done")
def mission_done():
    data = request.get_json() or {}
    player_id = data.get("player_id") or data.get("player_display")

    if not player_id:
        return jsonify(ok=False, error="Missing player_id"), 400

    state = load_json(STATE_FILE, {})
    entry = ensure_player_state(state, player_id)

    entry["mission_done"] = True
    save_json(STATE_FILE, state)

    return jsonify(ok=True, mission_done=True)


# -------------------------------------------------------------------
# POST /api/guess
# body: {
#   player_id: "<nom>",
#   accused_killer_id: "<nom>" (ou accused_killer_display),
#   guessed_mission: "..."
# }
# -> enregistre le guess
# -------------------------------------------------------------------

@app.post("/api/guess")
def submit_guess():
    data = request.get_json() or {}

    player_id = data.get("player_id") or data.get("player_display")
    accused_id = data.get("accused_killer_id") or data.get("accused_killer_display")
    guessed_mission = data.get("guessed_mission")

    if not player_id:
        return jsonify(ok=False, error="Missing player_id"), 400
    if not accused_id:
        return jsonify(ok=False, error="Missing accused_killer_id"), 400
    if not guessed_mission:
        return jsonify(ok=False, error="Missing guessed_mission"), 400

    state = load_json(STATE_FILE, {})
    entry = ensure_player_state(state, player_id)

    entry["guess"] = {
        "killer_id": accused_id,          # ID = nom
        "killer_display": accused_id,     # affichage = nom
        "mission": guessed_mission
    }

    save_json(STATE_FILE, state)
    return jsonify(ok=True)


# -------------------------------------------------------------------
# GET /api/leaderboard
# -> tableau admin
# -------------------------------------------------------------------

@app.get("/api/leaderboard")
def leaderboard():
    players = load_json(PLAYERS_FILE, [])
    state = load_json(STATE_FILE, {})

    rows = []
    for p in players:
        name = p.get("id")  # ID = nom
        if not name:
            continue

        s = state.get(name, {})
        guess = s.get("guess") or {}

        rows.append({
            "display": name,
            "points": s.get("points", 0),
            "mission_done": bool(s.get("mission_done", False)),
            "discovered_by_target": bool(s.get("discovered_by_target", False)),
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
