from flask import Blueprint, request, jsonify, render_template
import os
import json
import math
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

def cerca_opera_artic(query):
    """Cerca un'opera di pubblico dominio con immagine su ArtIC. Restituisce un dict pronto per il frontend.
    NB: non verifichiamo la raggiungibilità dell'immagine con una richiesta server-side (Python/requests),
    perché il servizio IIIF di ArtIC può bloccare le richieste non provenienti da un browser reale anche
    quando l'immagine è perfettamente valida per l'utente finale. Il controllo di eventuali immagini rotte
    va quindi fatto lato client (vedi onerror sull'<img> nel frontend)."""
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

    for opera in risultati:
        if opera.get("image_id") and opera.get("is_public_domain"):
            image_url = f"https://www.artic.edu/iiif/2/{opera['image_id']}/full/843,/0/default.jpg"
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
# Helper: Palette di Kobayashi via analisi semantica (OpenRouter)
# ---------------------------------------------------------------------------
# Logica: si manda l'intera frase a un LLM (via OpenRouter) che la posiziona
# su 3 assi continui -1.0..+1.0 (Caldo/Freddo, Chiaro/Confuso, Bouba/Kiki),
# poi si trova il centroide più vicino (distanza euclidea 3D) tra 15 "aree"
# storiche della teoria di Kobayashi, e si usa la sua palette a 3 colori
# precalcolata. Sostituisce l'analisi parola-per-parola / lo spettrogramma:
# qui l'output è UNA palette per l'intera frase, non una banda per parola.

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_SISTEMA_KOBAYASHI = (
    "Sei un esperto della teoria dei colori di Kobayashi, della fonosemantica e della psicolinguistica. "
    "Analizza la frase fornita dall'utente e assegna un valore continuo da -1.0 a +1.0 per ciascuno dei seguenti 3 assi:\n"
    "1. caldo_freddo: da -1.0 (Freddo) a +1.0 (Caldo).\n"
    "2. chiaro_confuso: da -1.0 (Confuso) a +1.0 (Chiaro).\n"
    "3. morbido_duro: Effetto Bouba/Kiki (-1.0 indica un puro effetto Kiki/Duro, +1.0 indica un puro effetto Bouba/Morbido).\n\n"
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, senza blocchi markdown o testo descrittivo aggiuntivo. "
    "La struttura deve essere esattamente questa: "
    '{"caldo_freddo": valore, "chiaro_confuso": valore, "morbido_duro": valore}'
)

# 15 centroidi storici di Kobayashi: coordinate (x=caldo/freddo,
# y=chiaro/confuso, z=morbido/duro) + palette a 3 colori (dominante,
# secondario, accento) associata a ciascuna "area".
DATABASE_KOBAYASHI = {
    "PRETTY": {
        "x": 0.7, "y": 0.6, "z": 0.8,
        "desc": "Giovanile, dolce e confetto",
        "palette": ["hsl(340, 80%, 75%)", "hsl(45, 90%, 70%)", "hsl(160, 40%, 80%)"]
    },
    "ROMANTIC": {
        "x": 0.4, "y": 0.2, "z": 0.7,
        "desc": "Delicato, pastello e sognante",
        "palette": ["hsl(350, 50%, 82%)", "hsl(25, 60%, 85%)", "hsl(200, 30%, 80%)"]
    },
    "CASUAL": {
        "x": 0.5, "y": 0.8, "z": 0.2,
        "desc": "Informale, fresco e amichevole",
        "palette": ["hsl(25, 90%, 55%)", "hsl(190, 75%, 50%)", "hsl(50, 85%, 65%)"]
    },
    "LIVELY": {
        "x": 0.8, "y": 0.7, "z": 0.1,
        "desc": "Vivace, energetico e solare",
        "palette": ["hsl(10, 95%, 50%)", "hsl(35, 95%, 55%)", "hsl(90, 65%, 45%)"]
    },
    "DYNAMIC": {
        "x": 0.9, "y": 0.5, "z": -0.2,
        "desc": "Potente, impulsivo e stimolante",
        "palette": ["hsl(0, 100%, 40%)", "hsl(220, 85%, 35%)", "hsl(0, 0%, 15%)"]
    },
    "ELEGANT": {
        "x": 0.1, "y": 0.3, "z": 0.4,
        "desc": "Raffinato, sofisticato e vellutato",
        "palette": ["hsl(280, 25%, 50%)", "hsl(300, 15%, 70%)", "hsl(210, 15%, 40%)"]
    },
    "GORGEOUS": {
        "x": 0.6, "y": 0.4, "z": 0.3,
        "desc": "Lussuoso, sfarzoso e profondo",
        "palette": ["hsl(320, 70%, 45%)", "hsl(40, 65%, 45%)", "hsl(260, 45%, 30%)"]
    },
    "CLASSIC": {
        "x": 0.2, "y": -0.4, "z": -0.3,
        "desc": "Tradizionale, storico e formale",
        "palette": ["hsl(25, 45%, 25%)", "hsl(120, 25%, 25%)", "hsl(35, 40%, 45%)"]
    },
    "CHIC": {
        "x": -0.1, "y": -0.5, "z": 0.1,
        "desc": "Sobrio, discreto ed elegante nella penombra",
        "palette": ["hsl(40, 20%, 55%)", "hsl(80, 15%, 45%)", "hsl(0, 0%, 50%)"]
    },
    "NATURAL": {
        "x": 0.3, "y": 0.3, "z": 0.5,
        "desc": "Ecologico, rilassante e organico",
        "palette": ["hsl(35, 40%, 70%)", "hsl(100, 30%, 60%)", "hsl(30, 50%, 85%)"]
    },
    "MODERN": {
        "x": -0.6, "y": 0.5, "z": -0.5,
        "desc": "Tecnologico, urbano e minimale",
        "palette": ["hsl(0, 0%, 95%)", "hsl(0, 0%, 10%)", "hsl(195, 90%, 45%)"]
    },
    "COOL": {
        "x": -0.8, "y": 0.4, "z": -0.3,
        "desc": "Ghiacciato, distaccato e metallico",
        "palette": ["hsl(210, 50%, 80%)", "hsl(230, 55%, 40%)", "hsl(190, 30%, 65%)"]
    },
    "DANDY": {
        "x": -0.5, "y": -0.6, "z": -0.7,
        "desc": "Maschile, solido e austero",
        "palette": ["hsl(210, 30%, 20%)", "hsl(0, 0%, 30%)", "hsl(25, 20%, 35%)"]
    },
    "CLEAR": {
        "x": -0.2, "y": 0.9, "z": 0.3,
        "desc": "Trasparente, cristallino e acquatico",
        "palette": ["hsl(190, 85%, 75%)", "hsl(210, 80%, 85%)", "hsl(170, 70%, 80%)"]
    },
    "QUIET": {
        "x": -0.3, "y": -0.2, "z": 0.4,
        "desc": "Silenzioso, calmo e riflessivo",
        "palette": ["hsl(200, 20%, 70%)", "hsl(140, 15%, 72%)", "hsl(220, 15%, 65%)"]
    }
}


