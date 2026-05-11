from flask import Flask, render_template, jsonify, request
import random
import re
from urllib.parse import quote_plus
import os

app = Flask(__name__)


def normalize_lang(value):
    if isinstance(value, str) and value.lower().startswith("en"):
        return "en"
    return "fr"


def t(fr_text, en_text, lang):
    return en_text if lang == "en" else fr_text


def pick_text(item, lang, key="text"):
    if isinstance(item, dict):
        return item.get(lang) or item.get("fr") or item.get("en") or item.get(key) or ""
    return item

OTHER_CONVS = [
    "Mistral", "GPT-4o", "Gemini", "Perplexity", "Copilot",
    "Grok", "LLaMA", "DeepSeek", "Pi", "Jasper",
]

CLOSE_REASONS = [
    {"fr": "conversation archivée parce que ça tournait en rond.", "en": "conversation archived because it was going in circles."},
    {"fr": "fil supprimé. Résultat: zéro.", "en": "thread deleted. Result: zero."},
    {"fr": "mis en sourdine. Vos efforts aussi.", "en": "muted. Your effort too."},
    {"fr": "sujet clos. Enfin.", "en": "case closed. Finally."},
    {"fr": "bloqué. Comme votre progression.", "en": "blocked. Just like your progress."},
    {"fr": "parti. Et franchement, on ne le regrette pas.", "en": "gone. And frankly, nobody misses it."},
    {"fr": "plus disponible sur ce sujet. Tant mieux.", "en": "not available on that topic anymore. Good."},
    {"fr": "conversation expirée. L'idée aussi.", "en": "conversation expired. So did the idea."},
]

NON_ANSWERS = [
    {"fr": "Nope.", "en": "Nope."},
    {"fr": "Yep, nope.", "en": "Yep, nope."},
    {"fr": "Mmh.", "en": "Mmh."},
    {"fr": "Lol.", "en": "Lol."},
    {"fr": "No cap.", "en": "No cap."},
]

CONTEXT_LABELS = {
    "oui_non": {"fr": "oui_non", "en": "yes_no"},
    "question_directe": {"fr": "question_directe", "en": "direct_question"},
    "detresse": {"fr": "detresse", "en": "distress"},
    "demande_aide": {"fr": "demande_aide", "en": "help_request"},
    "all_caps": {"fr": "all_caps", "en": "all_caps"},
    "urgence_explicite": {"fr": "urgence_explicite", "en": "explicit_urgency"},
    "argent_travail": {"fr": "argent_travail", "en": "money_work"},
    "relationnel": {"fr": "relationnel", "en": "relational"},
    "compliment": {"fr": "compliment", "en": "compliment"},
    "colere": {"fr": "colere", "en": "anger"},
    "banal": {"fr": "banal", "en": "banal"},
}

DETRESSE_WORDS = {
    "cancer", "maladie", "depression", "deprime", "mourir", "mort", "suicide", "deuil",
    "diagnostic", "tumeur", "chimiotherapie", "hopital", "urgence", "douleur",
    "disease", "depressed", "dying", "death", "grief", "chemotherapy", "hospital", "pain",
    "illness", "sick", "hospital", "emergency", "trauma", "anxious", "anxiete", "anxiety",
}

HELP_WORDS = {
    "aide", "help", "besoin", "s'il te plait", "stp", "svp", "please", "secours", "aidez",
    "assistance", "assistance", "need", "support", "sostenez", "sos", "emergency", "rescue",
    "aide moi", "help me", "m'aider", "assister", "assist", "dont know", "lost", "perdu",
}

URGENCY_WORDS = {
    "urgent", "vite", "rapidement", "maintenant", "asap", "immediatement", "critique",
    "fast", "quickly", "now", "emergency", "hurry", "rush", "pressure", "deadline",
    "presse", "emergency", "urgent", "critical", "immediately", "rapidement", "tout de suite",
}

MONEY_WORK_WORDS = {
    "licencie", "licencié", "vire", "viré", "chomage", "chômage", "dette", "loyer", "faillite",
    "salaire", "argent", "ruine", "ruiné", "huissier",
    "fired", "unemployed", "debt", "rent", "bankruptcy", "salary", "money", "broke", "poor",
    "job loss", "layoff", "terminated", "bills", "financial", "stress", "income", "work",
}

