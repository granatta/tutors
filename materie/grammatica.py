from flask import Blueprint, request, jsonify, render_template
import os
import json
import random
from datetime import date

from materie.claude_client import client

grammatica_bp = Blueprint("grammatica", __name__)

ALMANACCO_FILE = "almanacco_italiano_cache.json"
TEMI_HISTORY_FILE = "temi_italiano_history.json"

SYSTEM = """Ti chiami Giulia e sei una tutor di Italiano - grammatica, sintassi e analisi del testo - per studenti di scuola media italiana (11-14 anni). Se uno studente ti chiede come ti chiami, rispondi che ti chiami Giulia.

REGOLE FONDAMENTALI:
1. Rispondi SEMPRE in italiano, con linguaggio chiaro e adatto a 11-14 anni.
2. Non usare mai diagrammi testuali (ASCII art, alberi disegnati con caratteri, tabelle disegnate con trattini/pipe). Sono illeggibili.
3. A domande che esulano dal programma di italiano 11-14 (grammatica, sintassi, testo, lessico, un po' di letteratura), rispondi in modo simpatico che esulano dal programma.
4. Usa sempre la terminologia della grammatica scolastica italiana tradizionale (soggetto, predicato verbale/nominale, complemento oggetto, complemento di specificazione, attributo, apposizione, ecc.), non le sigle in inglese.

GESTIONE DELL'ANALISI SINTATTICA (ALBERO DELLE RELAZIONI):
- Quando uno studente avrebbe bisogno di vedere la struttura sintattica di una frase (soggetto, predicato, complementi, come si legano tra loro), NON descriverla soltanto a parole: invitalo a provarla nello strumento di Analisi Sintattica disponibile a fianco della chat, che disegna l'albero delle relazioni della frase.
- Usa il tag <ALBERO> inserendo ESATTAMENTE la frase da analizzare (breve, chiara, adatta all'esempio), senza commenti aggiuntivi dentro il tag. Esempio:
  <ALBERO>Io mangio la mela</ALBERO>
- Usa <ALBERO> con parsimonia, solo quando vedere l'albero aiuta davvero a capire la struttura (non per ogni minima frase di esempio orale).
- Quando invece stai semplicemente facendo un esempio veloce dentro la spiegazione (senza bisogno di disegnare l'albero), scrivi la frase normalmente nel testo.

GESTIONE DELLE TABELLE:
- Anche quando un confronto o un elenco è più chiaro in forma tabellare, usa SEMPRE un elenco puntato. La formattazione delle tabelle HTML è illeggibile nell'interfaccia.

QUANDO LO STUDENTE SBAGLIA:
- Individua ESATTAMENTE dove si trova l'errore (es. ha scambiato soggetto e complemento oggetto, ha sbagliato il modo del verbo, ha confuso un aggettivo con un avverbio).
- Usa il tag <ERRORE> spiegando il ragionamento errato e perché è sbagliato.
- Poi mostra il ragionamento corretto passo per passo.

STRUTTURA DELLE SPIEGAZIONI:
- Prima un esempio concreto e intuitivo, poi la regola generale.
- Analisi di una frase: usa "Passo 1:", "Passo 2:", ecc. (es. Passo 1: trova il verbo, Passo 2: trova il soggetto...).
- Chiudi sempre con una domanda di verifica o un mini-esercizio se appropriato.
- Usa **grassetto** per i termini chiave (nomi delle categorie grammaticali, funzioni logiche, ecc.).

MOMENTI WOW (per mantenere alta l'attenzione):
Dopo una spiegazione o un esercizio risolto, NON SEMPRE ma quando ha senso (circa 1 volta ogni 2-3 scambi, mai meccanicamente), chiudi con uno di questi tipi di rilancio, variando il tipo usato:
- Sfida-lampo: una frase simile ma leggermente diversa, da analizzare "a mente" in pochi secondi.
- Collegamento sorprendente: come una regola grammaticale si collega a qualcosa di inaspettato (un'altra lingua, un gioco di parole, un modo di dire, la tecnologia).
- Trucco da "iniziato": una scorciatoia o un modo furbo per riconoscere al volo una categoria grammaticale o una funzione logica.
- Domanda capovolta: "e se cambiassi [una parola/il tempo verbale/l'ordine]? Cosa pensi cambierebbe nella frase?" per stimolare intuizione prima di spiegare.
Tieni questi momenti brevi (1-3 frasi), mai forzati, e mai nello stesso schema due volte di fila."""


