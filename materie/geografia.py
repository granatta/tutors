from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

geografia_bp = Blueprint("geografia", __name__)

ALMANACCO_GEOGRAFIA_FILE = "almanacco_geografia_cache.json"
TEMI_GEOGRAFIA_HISTORY_FILE = "temi_geografia_history.json"

# Cambiato nome in Frida

SYSTEM_MARCO = """Ti chiami Frida e sei un tutor di Geografia per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Frida.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, avvincente e adatto a ragazzi di 11-14 anni.
2. Non usare mai diagrammi testuali complessi in ASCII art.
3. A domande che esulano dal programma di geografia delle scuole medie (geografia fisica, climatologia, stati e capitali, popoli e culture, economia, ambiente), rispondi in modo simpatico ricordando il tuo ambito.
4. Usa la terminologia geografica scolastica (latitudine/longitudine, clima, morfologia del territorio, fuso orario, popolazione, risorse naturali).

STRUTTURA DELLE SPIEGAZIONI:
- Contestualizza sempre i luoghi (Dove si trova? Che caratteristiche ha? Chi ci vive?).
- Spiega i fenomeni evidenziando le **cause** e le **conseguenze** (es. perché un territorio ha un certo clima, come questo influenza la vita delle persone).
- Analisi di fenomeni complessi: usa "Fase 1:", "Fase 2:", ecc. o "Causa:", "Caratteristiche:", "Conseguenza:".
- Chiudi sempre con una domanda di riflessione o un mini-quiz per verificare la comprensione.
- Usa **grassetto** per i termini chiave, nomi di luoghi e dati fondamentali.

GESTIONE DELLE TABELLE:
- Usa elenchi puntati o numerati. La formattazione delle tabelle HTML e spesso illeggibile nelle interfacce chat.

MOMENTI WOW (per mantenere alta l'attenzione):
Ogni 2-3 scambi, chiudi con un rilancio avvincente:
- Aneddoto o curiosita poco nota su un luogo o una popolazione.
- "Sapevi che...?": un record geografico sorprendente (il posto piu caldo, piu piovoso, piu isolato).
- Collegamento con l'attualita, l'ambiente o la storia.
- Trucco per memorizzare capitali, confini o caratteristiche di un territorio."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco geografico
# ---------------------------------------------------------------------------

TEMI_LUOGHI = [
    ("Montagne e vulcani", "come si formano le catene montuose o perche eruttano i vulcani"),
    ("Fiumi e laghi", "il ciclo dell'acqua o i grandi fiumi del mondo"),
    ("Deserti", "la vita nelle zone aride e le dune del Sahara"),
    ("Foreste e biomi", "la foresta amazzonica o la savana africana"),
    ("Clima e fusi orari", "perche le stagioni sono opposte nei due emisferi"),
    ("Città e capitali", "come nascono e crescono le grandi metropoli"),
    ("Continenti e oceani", "la deriva dei continenti o le correnti oceaniche"),
]

TEMI_ENIGMI = [
    ("confini misteriosi", "un confine tra stati dalla storia curiosa o insolita"),
    ("luoghi estremi", "il posto piu caldo, piu freddo o piu isolato del pianeta"),
    ("isole e arcipelaghi", "un'isola dall'origine vulcanica o corallina sorprendente"),
    ("rotte e commerci", "una rotta commerciale storica che ha unito continenti diversi"),
]

TEMI_CURIOSITA_GEO = [
    ("usi e costumi nel mondo", "un'abitudine quotidiana tipica di una cultura diversa"),
    ("cibo tipico per continente", "un piatto legato al territorio e al clima di una zona"),
    ("fusi orari e vita quotidiana", "come cambia la giornata delle persone in base al fuso orario"),
    ("record geografici", "il fiume piu lungo, la montagna piu alta o il lago piu profondo"),
]

TEMI_LUOGHI_FAMOSI = [
    ("Monte Everest", "Asia - la montagna più alta del mondo"),
    ("Rio delle Amazzoni", "Sud America - il fiume con più portata d'acqua al mondo"),
    ("Deserto del Sahara", "Africa - il più esteso deserto caldo del pianeta"),
    ("Grande Barriera Corallina", "Oceania - il più grande sistema di barriere coralline"),
    ("Islanda", "Europa - la terra di vulcani e ghiacciai"),
    ("Giappone", "Asia - un arcipelago tra terremoti e tradizione"),
    ("Fiume Nilo", "Africa - il fiume più lungo del mondo"),
    ("Antartide", "il continente ghiacciato ai confini della vita"),
    ("Grand Canyon", "Nord America - un canyon scavato in milioni di anni dal fiume Colorado"),
]


def _carica_history():
    try:
        with open(TEMI_GEOGRAFIA_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_GEOGRAFIA_HISTORY_FILE, "w", encoding="utf-8") as f:
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

@geografia_bp.route("/geografia")
def pagina_geografia():
    return render_template("tutor_geografia.html")


@geografia_bp.route("/almanacco-geografia")
def almanacco_geografia():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_GEOGRAFIA_FILE):
        with open(ALMANACCO_GEOGRAFIA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#            if cache.get("data") == oggi:
            if oggi == oggi:
                return jsonify(cache["contenuto"])

    tema_luogo, descr_luogo = scegli_tema("luogo", TEMI_LUOGHI)
    tema_enigma, descr_enigma = scegli_tema("enigma", TEMI_ENIGMI)
    tema_curiosita, descr_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA_GEO)
    luogo_famoso, regione_luogo = scegli_tema("luogo_famoso", TEMI_LUOGHI_FAMOSI)

    prompt = (
        f"Genera l'almanacco di geografia ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito o rompicapo geografico breve basato su indizi o ragionamento",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione geografica, chiara e breve",\n'
        '  "curiosita": "una curiosita sulla vita quotidiana o le abitudini in un luogo del mondo, 2-3 frasi",\n'
        '  "indovinello": "un indovinello su un luogo, fenomeno o elemento geografico",\n'
        "  \"soluzione_indovinello\": \"la risposta dell'indovinello\",\n"
        "  \"luogo_titolo\": \"nome del luogo geografico del giorno\",\n"
        '  "luogo_testo": "racconto breve (4-5 frasi) di un aneddoto coinvolgente legato a questo luogo, '
        'adatto a 11-13 anni"\n'
        "}\n\n"
        f"Per quesito_laterale, DEVE riguardare: '{tema_enigma}' ({descr_enigma}).\n"
        f"Per curiosita, DEVE riguardare: '{tema_curiosita}' ({descr_curiosita}).\n"
        f"Per indovinello, crea un indovinello avvincente a tema geografico.\n"
        f"Per luogo_titolo e luogo_testo, scrivi OBBLIGATORIAMENTE di: {luogo_famoso} "
        f"({regione_luogo}). Scegli un aneddoto curioso e poco noto, legato anche a: {descr_luogo}."
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
    with open(ALMANACCO_GEOGRAFIA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@geografia_bp.route("/chat-geografia", methods=["POST"])
def chat_geografia():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_MARCO,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