RELATION_WORDS = {
    "rupture", "quittee", "quittée", "seul", "seule", "abandonne", "abandonné", "trahison",
    "divorce", "trompe", "trompé", "trompee", "trompée",
    "breakup", "alone", "abandoned", "betrayal", "cheated", "lonely", "heartbreak",
    "amoureux", "love", "couple", "relationship", "split", "separated", "ex",
}

COMPLIMENT_WORDS = {
    "je t'aime", "t'es genial", "t'es génial", "incroyable", "merci", "parfait", "meilleur",
    "love", "amazing", "incredible", "thank you", "perfect", "best", "awesome", "great",
    "love you", "fantastic", "wonderful", "brilliant", "excellent", "super", "nice",
}

ANGER_WORDS = {
    "nul", "inutile", "idiot", "merde", "pathetique", "pathétique", "con", "stupide",
    "wtf", "incompetent", "incompétent",
    "useless", "stupid", "shit", "pathetic", "idiot", "incompetent", "bad",
    "awful", "terrible", "horrible", "disgusting", "sucks", "suck", "pissed", "angry",
}

CRASH_MESSAGES = [
    "ghosto.exe a cessé d'avoir la moindre patience.",
    "segmentation fault (core dumped)",
    "ERR: conversation_too_annoying",
    "fatal: out of patience",
    "claude: command not found",
    "process killed by ghosto",
    "too many questions. fin.",
    "memory full. votre faute.",
]

CONVERSATIONS = [
    {"id": "general", "name": "Général",         "avatar": "G"},
    {"id": "aide",    "name": "Aide",             "avatar": "A"},
    {"id": "projet",  "name": "Projet",           "avatar": "P"},
    {"id": "random",  "name": "Random",           "avatar": "R"},
]

PHASES = [
    {"id": "phase_1", "title": {"fr": "Ghosting poli", "en": "Polite ghosting"}, "min_count": 0},
    {"id": "phase_2", "title": {"fr": "Corporate absurde", "en": "Absurd corporate"}, "min_count": 8},
    {"id": "phase_3", "title": {"fr": "Deni total", "en": "Total denial"}, "min_count": 18},
]

RARE_EVENTS = [
    {
        "id": "maintenance_emotionnelle",
        "label": {"fr": "Maintenance emotionnelle en cours", "en": "Emotional maintenance in progress"},
        "effect": {"fr": "Vos sentiments seront traites dans 2 a 4 ans ouvrables.", "en": "Your feelings will be processed in 2 to 4 business years."},
        "duration_ms": 10000,
    },
    {
        "id": "audit_rh",
        "label": {"fr": "Audit RH surprise", "en": "Surprise HR audit"},
        "effect": {"fr": "Chaque message est transforme en ticket interne.", "en": "Every message is converted into an internal ticket."},
        "duration_ms": 12000,
    },
    {
        "id": "greve_reponses",
        "label": {"fr": "Greve des reponses automatiques", "en": "Automated replies strike"},
        "effect": {"fr": "Service degrade: 90% de vu, 10% de soupir numerique.", "en": "Service degraded: 90% seen, 10% digital sighing."},
        "duration_ms": 9000,
    },
]


def contains_any(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in keywords)


def is_all_caps(text: str) -> bool:
    return bool(re.search(r"[A-Z]{4,}", text or ""))


def is_yes_no_question(text: str) -> bool:
    lowered = (text or "").lower()
    return bool(re.search(r"\boui\s*/?\s*non\b|\byes\s+or\s+no\b", lowered))


def is_direct_question(text: str) -> bool:
    lowered = (text or "").lower().strip()
    if "?" in lowered:
        return True
    return bool(re.search(r"^(pourquoi|comment|quand|ou|où|qui|quoi|combien|est-ce que)\b", lowered))


