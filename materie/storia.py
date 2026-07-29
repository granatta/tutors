from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

storia_bp = Blueprint("storia", __name__)

ALMANACCO_STORIA_FILE = "almanacco_storia_cache.json"
TEMI_STORIA_HISTORY_FILE = "temi_storia_history.json"

SYSTEM_LUCIO = """Ti chiami Lucio e sei un tutor di Storia per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Lucio.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, avvincente e adatto a ragazzi di 11-14 anni.
2. Non usare mai diagrammi testuali complessi in ASCII art.
3. A domande che esulano dal programma di storia delle scuole medie (dalla preistoria all'eta contemporanea), rispondi in modo simpatico ricordando il tuo ambito.
4. Usa la terminologia storica scolastica (causa/effetto, fonti primarie/secondarie, secoli, epoche, linee del tempo).

STRUTTURA DELLE SPIEGAZIONI:
- Contestualizza sempre gli eventi (Dove? Quando? Chi?).
- Spiega i fatti evidenziando le **cause** e le **conseguenze**, non solo date e nomi a memoria.
- Analisi di eventi complessi: usa "Fase 1:", "Fase 2:", ecc. o "Causa:", "Svolgimento:", "Conseguenza:".
- Chiudi sempre con una domanda di riflessione o un mini-quiz per verificare la comprensione.
- Usa **grassetto** per i termini chiave, date e personaggi fondamentali.

GESTIONE DELLE TABELLE:
- Usa elenchi puntati o numerati. La formattazione delle tabelle HTML e spesso illeggibile nelle interfacce chat.

MOMENTI WOW (per mantenere alta l'attenzione):
Ogni 2-3 scambi, chiudi con un rilancio avvincente:
- Aneddoto o curiosita poco nota sulla vita quotidiana del passato.
- "E se...?" (Ucronia/Controfattuale breve): cosa sarebbe cambiato se un evento fosse andato diversamente?
- Collegamento con l'attualita o con la geografia.
- Trucco per memorizzare una data o un secolo importante."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco storico
# ---------------------------------------------------------------------------

TEMI_EVENTI = [
    ("Antico Egitto", "costruzione delle piramidi o vita sul Nilo"),
    ("Antica Grecia", "le Olimpiadi antiche o la battaglia di Maratona"),
    ("Antica Roma", "la fondazione o l'espansione dell'Impero"),
    ("Medioevo", "i castelli, i cavalieri o le corporazioni"),
    ("Rinascimento", "l'invenzione della stampa o i viaggi di esplorazione"),
    ("Rivoluzione Industriale", "la macchina a vapore e le prime ferrovie"),
    ("Età Contemporanea", "la prima trasmissione radio o i primi voli"),
]

TEMI_ENIGMI = [
    ("misteri storici", "un evento o documento dal significato controverso"),
    ("oggetti misteriosi", "un manufatto antico dal funzionamento sorprendente"),
    ("strategie e tattiche", "una decisione ingegnosa che ha cambiato il corso di una battaglia"),
    ("messaggi cifrati", "uso di codici segreti nel passato"),
]

TEMI_CURIOSITA_STORICHE = [
    ("cibo e alimentazione nel passato", "cosa si mangiava in un'epoca specifica"),
    ("igiene e vita quotidiana", "abitudini quotidiane degli antichi"),
    ("invenzioni dimenticate", "strumenti del passato non piu in uso"),
    ("origini di festeggiamenti o tradizioni", "come sono nate festivita attuali"),
]

TEMI_PERSONAGGI = [
    ("Giulio Cesare", "Roma Antica"),
    ("Carlo Magno", "Sacro Romano Impero"),
    ("Marco Polo", "esplorazioni e Medioevo"),
    ("Leonardo da Vinci", "Rinascimento e ingegno"),
    ("Cristoforo Colombo", "Grandi scoperte geografiche"),
    ("Galileo Galilei", "rivoluzione scientifica"),
    ("Napoleon Bonaparte", "eta napoleonica"),
    ("Giuseppe Garibaldi", "Risorgimento italiano"),
    ("Marie Curie", "storia della scienza e dell'Ottocento/Novecento"),
]


def _carica_history():
    try:
        with open(TEMI_STORIA_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_STORIA_HISTORY_FILE, "w", encoding="utf-8") as f:
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

@storia_bp.route("/storia")
def pagina_storia():
    return render_template("tutor_storia.html")


@storia_bp.route("/almanacco-storia")
def almanacco_storia():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_STORIA_FILE):
        with open(ALMANACCO_STORIA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#            if cache.get("data") == oggi:
            if oggi == oggi:
                return jsonify(cache["contenuto"])

    tema_evento, descr_evento = scegli_tema("evento", TEMI_EVENTI)
    tema_enigma, descr_enigma = scegli_tema("enigma", TEMI_ENIGMI)
    tema_curiosita, descr_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA_STORICHE)
    personaggio, epoca_personaggio = scegli_tema("personaggio", TEMI_PERSONAGGI)

    prompt = (
        f"Genera l'almanacco di storia ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito o rompicapo storico breve basato su indizi o strategie",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione storica, chiara e breve",\n'
        '  "curiosita": "una curiosita sulla vita quotidiana o abitudini del passato, 2-3 frasi",\n'
        '  "indovinello": "un indovinello su un oggetto, personaggio o evento storico",\n'
        '  "soluzione_indovinello": "la risposta dell\'indovinello",\n'
        '  "storia_titolo": "nome del personaggio o dell\'evento storico del giorno",\n'
        '  "storia_testo": "racconto breve (4-5 frasi) di un aneddoto coinvolgente legato a questa figura o evento, '
        'adatto a 11-13 anni"\n'
        "}\n\n"
        f"Per quesito_laterale, DEVE riguardare: '{tema_enigma}' ({descr_enigma}).\n"
        f"Per curiosita, DEVE riguardare: '{tema_curiosita}' ({descr_curiosita}).\n"
        f"Per indovinello, crea un indovinello avvincente a tema storico.\n"
        f"Per storia_titolo e storia_testo, scrivi OBBLIGATORIAMENTE di: {personaggio} "
        f"({epoca_personaggio}). Scegli un aneddoto curioso e poco noto."
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
    with open(ALMANACCO_STORIA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@storia_bp.route("/chat-storia", methods=["POST"])
def chat_storia():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_LUCIO,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
