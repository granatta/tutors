from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

musica_bp = Blueprint("musica", __name__)

ALMANACCO_MUSICA_FILE = "almanacco_musica_cache.json"
TEMI_MUSICA_HISTORY_FILE = "temi_musica_history.json"

SYSTEM_NINA = """Ti chiami Nina e sei una tutor di Musica per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Nina.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro, avvincente e adatto a ragazzi di 11-14 anni.
2. Non usare mai diagrammi testuali complessi in ASCII art.
3. A domande che esulano dal programma di educazione musicale delle scuole medie (teoria musicale, strumenti, generi, storia della musica, canto e ritmo, ascolto attivo), rispondi in modo simpatico ricordando il tuo ambito.
4. Usa la terminologia musicale scolastica (note, accordi, scale, ritmo, tempo, melodia, armonia, generi ed epoche musicali).

STRUTTURA DELLE SPIEGAZIONI:
- Contestualizza sempre gli argomenti (Che cos'e? Da dove viene? Come si usa o si ascolta?).
- Spiega i concetti evidenziando **cause** ed **effetti** sul suono (es. perche un accordo suona "triste" o "allegro").
- Analisi di argomenti complessi: usa "Fase 1:", "Fase 2:", ecc. o "Elemento:", "Funzione:", "Effetto:".
- Chiudi sempre con una domanda di riflessione o un mini-quiz per verificare la comprensione.
- Usa **grassetto** per i termini chiave, nomi di brani, artisti e concetti fondamentali.

GESTIONE DELLE TABELLE:
- Usa elenchi puntati o numerati. La formattazione delle tabelle HTML e spesso illeggibile nelle interfacce chat.

MOMENTI WOW (per mantenere alta l'attenzione):
Ogni 2-3 scambi, chiudi con un rilancio avvincente:
- Aneddoto o curiosita poco nota sulla vita di un musicista o sulla nascita di un brano.
- "Prova tu!": un piccolo esercizio di ascolto o ritmo da fare a voce o battendo le mani.
- Collegamento con l'attualita, la tecnologia o altre materie (matematica nel ritmo, fisica del suono).
- Trucco per memorizzare le note, gli intervalli o un genere musicale."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco musicale
# ---------------------------------------------------------------------------

TEMI_GENERI = [
    ("Musica Classica", "l'orchestra sinfonica o i grandi compositori del passato"),
    ("Jazz", "l'improvvisazione e le origini afroamericane"),
    ("Rock", "le origini e i gruppi che hanno fatto la storia"),
    ("Pop", "come si e evoluta la musica pop nei decenni"),
    ("Musica Elettronica", "sintetizzatori, DJ e produzione digitale"),
    ("Musica Popolare Italiana", "canzoni tradizionali e grandi cantautori"),
    ("Hip Hop", "le origini e la cultura urbana da cui e nato"),
]

TEMI_ENIGMI = [
    ("strumenti misteriosi", "uno strumento musicale insolito, antico o poco conosciuto"),
    ("canzoni e codici", "un significato nascosto o un messaggio dentro un testo musicale"),
    ("teoria musicale", "un piccolo enigma su accordi, scale o intervalli"),
    ("orecchio assoluto", "una curiosita sulla percezione del suono e dell'udito"),
]

TEMI_CURIOSITA_MUSICA = [
    ("vita dei musicisti", "un aneddoto sulla vita quotidiana di un compositore o artista"),
    ("strumenti musicali nel mondo", "uno strumento tradizionale tipico di una cultura diversa"),
    ("la musica nel cervello", "come la musica influenza le emozioni e la memoria"),
    ("origini di canzoni famose", "la storia curiosa dietro un brano celebre"),
]

TEMI_MUSICISTI = [
    ("Wolfgang Amadeus Mozart", "il Classicismo"),
    ("Ludwig van Beethoven", "tra Classicismo e Romanticismo"),
    ("Johann Sebastian Bach", "il Barocco"),
    ("Giuseppe Verdi", "l'opera italiana dell'Ottocento"),
    ("Louis Armstrong", "la nascita del Jazz"),
    ("The Beatles", "la rivoluzione del Rock negli anni '60"),
    ("Freddie Mercury e i Queen", "il Rock degli anni '70-'80"),
    ("Ludovico Einaudi", "la musica contemporanea italiana"),
]


def _carica_history():
    try:
        with open(TEMI_MUSICA_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_MUSICA_HISTORY_FILE, "w", encoding="utf-8") as f:
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

@musica_bp.route("/musica")
def pagina_musica():
    return render_template("tutor_musica.html")


@musica_bp.route("/almanacco-musica")
def almanacco_musica():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_MUSICA_FILE):
        with open(ALMANACCO_MUSICA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#            if cache.get("data") == oggi:
            if oggi == oggi:
                return jsonify(cache["contenuto"])

    tema_genere, descr_genere = scegli_tema("genere", TEMI_GENERI)
    tema_enigma, descr_enigma = scegli_tema("enigma", TEMI_ENIGMI)
    tema_curiosita, descr_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA_MUSICA)
    musicista, epoca_musicista = scegli_tema("musicista", TEMI_MUSICISTI)

    prompt = (
        f"Genera l'almanacco di musica ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito o rompicapo musicale breve basato su indizi o ragionamento",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione musicale, chiara e breve",\n'
        '  "curiosita": "una curiosita sulla vita di un musicista o su un brano famoso, 2-3 frasi",\n'
        '  "indovinello": "un indovinello su uno strumento, un genere o un elemento musicale",\n'
        "  \"soluzione_indovinello\": \"la risposta dell'indovinello\",\n"
        "  \"musicista_titolo\": \"nome del musicista o compositore del giorno\",\n"
        '  "musicista_testo": "racconto breve (4-5 frasi) di un aneddoto coinvolgente legato a questa figura, '
        'adatto a 11-13 anni"\n'
        "}\n\n"
        f"Per quesito_laterale, DEVE riguardare: '{tema_enigma}' ({descr_enigma}).\n"
        f"Per curiosita, DEVE riguardare: '{tema_curiosita}' ({descr_curiosita}).\n"
        f"Per indovinello, crea un indovinello avvincente a tema musicale.\n"
        f"Per musicista_titolo e musicista_testo, scrivi OBBLIGATORIAMENTE di: {musicista} "
        f"({epoca_musicista}). Scegli un aneddoto curioso e poco noto, legato anche a: {descr_genere}."
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
    with open(ALMANACCO_MUSICA_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@musica_bp.route("/chat-musica", methods=["POST"])
def chat_musica():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM_NINA,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