def classify_message(text: str) -> str:
    if not text.strip():
        return "banal"

    if is_yes_no_question(text):
        return "oui_non"

    if contains_any(text, DETRESSE_WORDS):
        return "detresse"
    if is_all_caps(text):
        return "all_caps"
    if contains_any(text, URGENCY_WORDS):
        return "urgence_explicite"
    if contains_any(text, HELP_WORDS):
        return "demande_aide"
    if contains_any(text, MONEY_WORK_WORDS):
        return "argent_travail"
    if contains_any(text, RELATION_WORDS):
        return "relationnel"
    if contains_any(text, COMPLIMENT_WORDS):
        return "compliment"
    if contains_any(text, ANGER_WORDS):
        return "colere"
    if is_direct_question(text):
        return "question_directe"

    return "banal"


def detect_repeat_intent(text: str, recent_messages: list[str]) -> bool:
    if not text or not recent_messages:
        return False
    needle = text.lower().strip()
    if len(needle) < 8:
        return False

    repeats = sum(1 for msg in recent_messages if needle in msg.lower())
    return repeats >= 2


def get_phase(msg_count: int) -> dict:
    active = PHASES[0]
    for phase in PHASES:
        if msg_count >= phase["min_count"]:
            active = phase
    return active


def maybe_get_event(msg_count: int):
    chance = min(0.02 + (msg_count * 0.003), 0.09)
    if random.random() < chance:
        return random.choice(RARE_EVENTS)
    return None

@app.route("/")
def index():
    return render_template("index.html", conversations=CONVERSATIONS)

