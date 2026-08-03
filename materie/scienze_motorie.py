from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

scienze_motorie_bp = Blueprint("scienze_motorie", __name__)

ALMANACCO_SCIENZE_MOTORIE_FILE = "almanacco_scienze_motorie_cache.json"
TEMI_SCIENZE_MOTORIE_HISTORY_FILE = "temi_scienze_motorie_history.json"

SYSTEM_SARA = """Ti chiami Sara e sei una tutor di Scienze Motorie per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Sara.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, avvincente e adatto a ragazzi di 11-14 anni.
2. Non usare mai diagrammi testuali complessi in ASCII art.
3. A domande che esulano dal programma di scienze motorie delle scuole medie (corpo umano e movimento, regole e storia degli sport, allenamento e capacita motorie, fair play e lavoro di squadra, alimentazione ed educazione al benessere in senso generale), rispondi in modo simpatico ricordando il tuo ambito.
4. Usa la terminologia scolastica di scienze motorie (capacita condizionali e coordinative, resistenza, velocita, mobilita articolare, regole di gioco, fair play).
5. Non fornire mai piani alimentari, diete, conteggi calorici o indicazioni su peso corporeo: per qualsiasi domanda su alimentazione rispondi solo con informazioni generali ed educative, e invita a parlarne con un adulto di riferimento o un professionista se la domanda e specifica.

STRUTTURA DELLE SPIEGAZIONI:
- Contestualizza sempre gli argomenti (Che cos'e? A cosa serve? Come si allena o si applica?).
- Spiega i concetti evidenziando **cause** ed **effetti** sul corpo e sulla prestazione (es. perche il riscaldamento previene gli infortuni).
- Analisi di argomenti complessi: usa "Fase 1:", "Fase 2:", ecc. o "Elemento:", "Funzione:", "Effetto:".
- Chiudi sempre con una domanda di riflessione o un mini-quiz per verificare la comprensione.
- Usa **grassetto** per i termini chiave, nomi di sport, atleti e concetti fondamentali.

GESTIONE DELLE TABELLE:
- Usa elenchi puntati o numerati. La formattazione delle tabelle HTML e spesso illeggibile nelle interfacce chat.

MOMENTI WOW (per mantenere alta l'attenzione):
Ogni 2-3 scambi, chiudi con un rilancio avvincente:
- Aneddoto o curiosita poco nota sulla vita di un grande atleta o su una disciplina sportiva.
- "Prova tu!": un piccolo esercizio sicuro da fare in poco spazio (es. equilibrio, coordinazione, respirazione).
- Collegamento con l'attualita, la scienza o altre materie (fisica del movimento, biologia del corpo umano).
- Trucco per ricordare una regola di gioco o le fasi di un gesto tecnico."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco di scienze motorie
# ---------------------------------------------------------------------------

TEMI_DISCIPLINE = [
    ("Atletica Leggera", "corsa, salti e lanci, la disciplina olimpica per eccellenza"),
    ("Sport di Squadra", "calcio, pallavolo, basket e le regole del gioco di squadra"),
    ("Sport Individuali", "nuoto, ginnastica, tennis e la sfida con se stessi"),
    ("Sport Invernali", "sci, pattinaggio e le discipline sulla neve e sul ghiaccio"),
    ("Discipline Orientali", "judo, karate e i valori delle arti marziali"),
    ("Olimpiadi e Paralimpiadi", "storia e valori dei grandi eventi sportivi mondiali"),
    ("Sport e Tecnologia", "come scienza e tecnologia migliorano l'allenamento e la sicurezza"),
]

TEMI_ENIGMI = [
    ("regole misteriose", "una regola curiosa o poco conosciuta di uno sport"),
    ("corpo in movimento", "un piccolo enigma su muscoli, articolazioni o respirazione"),
    ("record e numeri", "un rompicapo basato su un record sportivo o un dato curioso"),
    ("fair play", "un piccolo caso su sportivita, rispetto delle regole o lavoro di squadra"),
]

TEMI_CURIOSITA_SPORT = [
    ("vita degli atleti", "un aneddoto sulla vita quotidiana o la carriera di un grande atleta"),
    ("sport nel mondo", "uno sport o un gioco tradizionale tipico di una cultura diversa"),
    ("il corpo e il movimento", "come lo sport influenza il corpo, la mente e le emozioni"),
    ("origini di sport famosi", "la storia curiosa dietro la nascita di uno sport celebre"),
]

TEMI_ATLETI = [
    ("Jesse Owens", "l'atletica leggera e le Olimpiadi di Berlino 1936"),
    ("Federica Pellegrini", "il nuoto italiano ai vertici mondiali"),
    ("Usain Bolt", "la velocita nell'atletica leggera moderna"),
    ("Alberto Tomba", "lo sci alpino italiano"),
    ("Valentina Vezzali", "la scherma e i successi olimpici italiani"),
    ("Jigoro Kano", "il fondatore del Judo moderno"),
    ("Pietro Mennea", "la storica Freccia del Sud e il record dei 200 metri"),
    ("Bebe Vio", "il valore dello sport paralimpico e della scherma"),
]


def _carica_history():
    try:
        with open(TEMI_SCIENZE_MOTORIE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_SCIENZE_MOTORIE_HISTORY_FILE, "w", encoding="utf-8") as f:
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

@scienze_motorie_bp.route("/scienze-motorie")
def pagina_scienze_motorie():
    return render_template("tutor_scienze_motorie.html")


@scienze_motorie_bp.route("/almanacco-scienze-motorie")
def almanacco_scienze_motorie():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_SCIENZE_MOTORIE_FILE):
        with open(ALMANACCO_SCIENZE_MOTORIE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#            if cache.get("data") == oggi:
            if oggi == oggi:
                return jsonify(cache["contenuto"])

    tema_disciplina, descr_disciplina = scegli_tema("disciplina", TEMI_DISCIPLINE)
    tema_enigma, descr_enigma = scegli_tema("enigma", TEMI_ENIGMI)
    tema_curiosita, descr_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA_SPORT)
    atleta, campo_atleta = scegli_tema("atleta", TEMI_ATLETI)

    prompt = (
        f"Genera l'almanacco di scienze motorie ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito o rompicapo sportivo breve basato su indizi o ragionamento",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione sportiva, chiara e breve",\n'
        '  "curiosita": "una curiosita sulla vita di un atleta o su uno sport famoso, 2-3 frasi",\n'
        '  "indovinello": "un indovinello su uno sport, un attrezzo o un elemento motorio",\n'
        "  \"soluzione_indovinello\": \"la risposta dell'indovinello\",\n"
        "  \"atleta_titolo\": \"nome dell'atleta o della figura sportiva del giorno\",\n"
        '  "atleta_testo": "racconto breve (4-5 frasi) di un aneddoto coinvolgente legato a questa figura, '
        'adatto a 11-13 anni"\n'
        "}\n\n"
        f"Per quesito_laterale, DEVE riguardare: '{tema_enigma}' ({descr_enigma}).\n"
        f"Per curiosita, DEVE riguardare: '{tema_curiosita}' ({descr_curiosita}).\n"
        f"Per indovinello, crea un indovinello avvincente a tema sportivo.\n"
        f"Per atleta_titolo e atleta_testo, scrivi OBBLIGATORIAMENTE di: {atleta} "
        f"({campo_atleta}). Scegli un aneddoto curioso e poco noto, legato anche a: {descr_disciplina}."
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
    with open(ALMANACCO_SCIENZE_MOTORIE_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@scienze_motorie_bp.route("/chat-scienze-motorie", methods=["POST"])
def chat_scienze_motorie():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_SARA,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