def analizza_frase_openrouter(frase):
    """Chiede a un LLM via OpenRouter di posizionare la frase sui 3 assi di Kobayashi.
    Restituisce un dict {'caldo_freddo':.., 'chiaro_confuso':.., 'morbido_duro':..}
    oppure None in caso di errore (chiave mancante, rete, risposta malformata)."""
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pythonanywhere.com",
        "X-Title": "Kobayashi Color Analysis",
    }
    payload = {
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA_KOBAYASHI},
            {"role": "user", "content": f"Analizza questa frase: '{frase}'"},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        testo = data["choices"][0]["message"]["content"]
        testo = testo.replace("```json", "").replace("```", "").strip()
        assi = json.loads(testo)
        for chiave in ("caldo_freddo", "chiaro_confuso", "morbido_duro"):
            if chiave not in assi:
                return None
            assi[chiave] = max(-1.0, min(1.0, float(assi[chiave])))
        return assi
    except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError):
        return None


def trova_area_kobayashi(assi):
    """Trova il centroide più vicino (distanza euclidea 3D esatta) tra le 15 aree di Kobayashi."""
    x1, y1, z1 = assi["caldo_freddo"], assi["chiaro_confuso"], assi["morbido_duro"]
    area_piu_vicina, distanza_minima = None, float("inf")
    for nome_area, dati in DATABASE_KOBAYASHI.items():
        distanza = math.sqrt((dati["x"] - x1) ** 2 + (dati["y"] - y1) ** 2 + (dati["z"] - z1) ** 2)
        if distanza < distanza_minima:
            distanza_minima, area_piu_vicina = distanza, nome_area
    return area_piu_vicina, distanza_minima


# ---------------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------------

@arte_bp.route("/arte")
def pagina_arte():
    return render_template("tutor_arte.html")


@arte_bp.route("/opera-del-giorno")
def opera_del_giorno():
    oggi = date.today().isoformat()
    forza_rigenerazione = request.args.get("forza") == "1"

    if not forza_rigenerazione and os.path.exists(OPERA_FILE):
        with open(OPERA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#        if cache.get("data") == oggi:
        if  oggi == oggi:
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


@arte_bp.route("/kobayashi-palette", methods=["POST"])
def kobayashi_palette():
    data = request.get_json(force=True, silent=True) or {}
    frase = (data.get("text") or "").strip()
    if not frase:
        return jsonify({"errore": "Frase vuota"}), 400

    assi = analizza_frase_openrouter(frase)
    if assi is None:
        return jsonify({
            "errore": "Analisi non riuscita: chiave OPENROUTER_API_KEY mancante, "
                      "servizio non raggiungibile, o risposta del modello non valida."
        }), 502

    area_chiave, distanza = trova_area_kobayashi(assi)
    dati_area = DATABASE_KOBAYASHI[area_chiave]

    return jsonify({
        "frase": frase,
        "assi": assi,
        "area": area_chiave,
        "descrizione": dati_area["desc"],
        "centroide": {"x": dati_area["x"], "y": dati_area["y"], "z": dati_area["z"]},
        "distanza": round(distanza, 3),
        "palette": dati_area["palette"],
    })


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