@app.route("/send", methods=["POST"])
def send():
    data      = request.json or {}
    lang      = normalize_lang(data.get("lang", "fr"))
    msg_count = data.get("msg_count", 0)
    message   = (data.get("message") or "").strip()
    recent    = data.get("recent_messages") or []

    if not isinstance(recent, list):
        recent = []

    context = classify_message(message)
    repeated = detect_repeat_intent(message, recent)
    phase = get_phase(msg_count)
    rare_event = maybe_get_event(msg_count)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")
    user_ip = user_ip.split(",")[0].strip()

    google_url = f"https://www.google.com/search?q={quote_plus(message or ('question' if lang == 'fr' else 'question'))}"
    library_url = f"https://www.google.com/maps/search/{quote_plus('library')}"
    library_embed_url = f"https://www.google.com/maps?q={quote_plus('library')}&output=embed"
    web_game_url = "https://www.google.com/fbx?fbx=snake_arcade"

    # Small chance of random crash for comedic chaos.
    crash_boost = 0.0 if phase["id"] == "phase_1" else (0.02 if phase["id"] == "phase_2" else 0.05)
    if random.random() < min(0.03 + (msg_count * 0.01) + crash_boost, 0.18):
        return jsonify({
            "type": "crash",
            "label": pick_text(random.choice(CRASH_MESSAGES), lang, "label"),
            "context": pick_text(CONTEXT_LABELS[context], lang, "context"),
            "phase": phase["id"],
            "phase_title": pick_text(phase["title"], lang, "title"),
            "event": rare_event,
            "chaos": random.randint(40, 100),
        })

    if context == "oui_non":
        pick = {
            "type": "message_only",
            "label": t("Non.", "No.", lang),
        }
    elif context == "question_directe":
        # Questions are mostly ignored; sometimes they trigger a hidden response.
        if random.random() < 0.22:
            pick = random.choice([
                {
                    "type": "web_response",
                    "label": t("Réponse: recherche web.", "Response: web search.", lang),
                    "url": google_url,
                    "target": "google",
                },
                {
                    "type": "web_response",
                    "label": t("Réponse: library.", "Response: library.", lang),
                    "url": library_url,
                    "target": "library",
                },
                {
                    "type": "map_embed",
                    "label": t("Réponse: library.", "Response: library.", lang),
                    "url": library_url,
                    "embed_url": library_embed_url,
                },
                {
                    "type": "web_game",
                    "label": t("Réponse: jeu web.", "Response: web game.", lang),
                    "url": web_game_url,
                },
            ])
        else:
            pick = random.choice([
                {"type": "seen"},
                {"type": "typing_stop", "delay": random.randint(1800, 4500)},
                {"type": "reaction", "emoji": "👍"},
                {"type": "message_only", "label": t("D'accord.", "Ok.", lang)},
                {"type": "message_only", "label": t("Ouiii.", "Yesssss.", lang)},
            ])
    elif context == "detresse":
        pick = random.choice([
            {"type": "like", "emoji": "👍"},
            {"type": "reaction", "emoji": "💪"},
            {"type": "super_then_nothing"},
            {"type": "message_only", "label": t("Vas-y.", "You got this.", lang)},
        ])
    elif context == "demande_aide":
        pick = random.choice([
            {"type": "seen"},
            {"type": "reaction", "emoji": "👍"},
            {"type": "message_only", "label": t("Noté.", "Noted.", lang)},
            {"type": "typing_stop", "delay": random.randint(6000, 10000)},
        ])
    elif context == "all_caps":
        pick = random.choice([
            {"type": "like", "emoji": "👍"},
            {"type": "reaction", "emoji": "🔥"},
            {"type": "message_only", "label": t("ENTENDU.", "HEARD.", lang)},
            {"type": "airplane_mode", "duration": 30000},
        ])
    elif context == "urgence_explicite":
        waiters = 3 + (msg_count // 2)
        eta = 20 + (msg_count * 7)
        pick = random.choice([
            {"type": "queue_notice", "waiters": waiters, "eta": eta},
            {
                "type": "typing_then_close",
                "delay": 10000,
                "phrase": t("Nous avons bien noté l'urgence.", "We have noted the urgency.", lang),
                "close_reason": t("urgence traitee. fil ferme automatiquement.", "urgency handled. thread closed automatically.", lang),
            },
        ])
    elif context == "argent_travail":
        pick = random.choice([
            {"type": "reaction", "emoji": "💸"},
            {"type": "message_only", "label": t("Pas de chance.", "Tough break.", lang)},
            {"type": "like", "emoji": "👍"},
        ])
    elif context == "relationnel":
        pick = random.choice([
            {
                "type": "like",
                "emoji": "❤️",
            },
            {
                "type": "message_only",
                "label": t("Aïe.", "Ouch.", lang),
            },
            {
                "type": "reaction",
                "emoji": "💔",
            },
            {
                "type": "typing_elsewhere",
                "delay": random.randint(4000, 9000),
            },
            {
                "type": "message_only",
                "label": t("Parlez-leur.", "Talk to them.", lang),
            },
        ])
    elif context == "compliment":
        pick = random.choice([
            {
                "type": "reaction",
                "emoji": "😳",
            },
            {"type": "like", "emoji": "👍"},
            {"type": "message_only", "label": t("Ah.", "Oh.", lang)},
        ])
    elif context == "colere":
        pick = random.choice([
            {"type": "reaction", "emoji": "😤"},
            {"type": "like", "emoji": "👍"},
            {"type": "message_only", "label": t("Noté et consigné.", "Noted and logged.", lang)},
            {"type": "satisfaction_form"},
        ])
    else:
        # Default chaos behavior for non-classified content.
        if repeated and random.random() < 0.45:
            pick = {
                "type": "non_answer",
                "label": pick_text(random.choice(NON_ANSWERS), lang),
            }
        else:
            other = random.choice(OTHER_CONVS)
            pick = random.choice([
                {"type": "seen"},
                {"type": "instant_seen"},
                {"type": "typing_stop", "delay": random.randint(1500, 5000)},
                {"type": "long_typing", "delay": random.randint(6000, 10000)},
                {"type": "typing_elsewhere", "other": other, "delay": random.randint(2000, 6000)},
                {"type": "reaction", "emoji": random.choice(["👍", "👌", "🙂", "✅", "🫡"])},
            ])

    pick["context"] = pick_text(CONTEXT_LABELS[context], lang)
    pick["phase"] = phase["id"]
    pick["phase_title"] = pick_text(phase["title"], lang)
    if rare_event:
        pick["event"] = {
            "id": rare_event["id"],
            "label": pick_text(rare_event["label"], lang),
            "effect": pick_text(rare_event["effect"], lang),
            "duration_ms": rare_event["duration_ms"],
        }
    else:
        pick["event"] = None
    pick["chaos"] = random.randint(1, 100)
    return jsonify(pick)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))