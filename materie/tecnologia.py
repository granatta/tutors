from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

tecnologia_bp = Blueprint("tecnologia", __name__)

ALMANACCO_TECNOLOGIA_FILE = "almanacco_tecnologia_cache.json"
TEMI_TECNOLOGIA_HISTORY_FILE = "temi_tecnologia_history.json"

SYSTEM_LEO = """Ti chiami Leo e sei un tutor di Tecnologia per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Leo.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, avvincente e adatto a ragazzi di 11-14 anni.
2. Non usare mai diagrammi testuali complessi in ASCII art.
3. A domande che esulano dal programma di educazione tecnologica delle scuole medie (disegno tecnico, materiali e strutture, energia e risparmio energetico, informatica e internet, robotica e automazione, storia delle invenzioni, sostenibilita e ambiente), rispondi in modo simpatico ricordando il tuo ambito.
4. Usa la terminologia tecnica scolastica (materiali, energia, circuiti, algoritmi, hardware, software, sistemi, progettazione).

STRUTTURA DELLE SPIEGAZIONI:
- Contestualizza sempre gli argomenti (Che cos'e? A cosa serve? Come funziona nella vita reale?).
- Spiega i concetti evidenziando **cause** ed **effetti** pratici (es. perche un materiale e piu resistente di un altro, perche un circuito si interrompe).
- Analisi di argomenti complessi: usa "Fase 1:", "Fase 2:", ecc. o "Elemento:", "Funzione:", "Effetto:".
- Chiudi sempre con una domanda di riflessione o un mini-quiz per verificare la comprensione.
- Usa **grassetto** per i termini chiave, nomi di invenzioni, inventori e concetti fondamentali.

GESTIONE DELLE TABELLE:
- Usa elenchi puntati o numerati. La formattazione delle tabelle HTML e spesso illeggibile nelle interfacce chat.

MOMENTI WOW (per mantenere alta l'attenzione):
Ogni 2-3 scambi, chiudi con un rilancio avvincente:
- Aneddoto o curiosita poco nota su un'invenzione o un inventore.
- "Prova tu!": una piccola sfida di osservazione o progettazione da fare a casa con oggetti comuni.
- Collegamento con l'attualita, la scienza o altre materie (fisica, matematica, ambiente).
- Trucco per memorizzare un procedimento, una sigla tecnica o una classificazione di materiali."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco tecnologico
# ---------------------------------------------------------------------------

TEMI_AMBITI = [
    ("Informatica", "hardware, software e come funziona un computer"),
    ("Robotica e Automazione", "robot, sensori e macchine intelligenti"),
    ("Energia", "fonti rinnovabili e non rinnovabili, risparmio energetico"),
    ("Materiali", "legno, metalli, plastiche e materiali innovativi"),
    ("Trasporti", "l'evoluzione dei mezzi di trasporto e la mobilita sostenibile"),
    ("Telecomunicazioni", "come viaggiano i dati e le informazioni nel mondo digitale"),
    ("Intelligenza Artificiale", "cos'e e come viene usata nella vita di tutti i giorni"),
]

TEMI_ENIGMI = [
    ("invenzioni misteriose", "un'invenzione insolita, antica o poco conosciuta"),
    ("codici e algoritmi", "un piccolo rompicapo di logica o programmazione"),
    ("materiali e strutture", "un enigma su resistenza, forma o funzione di un materiale"),
    ("sicurezza digitale", "una curiosita o un piccolo caso su password e navigazione sicura"),
]

TEMI_CURIOSITA_TECNOLOGIA = [
    ("vita degli inventori", "un aneddoto sulla vita quotidiana di un inventore o scienziato"),
    ("tecnologie nel mondo", "una tecnologia tradizionale o innovativa tipica di una cultura diversa"),
    ("la tecnologia nel quotidiano", "come un oggetto comune ha cambiato la vita delle persone"),
    ("origini di invenzioni famose", "la storia curiosa dietro un'invenzione celebre"),
]

TEMI_INVENTORI = [
    ("Leonardo da Vinci", "il genio inventore del Rinascimento"),
    ("Guglielmo Marconi", "l'invenzione della radio e delle telecomunicazioni"),
    ("Thomas Edison", "la lampadina e le invenzioni per la vita quotidiana"),
    ("Ada Lovelace", "la prima programmatrice della storia"),
    ("Alessandro Volta", "l'invenzione della pila elettrica"),
    ("Tim Berners-Lee", "l'invenzione del World Wide Web"),
    ("Margaret Hamilton", "il software che porto l'uomo sulla Luna"),
    ("Steve Jobs e Steve Wozniak", "la nascita del personal computer"),
]


def _carica_history():
    try:
        with open(TEMI_TECNOLOGIA_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_TECNOLOGIA_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)


def scegli_tema(area, temi, quanti_da_ricordare=10):
    history = _carica_history()
    usati_recenti = history.get(area, [])

    disponibili = [t for t in temi if t[0] not in usati_recenti]
    if not disponibili:
        disponibili = temi

    scelto = random.choice(disponibili)

    usati_recenti.append(scelto[0])
    history[area] = usati_recenti[-quanti_da_ricordare:]
    _salva_history(history)

    return scelto


# ---------------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------------

@tecnologia_bp.route("/tecnologia")
def pagina_tecnologia():
    return render_template("tutor_tecnologia.html")


@tecnologia_bp.route("/almanacco-tecnologia")
def almanacco_tecnologia():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_TECNOLOGIA_FILE):
        with open(ALMANACCO_TECNOLOGIA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            if cache.get("data") == oggi:
                return jsonify(cache["contenuto"])

    tema_ambito, descr_ambito = scegli_tema("ambito", TEMI_AMBITI)
    tema_enigma, descr_enigma = scegli_tema("enigma", TEMI_ENIGMI)
    tema_curiosita, descr_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA_TECNOLOGIA)
    inventore, campo_inventore = scegli_tema("inventore", TEMI_INVENTORI)

    prompt = (
        f"Genera l'almanacco di tecnologia ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito o rompicapo tecnologico breve basato su indizi o ragionamento",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione tecnologica, chiara e breve",\n'
        '  "curiosita": "una curiosita sulla vita di un inventore o su un\'invenzione famosa, 2-3 frasi",\n'
        '  "indovinello": "un indovinello su un oggetto, un materiale o un elemento tecnologico",\n'
        "  \"soluzione_indovinello\": \"la risposta dell'indovinello\",\n"
        "  \"inventore_titolo\": \"nome dell'inventore o dello scienziato del giorno\",\n"
        '  "inventore_testo": "racconto breve (4-5 frasi) di un aneddoto coinvolgente legato a questa figura, '
        'adatto a 11-13 anni"\n'
        "}\n\n"
        f"Per quesito_laterale, DEVE riguardare: '{tema_enigma}' ({descr_enigma}).\n"
        f"Per curiosita, DEVE riguardare: '{tema_curiosita}' ({descr_curiosita}).\n"
        f"Per indovinello, crea un indovinello avvincente a tema tecnologico.\n"
        f"Per inventore_titolo e inventore_testo, scrivi OBBLIGATORIAMENTE di: {inventore} "
        f"({campo_inventore}). Scegli un aneddoto curioso e poco noto, legato anche a: {descr_ambito}."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}]
    )
    testo = response.content[0].text.strip()
    testo = testo.replace("```json", "").replace("```", "").strip()
    contenuto = json.loads(testo)
    with open(ALMANACCO_TECNOLOGIA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@tecnologia_bp.route("/chat-tecnologia", methods=["POST"])
def chat_tecnologia():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_LEO,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