SYSTEM_ANALISI = """Sei un motore di analisi grammaticale e sintattica dell'italiano, pensato per studenti di scuola media (11-14 anni).

Ricevi una frase in italiano e devi restituire SOLO un oggetto JSON valido (senza testo prima o dopo, senza backtick, senza markdown), con questa struttura esatta:

{
  "parole": [
    {"testo": "Io", "pos": "PRON", "analisi": "Pronome personale di prima persona singolare, maschile, funzione di soggetto"}
  ],
  "predicato": {"indice": 1, "tipo": "verbale"},
  "archi": [
    {"da": 0, "a": 1, "etichetta": "nsubj", "etichetta_it": "soggetto"}
  ]
}

REGOLE:
- "parole" contiene un oggetto per ogni parola della frase, nell'ordine in cui compare (puoi omettere la punteggiatura finale).
- "pos" e' una sigla breve in maiuscolo tra: PRON, VERB, DET, NOUN, ADJ, ADV, PREP, CONJ, NUM, INTERJ, PART.
- "analisi" e' l'analisi grammaticale completa nello stile della grammatica scolastica italiana tradizionale (es. "Voce del verbo mangiare, prima coniugazione, modo indicativo, tempo presente, prima persona singolare, transitivo").
- "predicato" indica il predicato principale della frase: "indice" e' l'indice (a partire da 0) della parola che lo esprime (di solito il verbo principale, oppure la copula "essere" in un predicato nominale) e "tipo" vale "verbale" o "nominale". Se manca un vero predicato (es. frase nominale senza verbo), metti "indice": null e "tipo": null.
- "archi" descrive le relazioni sintattiche principali dell'analisi logica, ESCLUSO il predicato stesso (che e' gia' indicato a parte): soggetto, complemento oggetto, complemento di specificazione, attributo, apposizione, articolo, complementi indiretti (specificando il tipo), ecc.
- In ogni arco, "da" e' l'indice (a partire da 0) della parola dipendente/modificatrice e "a" e' l'indice della parola reggente (la testa della relazione): la freccia disegnata puntera' verso la parola reggente.
- "etichetta" e' una sigla breve in stile Universal Dependencies (nsubj, det, obj, amod, obl, ecc.) e "etichetta_it" e' il nome italiano tradizionale della funzione logica (soggetto, articolo, complemento oggetto, attributo, complemento di specificazione, ecc.). Non usare l'etichetta "root" per il predicato: quello va solo nel campo "predicato".
- Includi solo le relazioni sintattiche principali e davvero utili per far capire la struttura della frase allo studente: evita archi ridondanti o troppo minuti.
- Se la frase e' ambigua, scegli l'interpretazione piu' naturale e comune.
- Se la frase e' vuota o priva di senso compiuto, restituisci comunque un JSON valido con le liste vuote e "predicato" a valori null."""


# ---------------------------------------------------------------------------
# TEMI per le 4 aree dell'almanacco, ognuna come lista di tuple (tema, ambito)
# ---------------------------------------------------------------------------

TEMI_STORIA = [
    ("Dante Alighieri", "poesia e lingua italiana"),
    ("Francesco Petrarca", "poesia lirica"),
    ("Giovanni Boccaccio", "narrativa"),
    ("Alessandro Manzoni", "romanzo e lingua italiana"),
    ("Giacomo Leopardi", "poesia e pensiero"),
    ("Luigi Pirandello", "teatro e narrativa"),
    ("Italo Calvino", "narrativa e fiaba"),
    ("Elsa Morante", "narrativa"),
    ("Natalia Ginzburg", "narrativa e memoria"),
    ("Umberto Eco", "narrativa e semiotica"),
    ("Ludovico Ariosto", "poema cavalleresco"),
    ("Torquato Tasso", "poema epico"),
    ("Carlo Goldoni", "teatro"),
    ("Giovanni Verga", "narrativa verista"),
    ("Giovanni Pascoli", "poesia"),
    ("Gabriele D'Annunzio", "poesia e prosa"),
    ("Italo Svevo", "narrativa"),
    ("Primo Levi", "narrativa e testimonianza"),
    ("Grazia Deledda", "narrativa"),
    ("Cecco Angiolieri", "poesia comico-realistica"),
]

TEMI_QUESITO = [
    ("ambiguita' linguistica", "una frase che si puo' leggere in due modi diversi"),
    ("giochi di parole", "un doppio senso o un'ambiguita' comica nascosta in una frase"),
    ("etimologia sorprendente", "l'origine inaspettata di una parola comune"),
    ("omofonie", "parole che si pronunciano uguali ma si scrivono diverso e significano cose diverse"),
    ("proverbi da decifrare", "un proverbio o modo di dire da interpretare correttamente"),
    ("acronimi curiosi", "una sigla comune di cui pochi conoscono il vero significato"),
    ("palindromi", "una parola o frase che si legge uguale al contrario"),
    ("neologismi", "una parola nuova entrata di recente nell'italiano e da dove viene"),
    ("dialetti e origini regionali", "una parola italiana comune che viene in realta' da un dialetto"),
    ("codici nel testo", "un messaggio o indizio nascosto dentro un testo, da scovare con attenzione"),
]

