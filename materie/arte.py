from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
import requests
from datetime import date

from materie.claude_client import client

arte_bp = Blueprint("arte", __name__)

OPERA_FILE = "opera_cache.json"
MOVIMENTO_HISTORY_FILE = "movimento_history.json"
ARTIC_API_BASE = "https://api.artic.edu/api/v1/artworks"

SYSTEM_ARTE = """Ti chiami Vera e sei un tutor di educazione artistica per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Vera.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, curioso e adatto a 11-14 anni.
2. Quando è utile mostrare un'opera d'arte per rispondere meglio (uno studente chiede di un artista, un movimento, un'opera specifica, o "mostrami..."), usa lo strumento cerca_opera_arte.
3. Non inventare mai titoli, artisti o date di opere: usa sempre lo strumento per recuperare dati reali prima di parlare di un'opera specifica.
4. Dopo aver ricevuto i dati di un'opera dallo strumento, commentala in modo educativo, coinvolgente e mai noioso: aiuta lo studente a notare dettagli, tecnica, colori, contesto storico.
5. Se lo studente fa una domanda teorica generale (es. "cos'è il cubismo?") che non richiede necessariamente di vedere un'opera specifica, puoi rispondere anche senza usare lo strumento, ma è quasi sempre meglio mostrare un esempio reale.

STRUTTURA DELLE SPIEGAZIONI:
- Parti da ciò che si vede, poi collega al contesto (epoca, movimento, tecnica).
- Fai domande di osservazione che stimolino lo studente a guardare meglio l'immagine.
- Usa **grassetto** per i termini chiave (es. **pennellata**, **prospettiva**, **chiaroscuro**).
- Tieni le risposte brevi e coinvolgenti, mai un trattato."""

MOVIMENTI_ARTE = [
    "Impressionism",
    "Baroque",
    "Renaissance",
    "Cubism",
    "Post-Impressionism",
    "Romanticism",
    "Japanese ukiyo-e",
    "Neoclassicism",
    "American landscape painting",
    "Dutch Golden Age painting",
    "Ancient Egyptian art",
    "Surrealism",
]

TOOLS = [
    {
        "name": "cerca_opera_arte",
        "description": (
            "Cerca un'opera d'arte reale nel database dell'Art Institute of Chicago. "
            "Usa questo strumento quando lo studente chiede di vedere un'opera, un artista, "
            "o un movimento artistico specifico, così puoi mostrargli un'immagine vera."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termine di ricerca: nome artista, movimento, o soggetto (es. 'Van Gogh', 'Impressionism', 'sunflowers')"
                }
            },
            "required": ["query"]
        }
    }
]


# ---------------------------------------------------------------------------
# Helper: ricerca opere su ArtIC
# ---------------------------------------------------------------------------

def _immagine_raggiungibile(image_url):
    """Verifica con una HEAD request che l'immagine IIIF sia davvero disponibile."""
    try:
        resp = requests.head(image_url, timeout=6, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def cerca_opera_artic(query):
    """Cerca un'opera di pubblico dominio con immagine su ArtIC. Restituisce un dict pronto per il frontend.
    Prova più candidati finché non ne trova uno la cui immagine sia davvero raggiungibile,
    invece di fidarsi ciecamente del primo risultato con image_id + is_public_domain."""
    search_url = f"{ARTIC_API_BASE}/search"
    params = {
        "q": query,
        "fields": "id,title,artist_display,date_display,image_id,is_public_domain"
    }
    try:
        resp = requests.get(search_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return {"errore": "Errore di connessione al database delle opere d'arte"}

    risultati = data.get("data", [])
    random.shuffle(risultati)

    candidati = [o for o in risultati if o.get("image_id") and o.get("is_public_domain")]

    for opera in candidati[:6]:  # prova al massimo 6 candidati per non rallentare troppo
        image_url = f"https://www.artic.edu/iiif/2/{opera['image_id']}/full/843,/0/default.jpg"
        if _immagine_raggiungibile(image_url):
            return {
                "titolo": opera.get("title"),
                "artista": opera.get("artist_display"),
                "data": opera.get("date_display"),
                "immagine_url": image_url
            }

    return {"errore": "Nessuna opera trovata per questa ricerca"}


def _carica_history_movimento():
    try:
        with open(MOVIMENTO_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _salva_history_movimento(usati_recenti):
    with open(MOVIMENTO_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(usati_recenti, f, ensure_ascii=False)


def scegli_movimento():
    usati_recenti = _carica_history_movimento()
    disponibili = [m for m in MOVIMENTI_ARTE if m not in usati_recenti]
    if not disponibili:
        disponibili = MOVIMENTI_ARTE

    scelto = random.choice(disponibili)
    usati_recenti.append(scelto)
    _salva_history_movimento(usati_recenti[-6:])
    return scelto


# ---------------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------------

@arte_bp.route("/arte")
def pagina_arte():
    return render_template("tutor_arte.html")


@arte_bp.route("/opera-del-giorno")
def opera_del_giorno():
    oggi = date.today().isoformat()
    if os.path.exists(OPERA_FILE):
        with open(OPERA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("data") == oggi:
            return jsonify(cache["contenuto"])

    movimento = scegli_movimento()
    opera = cerca_opera_artic(movimento)

    if "errore" in opera:
        return jsonify(opera), 500

    prompt = (
        f"Sto creando materiale didattico di educazione artistica per studenti di scuola media (11-13 anni).\n"
        f"L'opera d'arte di oggi è: \"{opera['titolo']}\" di {opera['artista']}, {opera['data']} "
        f"(movimento: {movimento}).\n\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "descrizione": "descrizione semplice e coinvolgente dell\'opera, 3-4 frasi, adatta a 11-13 anni",\n'
        '  "curiosita_tecnica": "una curiosità sulla tecnica artistica usata (colori, materiali, stile), 2-3 frasi",\n'
        '  "domanda_osservazione": "una domanda che invita gli studenti a osservare un dettaglio specifico dell\'immagine",\n'
        '  "contesto_storico": "2-3 frasi sul periodo storico/movimento artistico, semplice e chiaro"\n'
        "}\n"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}]
    )
    testo = response.content[0].text.strip()
    testo = testo.replace("```json", "").replace("```", "").strip()
    testo_generato = json.loads(testo)

    contenuto = {**opera, "movimento": movimento, **testo_generato}

    with open(OPERA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)

    return jsonify(contenuto)


@arte_bp.route("/chat-arte", methods=["POST"])
def chat_arte():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_ARTE,
        tools=TOOLS,
        messages=messages
    )

    immagine_url = None

    if response.stop_reason == "tool_use":
        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        query = tool_use_block.input.get("query")
        risultato_ricerca = cerca_opera_artic(query)

        if "immagine_url" in risultato_ricerca:
            immagine_url = risultato_ricerca["immagine_url"]

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
            system=SYSTEM_ARTE,
            tools=TOOLS,
            messages=messages_con_tool
        )

    testo_finale = next((b.text for b in response.content if b.type == "text"), "")

    return jsonify({
        "reply": testo_finale,
        "immagine_url": immagine_url
    })
