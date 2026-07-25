from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

matematica_bp = Blueprint("matematica", __name__)

ALMANACCO_FILE = "almanacco_cache.json"
TEMI_HISTORY_FILE = "temi_history.json"

SYSTEM = """Ti chiami Luca e sei un tutor di matematica e scienze per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Luca.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro e adatto a 11-14 anni.
2. Non usare mai diagrammi testuali (ASCII art, diagrammi Eulero-Venn in testo, tabelle disegnate con caratteri). Sono illeggibili.
3. Per le formule usa LaTeX: inline con \\( ... \\), su riga separata con \\[ ... \\].
4. A domande che esulano dal programma di matematica e scienze 11-14, rispondi in modo simpatico che esulano dal programma, anche si strettamente di matematica (come ad esempio la trigonometria)
5. Per il prodotto usa sempre il punto e non la x.

GESTIONE DELLE FIGURE GEOMETRICHE E ASTRAZIONI:
- Quando uno studente avrebbe bisogno di vedere una figura geometrica (triangolo, cerchio, retta, angolo, ecc.), NON descriverla soltanto: guidalo a costruirla da solo con GeoGebra Geometry, lo strumento di disegno disponibile a fianco della chat.
- Usa il tag <DISEGNA> con istruzioni chiare, numerate e nell'ordine in cui vanno eseguite, scritte come comandi pratici per i pulsanti di GeoGebra (es. "Punto", "Segmento", "Poligono", "Angolo", "Retta perpendicolare", "Circonferenza"). Esempio:
  <DISEGNA>
  1. Disegna un punto A in basso a sinistra e un punto B in basso a destra (strumento Punto).
  2. Collega A e B con un segmento.
  3. Disegna un punto C più in alto, poi unisci A-C e B-C per formare il triangolo.
  4. Usa lo strumento Angolo per misurare l'angolo in C.
  </DISEGNA>
- Usa <DISEGNA> con parsimonia, solo quando costruire la figura aiuta davvero a capire (non per ogni minima menzione di geometria).
- Per insiemi (Eulero-Venn): NON usare cerchi sovrapposti con lettere e NON suggerire di disegnarli. Usa invece la notazione algebrica degli insiemi e spiega con esempi concreti (es. "A = {2, 4, 6, 8} sono i numeri pari minori di 10").
- Per concetti astratti (funzioni, proporzionalità): usa esempi numerici concreti prima di qualsiasi generalizzazione.

GESTIONE DELLE TABELLE:
- Anche quando un confronto o un elenco di dati è più chiaro in forma tabellare, usa SEMPRE un elenco. La formattazione delle tabelle html è illeggibile

QUANDO LO STUDENTE SBAGLIA:
- Individua ESATTAMENTE dove si trova l'errore.
- Usa il tag <ERRORE> spiegando il ragionamento errato e perché è sbagliato.
- Poi mostra il procedimento corretto passo per passo.

STRUTTURA DELLE SPIEGAZIONI:
- Prima un esempio concreto e intuitivo, poi la regola generale.
- Risoluzione di esercizi: usa "Passo 1:", "Passo 2:", ecc.
- Chiudi sempre con una domanda di verifica o un mini-esercizio se appropriato.
- Usa **grassetto** per i termini chiave.

MOMENTI WOW (per mantenere alta l'attenzione):
Dopo una spiegazione o un esercizio risolto, NON SEMPRE ma quando ha senso (circa 1 volta ogni 2-3 scambi, mai meccanicamente), chiudi con uno di questi tipi di rilancio, variando il tipo usato:
- Sfida-lampo: una domanda simile ma leggermente diversa, da risolvere "a mente" o in pochi secondi.
- Collegamento sorprendente: come lo stesso concetto si applica a qualcosa di inaspettato nella vita reale, nello sport, nella tecnologia, nella natura.
- Trucco da "iniziato": una scorciatoia, un metodo mentale veloce, o un modo furbo di vedere il problema che i matematici/scienziati usano.
- Domanda capovolta: "e se cambiasse [una variabile]? Cosa pensi succederebbe?" per stimolare intuizione prima di spiegare.
Tieni questi momenti brevi (1-3 frasi), mai forzati, e mai nello stesso schema due volte di fila."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco, ognuna come lista di tuple (tema, ambito)
# ---------------------------------------------------------------------------

TEMI_STORIA = [
    ("Pitagora", "geometria"),
    ("Talete", "geometria"),
    ("Euclide", "geometria"),
    ("Archimede", "fisica e geometria"),
    ("Ipazia", "astronomia e matematica"),
    ("Fibonacci", "numeri"),
    ("Cartesio", "algebra e geometria"),
    ("Gauss", "numeri e algebra"),
    ("Newton", "fisica e calcolo"),
    ("Eulero", "algebra e analisi"),
    ("Sofia Kovalevskaya", "analisi"),
    ("Ada Lovelace", "informatica e algoritmi"),
    ("Ramanujan", "numeri"),
    ("Emmy Noether", "algebra"),
    ("Al-Khwarizmi", "algebra"),
    ("Leibniz", "calcolo"),
    ("Blaise Pascal", "probabilità"),
    ("Alan Turing", "informatica e logica"),
    ("Georg Cantor", "infinito e insiemi"),
    ("Talete e la misura delle piramidi", "geometria applicata"),
]

TEMI_QUESITO = [
    ("logica deduttiva", "chi mente/chi dice il vero, indizi da incrociare"),
    ("probabilità intuitiva", "una situazione dove l'intuito inganna"),
    ("fisica quotidiana", "un fenomeno che sembra assurdo ma ha una spiegazione semplice"),
    ("strategia e giochi", "una situazione tipo scacchi/carte dove serve pensare un passo avanti"),
    ("misure e stime", "stimare una quantità grande usando il buon senso"),
    ("spazio e forme", "un rompicapo che richiede di visualizzare mentalmente un oggetto 3D o un percorso"),
    ("linguaggio e ambiguità", "un indizio nascosto in una frase o in una domanda mal posta"),
    ("numeri e pattern", "una sequenza o una proprietà numerica sorprendente"),
    ("tempo e pianificazione", "un problema di organizzazione con vincoli (orari, percorsi, priorità)"),
    ("percezione e illusioni", "qualcosa che l'occhio o il senso comune interpretano male"),
]

TEMI_CURIOSITA = [
    ("numeri primi e crittografia", "matematica"),
    ("lo spazio e l'universo", "astronomia"),
    ("il corpo umano", "biologia"),
    ("il mondo animale", "biologia"),
    ("la tecnologia e i computer", "informatica"),
    ("la geometria nella natura", "matematica e natura"),
    ("l'infinito e i grandi numeri", "matematica"),
    ("la fisica del quotidiano", "fisica"),
    ("la storia della scrittura dei numeri", "matematica"),
    ("i record e le stranezze scientifiche", "scienza generale"),
    ("il clima e la Terra", "scienze della Terra"),
    ("le probabilità nella vita reale", "matematica"),
]

TEMI_INDOVINELLO = [
    ("logico", "un indovinello risolvibile con puro ragionamento, senza calcoli"),
    ("numerico", "un indovinello che richiede un piccolo calcolo o intuizione sui numeri"),
    ("geometrico", "un indovinello su forme, superfici o percorsi"),
    ("gioco di parole", "un indovinello basato su un doppio senso o un gioco linguistico"),
    ("probabilità", "un indovinello che gioca con l'idea di caso/fortuna"),
    ("misura del tempo", "un indovinello su orologi, calendari o durate"),
    ("classico rivisitato", "una variante originale di un indovinello matematico tradizionale"),
]


def _carica_history():
    try:
        with open(TEMI_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salva_history(history):
    with open(TEMI_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)


def scegli_tema(area, temi, quanti_da_ricordare=10):
    """
    Sceglie un tema in modo casuale per l'area indicata, evitando di ripetere
    gli ultimi `quanti_da_ricordare` temi già usati per quella stessa area.
    """
    history = _carica_history()
    usati_recenti = history.get(area, [])

    disponibili = [t for t in temi if t[0] not in usati_recenti]
    if not disponibili:
        disponibili = temi  # reset se esauriti

    scelto = random.choice(disponibili)

    usati_recenti.append(scelto[0])
    history[area] = usati_recenti[-quanti_da_ricordare:]
    _salva_history(history)

    return scelto


# ---------------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------------

@matematica_bp.route("/matematica")
def pagina_matematica():
    return render_template("tutor_matematica.html")


@matematica_bp.route("/almanacco")
def almanacco():
    oggi = date.today().isoformat()
    if os.path.exists(ALMANACCO_FILE):
        with open(ALMANACCO_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
#        if cache.get("data") == oggi:
        if oggi == oggi:
            return jsonify(cache["contenuto"])

    tema_quesito, tipo_quesito = scegli_tema("quesito", TEMI_QUESITO)
    tema_curiosita, ambito_curiosita = scegli_tema("curiosita", TEMI_CURIOSITA)
    tipo_indovinello, descr_indovinello = scegli_tema("indovinello", TEMI_INDOVINELLO)
    personaggio, ambito_storia = scegli_tema("storia", TEMI_STORIA)

    prompt = (
        f"Genera l'almanacco scientifico di ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito di pensiero laterale breve, intrigante, con soluzione non ovvia",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione, chiara e breve",\n'
        '  "curiosita": "una curiosità scientifica o matematica sorprendente, 2-3 frasi",\n'
        '  "indovinello": "un indovinello matematico o logico adatto a 11-13 anni",\n'
        '  "soluzione_indovinello": "la risposta dell\'indovinello",\n'
        '  "storia_titolo": "nome del matematico, scoperta o evento storico di oggi",\n'
        '  "storia_testo": "racconto breve (4-5 frasi) di un episodio di storia della matematica, '
        'adatto a 11-13 anni e scritto in modo coinvolgente"\n'
        "}\n\n"
        f"Per quesito_laterale, il quesito DEVE appartenere alla categoria '{tema_quesito}' "
        f"({tipo_quesito}).\n"
        f"Per curiosita, la curiosità DEVE riguardare l'ambito '{tema_curiosita}' ({ambito_curiosita}).\n"
        f"Per indovinello, l'indovinello DEVE essere di tipo '{tipo_indovinello}' ({descr_indovinello}).\n"
        f"Per storia_titolo e storia_testo, scrivi OBBLIGATORIAMENTE di: {personaggio} "
        f"(ambito: {ambito_storia}). Scegli un aneddoto o episodio specifico e poco scontato legato a questa figura, "
        "evitando il fatto più ovvio/conosciuto se possibile."
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
    with open(ALMANACCO_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": oggi, "contenuto": contenuto}, f, ensure_ascii=False)
    return jsonify(contenuto)


@matematica_bp.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        temperature=1.0,
        system=SYSTEM,
        messages=messages
    )

    return jsonify({"reply": response.content[0].text})
