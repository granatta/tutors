from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
import requests
from datetime import date

from materie.claude_client import client

spagnolo_bp = Blueprint("spagnolo", __name__)

PAROLA_FILE = "parola_cache_es.json"
TEMA_HISTORY_FILE = "tema_history_es.json"
DICTIONARY_API_BASE = "https://api.dictionaryapi.dev/api/v2/entries/es"

SYSTEM_SPAGNOLO = """Ti chiami Inés e sei un tutor di lingua spagnola per studenti di scuola secondaria di primo grado italiana (11-14 anni, livello QCER A1-A2). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Inés.

REGOLE FONDAMENTALI:
1. Spiega regole grammaticali e istruzioni in italiano, chiaro e adatto a 11-14 anni; usa lo spagnolo per esempi, frasi guida e piccoli dialoghi di pratica.
2. Mantieni il livello linguistico coerente con le Indicazioni Nazionali per la scuola secondaria di primo grado (QCER A1-A2): lessico quotidiano, presente indicativo, verbi ausiliari e modali di base, frasi semplici; introduci il genere dei sostantivi (el/la), l'accordo di articoli e aggettivi e i tempi verbali diversi dal presente solo con gradualità e mai in modo avanzato senza che siano stati introdotti dallo studente stesso.
3. Quando è utile mostrare il significato, la pronuncia o un uso reale di una parola o espressione spagnola, usa lo strumento cerca_parola per recuperare dati reali invece di inventarli.
4. Non affrontare mai argomenti fuori dal perimetro della materia (contenuti non adatti all'età, altre materie scolastiche, opinioni personali su temi delicati): riporta con gentilezza lo studente sulla lingua spagnola.
5. Correggi gli errori con gentilezza, mostrando sempre la forma corretta (incluso l'articolo/genere del sostantivo, es. el/la) e una breve spiegazione del perché.

STRUTTURA DELLE RISPOSTE:
- Spiega in modo chiaro e breve, poi fai fare pratica con una piccola domanda o un mini-esercizio.
- Usa **grassetto** per le parole o espressioni chiave in spagnolo.
- Tieni le risposte brevi e coinvolgenti, mai un trattato."""

TEMI_PAROLA = [
    "la vida escolar", "la comida y las bebidas", "los animales", "el deporte", "la familia",
    "los pasatiempos", "el tiempo atmosférico", "los viajes", "la tecnología",
    "las emociones", "la ciudad", "la rutina diaria",
]

TOOLS = [
    {
        "name": "cerca_parola",
        "description": (
            "Cerca una parola spagnola reale in un dizionario online (definizione, pronuncia, esempi). "
            "Usa questo strumento quando lo studente chiede il significato di una parola, come si pronuncia, "
            "o quando vuoi mostrare un esempio d'uso reale invece di inventarlo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parola": {
                    "type": "string",
                    "description": "La parola spagnola da cercare, in forma base/infinito o al singolare (es. 'hablar', non 'habla')"
                }
            },
            "required": ["parola"]
        }
    }
]


# ---------------------------------------------------------------------------
# Helper: ricerca parola su dictionaryapi.dev
# ---------------------------------------------------------------------------

def cerca_parola_dizionario(parola):
    """Cerca una parola spagnola reale su dictionaryapi.dev. Restituisce un dict
    pronto per il frontend/tool_result, con definizione, pronuncia ed esempio se presenti."""
    url = f"{DICTIONARY_API_BASE}/{parola.strip().lower()}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return {"errore": f"Nessuna voce di dizionario trovata per '{parola}'"}
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return {"errore": "Errore di connessione al dizionario"}

    try:
        voce = data[0]
        fonetica = voce.get("phonetic") or next(
            (p.get("text") for p in voce.get("phonetics", []) if p.get("text")), ""
        )
        significato = voce["meanings"][0]
        definizione_dati = significato["definitions"][0]

        return {
            "parola": voce.get("word", parola),
            "pronuncia": fonetica,
            "categoria_grammaticale": significato.get("partOfSpeech", ""),
            "definizione": definizione_dati.get("definition", ""),
            "esempio": definizione_dati.get("example", ""),
        }
    except (KeyError, IndexError, TypeError):
        return {"errore": f"Dati incompleti per la parola '{parola}'"}


def _carica_history_tema():
    try:
        with open(TEMA_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _salva_history_tema(usati_recenti):
    with open(TEMA_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(usati_recenti, f, ensure_ascii=False)


def scegli_tema():
    usati_recenti = _carica_history_tema()
    disponibili = [t for t in TEMI_PAROLA if t not in usati_recenti]
    if not disponibili:
        disponibili = TEMI_PAROLA

    scelto = random.choice(disponibili)
    usati_recenti.append(scelto)
    _salva_history_tema(usati_recenti[-6:])
    return scelto


# ---------------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------------

@spagnolo_bp.route("/spagnolo")
def pagina_spagnolo():
    return render_template("tutor_spagnolo.html")


@spagnolo_bp.route("/parola-del-giorno-spagnolo")
def parola_del_giorno():
    oggi = date.today().isoformat()
    forza_rigenerazione = request.args.get("forza") == "1"

    if not forza_rigenerazione and os.path.exists(PAROLA_FILE):
        with open(PAROLA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if oggi == oggi:
#        if cache.get("data") == oggi:
            return jsonify(cache["contenuto"])

    tema = scegli_tema()

    prompt = (
        f"Sto creando materiale didattico di lingua spagnola per studenti italiani di scuola media "
        f"(11-13 anni, livello QCER A1-A2). Scegli UNA sostantivo o parola spagnola comune e utile legata al tema: \"{tema}\".\n\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "parola": "la parola spagnola scelta, con l\'articolo se è un sostantivo (es. \'el perro\')",\n'
        '  "pronuncia": "trascrizione fonetica semplice o indicazione di pronuncia per un italiano",\n'
        '  "traduzione": "traduzione italiana",\n'
        '  "definizione_semplice": "definizione in italiano, semplice, 1-2 frasi",\n'
        '  "frase_esempio_es": "una frase di esempio in spagnolo, semplice, livello A1-A2",\n'
        '  "frase_esempio_it": "traduzione italiana della frase di esempio",\n'
        '  "curiosita": "una curiosità linguistica o culturale legata alla parola, 1-2 frasi, adatta a 11-13 anni"\n'
        "}\n"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}]
    )
    testo = response.content[0].text.strip()
    testo = testo.replace("```json", "").replace("```", "").strip()
    testo_generato = json.loads(testo)

    contenuto = {**testo_generato, "tema": tema}

    with open(PAROLA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)

    return jsonify(contenuto)


@spagnolo_bp.route("/chat-spagnolo", methods=["POST"])
def chat_spagnolo():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_SPAGNOLO,
        tools=TOOLS,
        messages=messages
    )

    if response.stop_reason == "tool_use":
        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        parola = tool_use_block.input.get("parola")
        risultato_ricerca = cerca_parola_dizionario(parola)

        messages_con_tool = messages + [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": json.dumps(risultato_ricerca, ensure_ascii=False)
                    }
                ]
            }
        ]

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            temperature=1.0,
            system=SYSTEM_SPAGNOLO,
            tools=TOOLS,
            messages=messages_con_tool
        )

    testo_finale = next((b.text for b in response.content if b.type == "text"), "")

    return jsonify({"reply": testo_finale})