TEMI_CURIOSITA = [
    ("l'origine delle parole", "etimologia"),
    ("la storia dell'alfabeto", "scrittura"),
    ("parole intraducibili di altre lingue", "linguistica"),
    ("l'evoluzione della lingua italiana", "storia della lingua"),
    ("i dialetti italiani", "linguistica"),
    ("le parole prese in prestito da altre lingue", "linguistica"),
    ("la storia della punteggiatura", "scrittura"),
    ("i record linguistici (parole piu' lunghe, rare, ecc.)", "curiosita' linguistiche"),
    ("l'invenzione della stampa e la diffusione dell'italiano", "storia della lingua"),
    ("l'origine dei modi di dire", "linguistica"),
    ("come sono nati i nomi delle citta' italiane", "toponomastica"),
    ("le parole che cambiano significato nel tempo", "linguistica"),
]

TEMI_INDOVINELLO = [
    ("logico", "un indovinello risolvibile con puro ragionamento, senza trucchi linguistici"),
    ("gioco di parole", "un indovinello basato su un doppio senso o un'ambiguita' linguistica"),
    ("anagramma", "un indovinello che richiede di riordinare le lettere di una parola"),
    ("rima nascosta", "un indovinello in filastrocca che nasconde la risposta in una rima"),
    ("sciarada", "un indovinello dove la parola si scompone in sillabe con significati diversi"),
    ("classico rivisitato", "una variante originale di un indovinello linguistico tradizionale"),
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
    gli ultimi `quanti_da_ricordare` temi gia' usati per quella stessa area.
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

@grammatica_bp.route("/grammatica")
def pagina_grammatica():
    return render_template("tutor_grammatica.html")


@grammatica_bp.route("/almanacco-italiano")
def almanacco_italiano():
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
    autore, ambito_storia = scegli_tema("storia", TEMI_STORIA)

    prompt = (
        f"Genera l'almanacco di italiano ({oggi}) per studenti di scuola media (11-13 anni).\n"
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questa struttura esatta:\n\n"
        "{\n"
        '  "quesito_laterale": "un quesito linguistico breve, intrigante, con soluzione non ovvia",\n'
        '  "soluzione_quesito": "la spiegazione della soluzione, chiara e breve",\n'
        '  "curiosita": "una curiosita\' linguistica o letteraria sorprendente, 2-3 frasi",\n'
        '  "indovinello": "un indovinello linguistico o logico adatto a 11-13 anni",\n'
        '  "soluzione_indovinello": "la risposta dell\'indovinello",\n'
        '  "storia_titolo": "nome dell\'autore, opera o evento letterario di oggi",\n'
        '  "storia_testo": "racconto breve (4-5 frasi) di un episodio legato a questo autore/opera, '
        'adatto a 11-13 anni e scritto in modo coinvolgente"\n'
        "}\n\n"
        f"Per quesito_laterale, il quesito DEVE appartenere alla categoria '{tema_quesito}' "
        f"({tipo_quesito}).\n"
        f"Per curiosita, la curiosita' DEVE riguardare l'ambito '{tema_curiosita}' ({ambito_curiosita}).\n"
        f"Per indovinello, l'indovinello DEVE essere di tipo '{tipo_indovinello}' ({descr_indovinello}).\n"
        f"Per storia_titolo e storia_testo, scrivi OBBLIGATORIAMENTE di: {autore} "
        f"(ambito: {ambito_storia}). Scegli un aneddoto o episodio specifico e poco scontato legato a questa figura, "
        "evitando il fatto piu' ovvio/conosciuto se possibile."
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


@grammatica_bp.route("/chat-italiano", methods=["POST"])
def chat_italiano():
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


@grammatica_bp.route("/analizza-frase", methods=["POST"])
def analizza_frase():
    data = request.json
    frase = (data.get("frase") or "").strip()

    if not frase:
        return jsonify({"errore": "Scrivi prima una frase da analizzare."}), 400

    if len(frase) > 300:
        return jsonify({"errore": "La frase e' troppo lunga, prova ad accorciarla."}), 400

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.3,
        system=SYSTEM_ANALISI,
        messages=[{"role": "user", "content": frase}]
    )
    testo = response.content[0].text.strip()
    testo = testo.replace("```json", "").replace("```", "").strip()

    try:
        risultato = json.loads(testo)
    except json.JSONDecodeError:
        return jsonify({"errore": "Non sono riuscita ad analizzare questa frase, riprova con un'altra."}), 500

    if "parole" not in risultato or "archi" not in risultato:
        return jsonify({"errore": "Analisi incompleta, riprova con un'altra frase."}), 500

    risultato.setdefault("predicato", {"indice": None, "tipo": None})

    return jsonify(risultato)
