
https://www.sisal.it/virtual-race/archivio-gare
mi serve un tool o bot che mi traccka in tempo reale i risultati della fas leauge su questo sito
2 passaggi completati
Sì: la soluzione più pratica è un piccolo bot di monitoraggio che interroga periodicamente la pagina/endpoint della FAS League e ti avvisa appena compare un nuovo risultato, invece di guardare manualmente l’archivio gare. Sisal indica che nelle Virtual Race ci sono eventi molto frequenti e che per Football All Stars League esistono giornate e classifica aggiornata in tempo reale, mentre l’Archivio Gare consente la ricerca dei risultati per data e giornata per FAS League/FAS.

Cosa conviene fare
Ti consiglio un tool in uno di questi 2 formati:

Bot Telegram: ricevi un messaggio appena esce un nuovo risultato FAS League, con polling ogni 15-30 secondi.

Mini web app/dashboard: pagina con auto-refresh, storico ultimi risultati, filtro per giornata/data e log delle variazioni rilevate dall’archivio Sisal.

La parte chiave è capire se la pagina espone i dati in HTML o tramite chiamate API/XHR lato browser; dalla pagina fetchata direttamente non emergono i risultati, quindi è probabile che i dati vengano caricati dinamicamente dopo l’apertura del sito. Per questo il bot va costruito osservando le richieste del browser verso Sisal e agganciandosi a quelle, se disponibili.

Architettura utile
Flusso semplice:

Il bot interroga ogni pochi secondi la fonte dati della FAS League.

Salva l’ultimo evento visto, per esempio ID partita, giornata, timestamp o hash del risultato.

Quando rileva una differenza, invia notifica e aggiorna uno storico locale.

Tecnologie comode:

Python + requests/httpx + parser JSON/HTML.

Scheduler leggero, oppure polling continuo.

Telegram Bot API per alert.

Facoltativo: Streamlit o pagina HTML per dashboard.
Questa impostazione è coerente col fatto che Sisal pubblica risultati e contenuti Virtual Race in modo continuo e consultabile tramite sito/app.

Limiti e attenzione
Ci sono due punti importanti:

Se i dati compaiono solo dopo login o tramite chiamate protette, servirà replicare sessione, header e forse cookie del browser; in alcuni casi è meglio usare browser automation controllata anziché puro scraping HTTP.

Va rispettato il sito: niente polling aggressivo; meglio intervalli ragionevoli, per esempio 20-30 secondi, dato che gli eventi virtuali sono molto frequenti ma non serve colpire il server ogni secondo.

Proposta pratica
Posso prepararti direttamente uno di questi:

Bot Telegram pronto all’uso con alert live.

Script Python che gira su PC o VPS e salva CSV/log.

Dashboard web con aggiornamento automatico.

Per farlo bene mi basta sapere una cosa: vuoi un bot che monitori solo i risultati finali della FAS League, oppure anche classifica/giornata/partite in arrivo?

prearami un bot telegram che mi restituisci i risultati ogni volta, in particolare i GOL GOL. Voglio che mi faccia una media dei gol gol, quindi squadre che segnano entrambe e mi calcola il trend di questa cosa

Ti preparo la struttura completa del bot: tu dovrai solo inserire il tuo token, il tuo chat_id e adattare la parte di scraping/lettura risultati in base a come appaiono i dati FAS League nella pagina o nelle API di Sisal (che non sono documentate pubblicamente).

L’idea:

il bot controlla periodicamente i nuovi risultati FAS League (“Archivio gare”);

identifica le partite GOL GOL (entrambe le squadre segnano);

salva i risultati in una piccola base dati locale (per es. file JSON) e calcola:

% di partite GOL GOL su un certo numero di match recenti;

trend (es. ultime N partite, moving average).

Di seguito trovi un esempio in Python con libreria python-telegram-bot (versione 21.x, la stessa usata negli esempi ufficiali).

1. Come impostare il progetto
Crea una cartella, ad esempio fas_golgol_bot/.

Crea un virtualenv e installa:

bash
pip install python-telegram-bot==21.7 requests
python-telegram-bot fornisce tutte le classi per bot, handler e polling.

All’interno crea un file config.py con:

python
BOT_TOKEN = "QUI_IL_TUO_TOKEN"
CHAT_ID = 123456789  # il tuo chat id o quello del gruppo
2. Logica di base: cosa fa il bot
Polling Telegram in background.

Un job periodico (es. ogni 30s) che:

legge la pagina/endpoint di archivio FAS League di Sisal;

individua l’ultima partita e confronta con l’ultima salvata;

se è nuova:

calcola se è GOL GOL (gol casa > 0 e gol ospite > 0);

aggiorna le statistiche globali;

manda un messaggio Telegram con:

risultato

se è GOL GOL o NO

media GOL GOL sugli ultimi N match

trend (es. ultimi 10 e ultimi 50).

3. Codice di esempio del bot
Nota: la funzione fetch_latest_match() è uno scheletro: dovrai completarci dentro il parsing reale della pagina Sisal, usando requests e magari BeautifulSoup oppure analizzando le chiamate XHR dal browser per capire se esiste un endpoint JSON con i risultati FAS League.

python
# main.py
import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN, CHAT_ID

DATA_FILE = "fas_results.json"


# ---------------------------
# Utilità per persistenza
# ---------------------------

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {
            "matches": [],      # lista di partite registrate
            "last_id": None,    # id o chiave dell'ultima partita letta
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------
# Da completare: lettura risultati da Sisal
# ---------------------------

def fetch_latest_match() -> Optional[Dict[str, Any]]:
    """
    Recupera l'ultima partita FAS League dall'Archivio gare Sisal.

    >>> STRUTTURA IDEALE DI RITORNO:
    {
        "id": "2026-06-02-1234",    # string univoca (puoi costruirla da data+ora+codice gara)
        "timestamp": "2026-06-02T15:20:00",
        "home_team": "Squadra A",
        "away_team": "Squadra B",
        "home_goals": 2,
        "away_goals": 1,
        "competition": "FAS League"
    }

    Attualmente è un MOCK: sostituiscilo con scraping reale.
    """
    # TODO: qui serve analisi della pagina:
    # 1. visita https://www.sisal.it/virtual-race/archivio-gare [web:15]
    # 2. imposta sport = FAS League (Football All Stars League) [web:2][web:16]
    # 3. individua l'ultima riga della tabella risultati e parse dei campi
    #
    # Esempio generico (pseudo):
    # resp = requests.get("https://www.sisal.it/virtual-race/archivio-gare", timeout=10)
    # html = resp.text
    # parse con BeautifulSoup per trovare la tabella e l'ultima riga

    return None  # finché non implementi lo scraping vero


# ---------------------------
# Logica GOL GOL e statistiche
# ---------------------------

def is_gol_gol(match: Dict[str, Any]) -> bool:
    return match["home_goals"] > 0 and match["away_goals"] > 0


def compute_stats(matches: List[Dict[str, Any]], window: int = 50) -> Dict[str, Any]:
    """
    Calcola la % di GOL GOL sull'intero storico e su una finestra recente.
    """
    if not matches:
        return {
            "total": 0,
            "gg_total": 0,
            "perc_total": 0.0,
            "window": window,
            "gg_window": 0,
            "perc_window": 0.0,
        }

    total = len(matches)
    gg_total = sum(1 for m in matches if is_gol_gol(m))
    perc_total = gg_total / total * 100

    window_matches = matches[-window:]
    gg_window = sum(1 for m in window_matches if is_gol_gol(m))
    perc_window = gg_window / len(window_matches) * 100 if window_matches else 0.0

    return {
        "total": total,
        "gg_total": gg_total,
        "perc_total": perc_total,
        "window": window,
        "gg_window": gg_window,
        "perc_window": perc_window,
    }


# ---------------------------
# Job periodico: controlla nuovi risultati
# ---------------------------

async def check_new_results(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    last_id = data.get("last_id")
    matches = data.get("matches", [])

    latest = fetch_latest_match()
    if latest is None:
        # nessun dato nuovo o errore nel fetch
        return

    if latest["id"] == last_id:
        # nessuna nuova partita
        return

    # Nuova partita
    matches.append(latest)
    data["matches"] = matches
    data["last_id"] = latest["id"]
    save_data(data)

    gg = is_gol_gol(latest)
    stats_50 = compute_stats(matches, window=50)
    stats_10 = compute_stats(matches, window=10)

    # Prepara testo messaggio
    dt = latest.get("timestamp", "")
    home = latest["home_team"]
    away = latest["away_team"]
    hs = latest["home_goals"]
    as_ = latest["away_goals"]

    status = "GOL GOL ✅" if gg else "NO GOL ❌"

    text = (
        f"Nuova partita FAS League:\n"
        f"{dt}\n"
        f"{home} {hs} - {as_} {away}\n"
        f"Esito: {status}\n\n"
        f"Statistica GOL GOL:\n"
        f"- Totale: {stats_50['gg_total']}/{stats_50['total']} "
        f"({stats_50['perc_total']:.1f}%)\n"
        f"- Ultime 50: {stats_50['gg_window']}/{min(stats_50['window'], stats_50['total'])} "
        f"({stats_50['perc_window']:.1f}%)\n"
        f"- Ultime 10: {stats_10['gg_window']}/{min(stats_10['window'], stats_10['total'])} "
        f"({stats_10['perc_window']:.1f}%)"
    )

    await context.bot.send_message(chat_id=CHAT_ID, text=text)


# ---------------------------
# Comandi Telegram
# ---------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ciao! Sono il bot FAS League GOL GOL.\n"
        "Ti manderò un messaggio ad ogni nuova partita con le statistiche aggiornate."
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    matches = data.get("matches", [])
    stats_50 = compute_stats(matches, window=50)
    stats_10 = compute_stats(matches, window=10)

    if not matches:
        await update.message.reply_text("Non ho ancora partite registrate.")
        return

    last = matches[-1]
    txt = (
        f"Statistiche GOL GOL FAS League\n"
        f"Partite totali memorizzate: {stats_50['total']}\n\n"
        f"- Totale: {stats_50['gg_total']}/{stats_50['total']} "
        f"({stats_50['perc_total']:.1f}%)\n"
        f"- Ultime 50: {stats_50['gg_window']}/{min(stats_50['window'], stats_50['total'])} "
        f"({stats_50['perc_window']:.1f}%)\n"
        f"- Ultime 10: {stats_10['gg_window']}/{min(stats_10['window'], stats_10['total'])} "
        f"({stats_10['perc_window']:.1f}%)\n\n"
        f"Ultima partita registrata:\n"
        f"{last['timestamp']} - {last['home_team']} {last['home_goals']} - "
        f"{last['away_goals']} {last['away_team']}"
    )
    await update.message.reply_text(txt)


# ---------------------------
# Avvio dell'applicazione
# ---------------------------

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Comandi
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))

    # Job periodico: ogni 30 secondi
    application.job_queue.run_repeating(
        check_new_results,
        interval=30,  # in secondi, puoi aumentare se vuoi essere più “gentile” con il sito
        first=5,
    )

    await application.run_polling(close_loop=False)


if __name__ == "__main__":
    asyncio.run(main())
4. Come completare la parte “Sisal”
Perché il bot funzioni davvero, devi implementare fetch_latest_match() sfruttando la struttura dell’Archivio Gare: da lì puoi filtrare per disciplina (FAS League / Football All Stars League) e data, e leggere l’ultima partita completata.

Suggerimento operativo:

Apri la pagina Archivio Gare nel browser, seleziona FAS / FAS League e una data recente.

Con gli strumenti sviluppatore (Network → XHR/fetch) guarda se quando cambi filtri parte una richiesta AJAX a un URL JSON: se sì, usa direttamente quell’endpoint in requests.get().

Se non c’è JSON esposto, fai scraping HTML delle righe di tabella (ultima riga = ultima partita).

Per calcolare GOL GOL ti basta estrarre i gol casa e gol ospite dai risultati.

5. Cosa puoi modificare facilmente
interval=30: frequenza con cui controlla nuovi risultati (attenzione a non esagerare).

Finestra delle statistiche: nel codice ho usato 50 e 10 partite, ma puoi cambiarle in compute_stats.

Messaggio: puoi aggiungere anche esito 1X2, somma goal o altri mercati, in base a quel che riesci a leggere dall’archivio.

Se vuoi, nel prossimo passo posso aiutarti a scrivere proprio la parte di scraping, se mi incolli l’HTML di una riga dell’Archivio Gare FAS League (o la risposta JSON di una chiamata XHR che vedi dal browser).

Per partire, su che sistema pensi di far girare il bot: sul tuo PC Windows/macOS oppure su un server/VPS sempre acceso?

Non ho un server consigliami un alternativa

Se non hai un server, l’alternativa migliore è usare un servizio hosted che tenga acceso il bot per te. Oggi le opzioni più semplici per un bot Python sono Railway per un processo sempre attivo, oppure GitHub Actions se ti basta un controllo schedulato invece di un bot live 24/7.

Opzioni pratiche
Soluzione	Quando va bene	Pro	Contro
Railway	Vuoi il bot sempre acceso con notifiche appena esce il risultato	Deploy rapido di bot Python, template dedicato per Telegram bot 
Il piano gratuito può cambiare nel tempo e va verificato nel tuo account 
GitHub Actions	Ti basta controllare ogni 5-15 minuti e mandare messaggi solo quando trova novità	Non serve server tuo, scheduler integrato, supporto timezone nei workflow schedulati 
Non è “real time” puro e hai limiti mensili/di esecuzione sui repo privati 
Render Cron Job	Vuoi lanciare uno script a intervalli senza tenere un processo sempre attivo	Facile da configurare come cron job 
Render indica un addebito minimo di $1 al mese per cron job 
Cosa ti consiglio
Per il tuo caso, io farei così:

Scelta 1: Railway, se vuoi avvisi quasi in tempo reale sul GOL GOL. Railway offre deploy rapidi per Python Telegram bot e ti evita tutta la gestione server.

Scelta 2: GitHub Actions, se vuoi spendere zero e ti va bene controllare l’archivio a intervalli, per esempio ogni 5 o 10 minuti.

Nel tuo scenario la seconda opzione è spesso sufficiente, perché il bot non deve servire utenti continui ma solo controllare Sisal, salvare i risultati e mandarti un messaggio quando trova una nuova partita con aggiornamento del trend GOL GOL.

Configurazione minima
Con GitHub Actions il flusso sarebbe:

carichi il progetto su GitHub;

salvi BOT_TOKEN e CHAT_ID nei Secrets;

imposti un workflow schedulato che esegue lo script Python periodicamente.

GitHub ha limiti di minuti e durata job sui piani free per repo privati, ma per uno script breve di polling schedulato di solito resti dentro, soprattutto se gira una volta ogni pochi minuti. Inoltre da marzo 2026 Actions supporta anche il fuso orario IANA nei cron schedule, quindi puoi impostarlo comodo per l’orario italiano.

Scelta consigliata
Se vuoi la mia raccomandazione netta: GitHub Actions è la migliore alternativa senza server, perché è gratis o quasi nel tuo caso, semplice da mantenere e adatta a uno script che controlla risultati e calcola statistiche GOL GOL/trend senza bisogno di restare sempre connesso. Se invece vuoi notifiche molto più immediate, allora Railway è il passo successivo più semplice.

Vuoi che ti prepari direttamente la versione del bot pensata per GitHub Actions, così ti lascio anche il file workflow.yml pronto?

ora non mi esce nulla

Allegato
image.jpg

Quella schermata quasi vuota significa molto probabilmente che l’app è crashata all’avvio oppure è rimasta in uno stato rotto dopo il deploy, e Streamlit non sta renderizzando il contenuto della pagina. Dallo screenshot si vede la cornice dell’app ma non il titolo né i widget, quindi il problema ora è probabilmente nel codice eseguito all’import o nei primissimi blocchi del file, non nel bottone o nell’API.

Cosa fare subito
Fai questi 3 passaggi, in questo ordine:

in alto a destra nell’app clicca i tre puntini;

scegli Reboot app oppure Rerun app;

se non cambia niente, apri Manage app e guarda i logs di errore.

Quando Streamlit Cloud mostra pagina vuota, i log sono il modo più rapido per capire se c’è un errore Python all’avvio o un blocco in esecuzione.

Test minimo
Per capire se il problema è davvero il file attuale, sostituisci temporaneamente tutto app.py con questo codice minimo:

python
import streamlit as st

st.set_page_config(page_title="Test", layout="wide")
st.title("Test app")
st.write("Se vedi questo, Streamlit funziona.")
Se dopo il commit questa pagina appare, allora Streamlit e il deploy sono sani e il problema è nel codice complesso che hai incollato. Se invece resta vuota anche così, c’è un problema di deploy/app state e non del parser Sisal.

Perché questo test serve
Abbiamo già verificato in precedenza che l’app si apriva e mostrava interfaccia, errori e pulsante, quindi Streamlit Cloud funzionava. Il fatto che ora tu veda una pagina quasi totalmente vuota suggerisce che l’ultima versione di app.py abbia introdotto un errore all’avvio oppure che l’app non abbia completato il render iniziale.

Passo più rapido
Fai il test con il file minimo qui sopra. È la strada più veloce per separare:

problema di Streamlit/deploy;

problema del codice attuale.

Appena hai fatto il test, mandami uno screenshot oppure incollami il contenuto dei log.

image.jpg

Allegato
image.jpg

Perfetto: questo conferma che Streamlit funziona benissimo e che il problema era nel codice dell’app precedente, non nel deploy o nel repo. Lo screenshot mostra la test app caricata correttamente, quindi adesso possiamo rimettere una versione molto più semplice e sicura del tracker e poi aggiungere pezzi poco alla volta.

Strategia migliore
Adesso non rimettiamo subito il codice complesso. Facciamo una versione intermedia che:

apre l’API Sisal JSON che hai trovato;

mostra solo le prime informazioni base della response;

non prova ancora a calcolare GOL GOL in automatico.

Così verifichiamo prima che i dati arrivino davvero nell’app, poi costruiamo sopra il resto.

Sostituisci tutto con questo
Cancella tutto app.py e incolla questo codice completo:

python
import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import json

st.set_page_config(page_title="FAS League Debug", layout="wide")

st.title("FAS League Debug")
st.write("Test lettura API Sisal")

date_str = datetime.now().strftime("%d-%m-%Y")
api_url = f"https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}"

st.write("API URL:", api_url)

if st.button("Leggi API"):
    try:
        r = requests.get(
            api_url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.sisal.it/",
            },
        )
        r.raise_for_status()
        data = r.json()

        st.success("API letta correttamente")

        st.subheader("Info root JSON")
        st.write("Tipo root:", type(data).__name__)

        if isinstance(data, dict):
            st.write("Chiavi root:", list(data.keys())[:50])

            # mostra anteprima compatta
            preview = {}
            for k, v in list(data.items())[:10]:
                if isinstance(v, (list, dict)):
                    preview[k] = f"{type(v).__name__} ({len(v) if hasattr(v, '__len__') else 'n/a'})"
                else:
                    preview[k] = v
            st.json(preview)

        elif isinstance(data, list):
            st.write("Lunghezza lista root:", len(data))
            if data:
                st.subheader("Primo elemento")
                st.json(data[0])

        st.subheader("JSON grezzo (prime 3000 battute)")
        st.code(json.dumps(data, ensure_ascii=False)[:3000])

    except Exception as e:
        st.error(f"Errore: {e}")
Cosa deve succedere
Dopo commit e deploy:

apri la app;

clicca Leggi API;

dovresti vedere:

API letta correttamente

Tipo root

Chiavi root oppure Lunghezza lista root

anteprima JSON.

A quel punto avremo finalmente la struttura reale della risposta direttamente dentro Streamlit, senza rompere tutto.

Perché facciamo così
L’endpoint Sisal che hai trovato risponde davvero ed è JSON. Il problema delle versioni precedenti era che cercavamo di interpretarlo troppo presto, senza prima vedere com’è fatto il root object reale nella tua app. Questa versione invece è solo un debug pulito e stabile.

Passo dopo
Quando hai fatto questo, mandami lo screenshot della schermata con:

Tipo root

Chiavi root

l’anteprima JSON.

Da lì ti preparo io il vero app.py finale, già con tabella partite, GOL GOL sì/no e trend.

la lista è lunghissima e continua

Allegato
image.jpg

Perfetto, adesso abbiamo capito la struttura. La root è una lista di 78 elementi, e dentro ogni elemento c’è risultatoModelloScommessaCampionatoMap, poi una chiave come "3", poi una lista di modelli, e dentro eventiScommessaList ci sono finalmente le partite con descrizioneAvvenimento, dataOra e risultatoScommessaUfficialeList. Quindi il parser adesso va scritto su quella struttura precisa, non con scansione ricorsiva generica.

Cosa fare ora
Cancella tutto app.py e incolla questo codice completo. Questo:

legge la lista root;

entra in risultatoModelloScommessaCampionatoMap;

estrae gli eventi da eventiScommessaList;

prova a dedurre GOL GOL / NO GOL dai mercati trovati;

mostra anche le partite N/D se il mercato non è ancora riconosciuto.

python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="FAS League GOL GOL Tracker", layout="wide")

st.title("FAS League GOL GOL Tracker")
st.caption("Dashboard manuale: clicca il pulsante per recuperare risultati, partite GOL GOL e trend.")


def infer_gol_gol(result_list):
    for rr in result_list:
        market = str(rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or "").lower()
        result = str(rr.get("risultato") or rr.get("descrizioneEsito") or "").lower()

        if "gol" in market:
            if result in ["gol", "goal", "gg"]:
                return "SI"
            if result in ["no gol", "nogol", "ng"]:
                return "NO"

    return "N/D"


def fetch_matches():
    date_str = datetime.now().strftime("%d-%m-%Y")
    api_url = f"https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}"

    r = requests.get(
        api_url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.sisal.it/",
        },
    )
    r.raise_for_status()
    data = r.json()

    matches = []

    if not isinstance(data, list):
        return matches

    for giornata_block in data:
        risultato_map = giornata_block.get("risultatoModelloScommessaCampionatoMap", {})
        if not isinstance(risultato_map, dict):
            continue

        for key, model_list in risultato_map.items():
            if not isinstance(model_list, list):
                continue

            for model in model_list:
                eventi = model.get("eventiScommessaList", [])
                if not isinstance(eventi, list):
                    continue

                for ev in eventi:
                    desc = str(ev.get("descrizioneAvvenimento", "")).strip()
                    data_ora = str(ev.get("dataOra", "")).strip()
                    codice_palinsesto = str(ev.get("codicePalinsesto", "")).strip()
                    codice_avvenimento = str(ev.get("codiceAvvenimento", "")).strip()

                    home_team = "Casa"
                    away_team = "Trasferta"
                    if " - " in desc:
                        parts = desc.split(" - ", 1)
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()

                    result_list = ev.get("risultatoScommessaUfficialeList", [])
                    if not isinstance(result_list, list):
                        result_list = []

                    gol_gol = infer_gol_gol(result_list)

                    raw_markets = []
                    for rr in result_list[:15]:
                        market = rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or ""
                        result = rr.get("risultato") or rr.get("descrizioneEsito") or ""
                        raw_markets.append(f"{market}: {result}")

                    matches.append({
                        "match_id": f"{date_str}-{codice_palinsesto}-{codice_avvenimento}",
                        "timestamp": f"{date_str} {data_ora}",
                        "home_team": home_team,
                        "away_team": away_team,
                        "gol_gol": gol_gol,
                        "markets_count": len(result_list),
                        "raw_markets": " | ".join(raw_markets)
                    })

    # dedup
    dedup = {}
    for m in matches:
        dedup[m["match_id"]] = m

    results = list(dedup.values())
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results


def build_stats(df, window):
    if df.empty:
        return {"count": 0, "gg": 0, "pct": 0.0}
    wdf = df.head(window).copy()
    gg = int((wdf["gol_gol"] == "SI").sum())
    return {
        "count": len(wdf),
        "gg": gg,
        "pct": round((gg / len(wdf)) * 100, 2)
    }


if st.button("Aggiorna risultati", type="primary"):
    try:
        matches = fetch_matches()
        st.session_state["matches"] = matches
        st.success(f"Partite trovate: {len(matches)}")
    except Exception as e:
        st.error(f"Errore API: {e}")

matches = st.session_state.get("matches", [])

if not matches:
    st.info("Premi 'Aggiorna risultati' per caricare i dati.")
    st.stop()

df = pd.DataFrame(matches)

valid_df = df[df["gol_gol"].isin(["SI", "NO"])].copy()
stats10 = build_stats(valid_df, 10)
stats25 = build_stats(valid_df, 25)
stats50 = build_stats(valid_df, 50)

c1, c2, c3 = st.columns(3)
c1.metric("GOL GOL ultime 10", f"{stats10['pct']}%", f"{stats10['gg']}/{stats10['count']}")
c2.metric("GOL GOL ultime 25", f"{stats25['pct']}%", f"{stats25['gg']}/{stats25['count']}")
c3.metric("GOL GOL ultime 50", f"{stats50['pct']}%", f"{stats50['gg']}/{stats50['count']}")

if not valid_df.empty:
    chart_df = valid_df.copy()
    chart_df = chart_df.iloc[::-1].reset_index(drop=True)
    chart_df["gol_gol_num"] = (chart_df["gol_gol"] == "SI").astype(int)
    chart_df["media_mobile_10"] = chart_df["gol_gol_num"].rolling(10, min_periods=1).mean() * 100
    st.subheader("Trend GOL GOL")
    st.line_chart(chart_df[["gol_gol_num", "media_mobile_10"]], height=300)

st.subheader("Partite uscite GOL GOL (SI)")
st.dataframe(
    df[df["gol_gol"] == "SI"][["timestamp", "home_team", "away_team", "gol_gol", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Partite uscite NO GOL GOL (NO)")
st.dataframe(
    df[df["gol_gol"] == "NO"][["timestamp", "home_team", "away_team", "gol_gol", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Partite non ancora classificate (N/D)")
st.dataframe(
    df[df["gol_gol"] == "N/D"][["timestamp", "home_team", "away_team", "gol_gol", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Storico completo")
st.dataframe(
    df[["timestamp", "home_team", "away_team", "gol_gol", "markets_count", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)
Cosa aspettarti
Dopo commit e deploy:

l’app non deve più mostrare il JSON infinito;

deve comparire il bottone;

cliccando, dovrebbe trovarti un certo numero di partite;

alcune saranno forse N/D, ma almeno inizierai a vedere le righe reali con squadre e mercati.

Perché adesso è meglio
Prima stavamo leggendo il JSON in modo troppo generico. Adesso invece stiamo seguendo esattamente il percorso che si vede nel tuo screenshot: lista root → risultatoModelloScommessaCampionatoMap → chiave "3" → modelli → eventiScommessaList.

Passo successivo
Fai questo replace completo, poi premi Aggiorna risultati e mandami uno screenshot della tabella. Se compaiono molte N/D, alla prossima iterazione ti faccio la versione che identifica meglio il vero mercato GOL/NO GOL.

image.jpg

Allegato
image.jpg

Perfetto: adesso funziona davvero. L’app trova 468 partite e popola le tabelle, quindi il parser della struttura JSON è corretto. I due problemi rimasti sono chiari dallo screenshot: i nomi squadra non vengono letti e il campo gol_gol resta N/D, anche se in raw_markets si vedono stringhe tipo 1X2 + Goal/No Goal 1: + No Goal e 1X2 + Goal/No Goal 1: + Goal.

Cosa sta succedendo
Il dato utile per classificare SI/NO c’è già dentro raw_markets, perché compaiono esiti + Goal e + No Goal. Quindi adesso basta:

leggere meglio descrizioneAvvenimento per estrarre le squadre;

interpretare + Goal come SI e + No Goal come NO quando il mercato contiene Goal/No Goal.

Sostituzione mirata
Non serve rifare tutto. Nel tuo app.py sostituisci solo la funzione infer_gol_gol(result_list) con questa:

python
def infer_gol_gol(result_list):
    for rr in result_list:
        market = str(rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or "").lower()
        result = str(rr.get("risultato") or rr.get("descrizioneEsito") or "").lower()

        if "goal/no goal" in market or "gol/no gol" in market:
            if "+ goal" in result or result.strip() in ["goal", "gol", "gg"]:
                return "SI"
            if "+ no goal" in result or "+ no gol" in result or result.strip() in ["no goal", "no gol", "nogol", "ng"]:
                return "NO"

    return "N/D"
Questa modifica è coerente con i valori che si vedono nello screenshot, dove il mercato contiene Goal/No Goal e l’esito contiene + Goal oppure + No Goal.

Squadre
Per i nomi squadra, il fatto che tu veda Casa e Trasferta significa che descrizioneAvvenimento non sta arrivando nel formato atteso oppure non sempre contiene " - " come separatore. Per sistemarlo, sostituisci anche questo blocco dentro fetch_matches():

python
home_team = "Casa"
away_team = "Trasferta"
if " - " in desc:
    parts = desc.split(" - ", 1)
    home_team = parts[0].strip()
    away_team = parts[1].strip()
con questo:

python
home_team = "Casa"
away_team = "Trasferta"

desc_clean = desc.replace("–", "-").replace("—", "-").strip()

if " - " in desc_clean:
    parts = desc_clean.split(" - ", 1)
    home_team = parts[0].strip() or "Casa"
    away_team = parts[1].strip() or "Trasferta"
elif "-" in desc_clean:
    parts = desc_clean.split("-", 1)
    home_team = parts[0].strip() or "Casa"
    away_team = parts[1].strip() or "Trasferta"
Questo serve perché nei dati reali i separatori possono variare, e il parser attuale è troppo rigido.

Cosa ti aspetti dopo
Dopo commit e redeploy:

molte righe N/D dovrebbero diventare SI o NO;

le tabelle GOL GOL e NO GOL GOL dovrebbero iniziare a popolarsi;

le percentuali ultime 10/25/50 non saranno più 0 se il mapping funziona.

Punto importante
Se dopo questa modifica le squadre restano ancora Casa/Trasferta, allora il passo successivo sarà stampare una colonna desc o descrizioneAvvenimento direttamente nella tabella per vedere il valore esatto che arriva dall’API. Ma prima prova questa correzione, perché per la parte GOL/NO GOL lo screenshot ci ha già dato abbastanza informazione per migliorare il parser.

Fai queste due sostituzioni e mandami il prossimo screenshot.

mandami tutto il codice, fai ogni volta cosi per evitare che elimino cos sbagliate
2 passaggi completati
Certo: da ora te lo mando sempre completo. Ti ho preparato un nuovo app.py intero da scaricare e sostituire tutto in blocco. Questa versione include:

parsing dell’API JSON corretta;

logica migliorata per riconoscere + Goal e + No Goal;

colonna descrizione_avvenimento per capire meglio i nomi squadra quando non vengono estratti bene.

Cosa fare
Scarica il nuovo app.py.

Vai nel repo GitHub.

Apri app.py.

Cancella tutto.

Incolla il nuovo file completo.

Fai Commit changes.

Cosa aspettarti
Dopo il redeploy:

l’app dovrebbe continuare a trovare le partite;

alcune righe N/D dovrebbero trasformarsi in SI o NO grazie al parsing di Goal/No Goal;

nello storico completo vedrai anche descrizione_avvenimento, utile per verificare perché alcuni team escono ancora come Casa/Trasferta.

Metodo da ora in poi
Sì, facciamo così ogni volta: solo file completi, niente patch parziali. Così eviti di cancellare il blocco sbagliato e lavoriamo in modo molto più pulito.

Quando lo rimetti online, mandami lo screenshot nuovo e continuo da lì.

image.jpg

Allegato
image.jpg

Perfetto: adesso il tool funziona davvero. Dallo screenshot si vede che trova 474 partite, classifica correttamente SI e NO, calcola le percentuali sulle ultime 10/25/50 e mostra anche il trend, quindi la parte API + logica GOL/NO GOL è sostanzialmente riuscita. L’unico difetto rimasto è che i nomi squadra sono ancora Casa e Trasferta, quindi il campo descrizioneAvvenimento non sta venendo valorizzato come ci aspettavamo oppure il nome partita sta in un altro campo del JSON.

Cosa ti consiglio
A questo punto io farei solo una rifinitura finale:

lasciare invariata tutta la logica GOL GOL, che ormai funziona;

aggiungere un piccolo pannello debug per vedere il nome reale dell’evento;

poi sistemare i team name in un ultimo passaggio.

Il resto non lo toccherei, perché lo screenshot conferma che medie e classificazione stanno già lavorando bene.

Situazione attuale
Quello che hai già ottenuto:

lettura dell’API JSON Sisal scoperta dal browser;

estrazione delle partite dal JSON annidato;

riconoscimento + Goal = SI e + No Goal = NO;

dashboard Streamlit con KPI e trend.

Quindi il progetto è già usabile per lo scopo principale, cioè vedere rapidamente le partite uscite GOL GOL e NO GOL GOL con un click.

Prossimo step utile
Da qui farei una sola modifica finale nel prossimo file completo:

aggiungo una colonna debug tipo event_name_raw;

provo 2-3 campi alternativi del JSON per i nomi squadra;

mantengo tutto il resto invariato.

Così non rischiamo di rompere una versione che adesso finalmente funziona. Vuoi che ti prepari subito l’app.py finale rifinito, completo come file intero, con tentativo avanzato di estrazione nomi squadra?

si, procedi pure con backtest alert e probabilità
4 passaggi completati
Posso farlo, ma prima devo sapere una cosa: quante partite ci sono di solito in un blocco (sempre 6 o può cambiare)?

sono sempre 6
4 passaggi completati





app_v2.py
Python
Perfetto: ho preparato una nuova versione del file assumendo sempre 6 partite per blocco, e ci ho aggiunto backtest, alert operativo e probabilità 4+/5+/6 GG .

Cosa ho aggiunto
La nuova versione include:

Backtest modello con MAE ultimi 10 blocchi, MAE ultimi 20 blocchi e Bias medio per misurare quanto la previsione avrebbe sbagliato sui blocchi passati, che è un modo standard per valutare un forecast storico.

Probabilità eventi per il prossimo blocco: Probabilità 4+ GG, Probabilità 5+ GG, Probabilità 6 GG, calcolate con una distribuzione binomiale su 6 partite usando la probabilità stimata del modello .

Alert visivo a tre livelli, basso/medio/alto, basato su forecast atteso e probabilità di eventi forti come 4+ o 6 GG, così la dashboard diventa più operativa e non solo descrittiva.

Come leggerli
Il MAE ti dice di quanto il modello sbaglia in media in numero di GG per blocco; più è basso, meglio è. Il Bias ti dice se il modello tende a sovrastimare o sottostimare sistematicamente i GG, mentre le probabilità 4+/5+/6 ti aiutano a trasformare il forecast in una lettura più concreta del rischio/opportunità del prossimo blocco.

Nota pratica
Ho salvato questa evoluzione come nuovo file perché il file precedente non era modificabile direttamente nell’ambiente corrente . Se vuoi, nel prossimo passaggio posso anche unificare tutto in una versione ancora più pulita con semaforo colori, storico alert e grafico forecast vs actual .

unifica tutto, dammi il codice completo finale
2 passaggi completati



fas_league_tracker_final.py
Python
Ho unificato tutto in un unico file finale: contiene caricamento dati, KPI trend, forecast, backtest, probabilità 4+/5+/6 GG, alert operativo, storico per blocchi, blocchi 6/6 e grafici finali .

Cosa contiene
Nel file finale trovi:

fetch dati Sisal del giorno;

calcolo esiti GOL / NO GOL;

metriche trend ultimi 5 e 10 blocchi;

previsione prossimo blocco e prossimi 3 blocchi con media pesata;

backtest con MAE e Bias;

probabilità binomiali su 6 partite;

alert visivo;

tabelle storiche e grafici riepilogativi .

Struttura del modello
La previsione usa una combinazione pesata delle percentuali GG degli ultimi 5, 10 e 20 blocchi, che è un approccio semplice e leggibile basato su rolling window. Il backtest applica la stessa logica sui blocchi passati per confrontare previsione e valore reale, pratica coerente con la validazione storica dei modelli di time series forecasting.

Uso pratico
Per usarlo, ti basta eseguire il file con Streamlit e premere Aggiorna risultati per caricare i dati correnti . Una volta caricati, nella parte alta avrai subito previsione, probabilità e alert, mentre sotto restano i dettagli completi per controllo operativo.

fas_league_tracker_final
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from math import comb

st.set_page_config(page_title='FAS League Tracker', layout='wide')

st.title('FAS League Tracker')
st.caption('Archivio risultati Sisal con focus GOL / NO GOL')


def infer_gol_gol(result_list):
    for rr in result_list:
        market = str(rr.get('descrizioneScommessa') or rr.get('modelloScommessa') or '').lower()
        result = str(rr.get('risultato') or rr.get('descrizioneEsito') or '').lower()
        if 'goal/no goal' in market or 'gol/no gol' in market:
            if '+ goal' in result or result.strip() in ['goal', 'gol', 'gg']:
                return 'GOL'
            if '+ no goal' in result or '+ no gol' in result or result.strip() in ['no goal', 'no gol', 'nogol', 'ng']:
                return 'NO GOL'
    return 'N/D'


def get_event_description(ev):
    candidates = [
        ev.get('descrizioneAvventimento'), ev.get('descrizioneAvvenimento'), ev.get('descrizioneEvento'),
        ev.get('evento'), ev.get('match'), ev.get('avvenimento'), ev.get('nomeEvento'), ev.get('labelEvento')
    ]
    for value in candidates:
        value = str(value or '').strip()
        if value:
            return value.replace(' ', '')
    return ''


def fetch_matches():
    date_str = datetime.now().strftime('%d-%m-%Y')
    api_url = f'https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}'
    r = requests.get(api_url, timeout=30, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://www.sisal.it/'
    })
    r.raise_for_status()
    data = r.json()
    matches = []
    if not isinstance(data, list):
        return matches
    for giornata_block in data:
        giornata = giornata_block.get('giornata')
        risultato_map = giornata_block.get('risultatoModelloScommessaCampionatoMap', {})
        if not isinstance(risultato_map, dict):
            continue
        for _, model_list in risultato_map.items():
            if not isinstance(model_list, list):
                continue
            for model in model_list:
                eventi = model.get('eventiScommessaList', [])
                if not isinstance(eventi, list):
                    continue
                for ev in eventi:
                    desc = get_event_description(ev)
                    data_ora = str(ev.get('dataOra') or '').strip()
                    codice_palinsesto = str(ev.get('codicePalinsesto') or '').strip()
                    codice_avvenimento = str(ev.get('codiceAvvenimento') or '').strip()
                    result_list = ev.get('risultatoScommessaUfficialeList', [])
                    if not isinstance(result_list, list):
                        result_list = []
                    esito = infer_gol_gol(result_list)
                    matches.append({
                        'match_id': f'{date_str}-{codice_palinsesto}-{codice_avvenimento}',
                        'timestamp': f'{date_str} {data_ora}',
                        'orario': data_ora,
                        'giornata': giornata,
                        'codice_avvenimento': codice_avvenimento,
                        'descrizione_avventimento': desc,
                        'esito': esito,
                    })
    dedup = {}
    for m in matches:
        dedup[m['match_id']] = m
    results = list(dedup.values())
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    return results


def build_blocks(df):
    if df.empty:
        return pd.DataFrame(columns=['orario', 'codice_avvenimento', 'GOL', '% sul totale'])
    grouped = df.groupby('orario').agg(
        codice_avvenimento=('codice_avvenimento', 'first'),
        totale=('esito', 'count'),
        GOL=('esito', lambda x: (x == 'GOL').sum())
    ).reset_index()
    grouped['% sul totale'] = ((grouped['GOL'] / grouped['totale']) * 100).round(2)
    grouped = grouped.sort_values('orario', ascending=False)
    return grouped[['orario', 'codice_avvenimento', 'GOL', '% sul totale']]


def build_trend_metrics(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy()
    if valid_df.empty:
        return {'last5': 0, 'prev5': 0, 'last10': 0, 'prev10': 0, 'latest_block_pct': 0.0}
    grouped = valid_df.groupby('orario').agg(
        totale=('esito', 'count'),
        gol=('esito', lambda x: (x == 'GOL').sum())
    ).reset_index().sort_values('orario', ascending=False)
    grouped['pct'] = ((grouped['gol'] / grouped['totale']) * 100).round(2)
    return {
        'last5': int(grouped.head(5)['gol'].sum()),
        'prev5': int(grouped.iloc[5:10]['gol'].sum()) if len(grouped) > 5 else 0,
        'last10': int(grouped.head(10)['gol'].sum()),
        'prev10': int(grouped.iloc[10:20]['gol'].sum()) if len(grouped) > 10 else 0,
        'latest_block_pct': float(grouped.iloc[0]['pct']) if not grouped.empty else 0.0,
    }


def build_all_gg_stats(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy()
    if valid_df.empty:
        return {'total_all_gg_blocks': 0, 'latest_streak': 0, 'blocks_table': pd.DataFrame(columns=['orario', 'GG', 'totale', 'all_gg_6su6'])}
    grouped = valid_df.groupby('orario').agg(
        totale=('esito', 'count'),
        GG=('esito', lambda x: (x == 'GOL').sum())
    ).reset_index().sort_values('orario', ascending=False)
    grouped['all_gg_6su6'] = (grouped['totale'] == 6) & (grouped['GG'] == 6)
    streak = 0
    for value in grouped['all_gg_6su6'].tolist():
        if value:
            streak += 1
        else:
            break
    return {
        'total_all_gg_blocks': int(grouped['all_gg_6su6'].sum()),
        'latest_streak': streak,
        'blocks_table': grouped[['orario', 'GG', 'totale', 'all_gg_6su6']]
    }


def build_forecast(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy()
    if valid_df.empty:
        return {
            'rate_5': 0.0, 'rate_10': 0.0, 'rate_20': 0.0, 'weighted_rate': 0.0,
            'next_block_expected': 0.0, 'next_block_rounded': 0, 'next_3_blocks_expected': 0.0,
            'range_min': 0, 'range_max': 0,
            'details': pd.DataFrame(columns=['finestra', 'percentuale_GG'])
        }
    grouped = valid_df.groupby('orario').agg(
        totale=('esito', 'count'),
        GG=('esito', lambda x: (x == 'GOL').sum())
    ).reset_index().sort_values('orario', ascending=False)
    grouped = grouped[grouped['totale'] > 0].copy()
    grouped['rate'] = grouped['GG'] / grouped['totale']

    def mean_rate(n):
        subset = grouped.head(n)
        return float(subset['rate'].mean()) if not subset.empty else 0.0

    rate_5 = mean_rate(5)
    rate_10 = mean_rate(10)
    rate_20 = mean_rate(20)
    weighted_rate = max(0.0, min(1.0, (0.5 * rate_5) + (0.3 * rate_10) + (0.2 * rate_20)))
    next_block_expected = round(weighted_rate * 6, 2)
    next_block_rounded = int(round(next_block_expected))
    next_3_blocks_expected = round(next_block_expected * 3, 2)
    range_min = max(0, int(round(next_block_expected - 1)))
    range_max = min(6, int(round(next_block_expected + 1)))
    details = pd.DataFrame([
        {'finestra': 'Ultimi 5 blocchi', 'percentuale_GG': round(rate_5 * 100, 2)},
        {'finestra': 'Ultimi 10 blocchi', 'percentuale_GG': round(rate_10 * 100, 2)},
        {'finestra': 'Ultimi 20 blocchi', 'percentuale_GG': round(rate_20 * 100, 2)},
        {'finestra': 'Media pesata finale', 'percentuale_GG': round(weighted_rate * 100, 2)},
    ])
    return {
        'rate_5': rate_5, 'rate_10': rate_10, 'rate_20': rate_20, 'weighted_rate': weighted_rate,
        'next_block_expected': next_block_expected, 'next_block_rounded': next_block_rounded,
        'next_3_blocks_expected': next_3_blocks_expected, 'range_min': range_min, 'range_max': range_max,
        'details': details
    }


def build_backtest(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy()
    cols = ['orario', 'actual_GG', 'predicted_GG', 'error']
    empty = pd.DataFrame(columns=cols)
    if valid_df.empty:
        return {'mae_10': 0.0, 'mae_20': 0.0, 'bias': 0.0, 'table': empty}
    grouped = valid_df.groupby('orario').agg(
        totale=('esito', 'count'),
        GG=('esito', lambda x: (x == 'GOL').sum())
    ).reset_index().sort_values('orario', ascending=True)
    grouped = grouped[grouped['totale'] > 0].copy()
    grouped['rate'] = grouped['GG'] / grouped['totale']
    preds = []
    for i in range(1, len(grouped)):
        hist = grouped.iloc[:i]
        def mean_rate(n):
            sub = hist.tail(n)
            return float(sub['rate'].mean()) if not sub.empty else 0.0
        rate_5 = mean_rate(5)
        rate_10 = mean_rate(10)
        rate_20 = mean_rate(20)
        weighted_rate = max(0.0, min(1.0, (0.5 * rate_5) + (0.3 * rate_10) + (0.2 * rate_20)))
        predicted = round(weighted_rate * 6, 2)
        actual = int(grouped.iloc[i]['GG'])
        preds.append({
            'orario': grouped.iloc[i]['orario'],
            'actual_GG': actual,
            'predicted_GG': predicted,
            'error': round(predicted - actual, 2),
            'abs_error': round(abs(predicted - actual), 2),
        })
    if not preds:
        return {'mae_10': 0.0, 'mae_20': 0.0, 'bias': 0.0, 'table': empty}
    backtest_df = pd.DataFrame(preds).sort_values('orario', ascending=False)
    return {
        'mae_10': round(float(backtest_df.head(10)['abs_error'].mean()), 2),
        'mae_20': round(float(backtest_df.head(20)['abs_error'].mean()), 2),
        'bias': round(float(backtest_df['error'].mean()), 2),
        'table': backtest_df[['orario', 'actual_GG', 'predicted_GG', 'error']]
    }


def build_probabilities(df):
    forecast = build_forecast(df)
    p = forecast['weighted_rate']

    def binom_prob_at_least(k, n=6, p=0.0):
        return sum(comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))

    p_ge4 = binom_prob_at_least(4, 6, p)
    p_ge5 = binom_prob_at_least(5, 6, p)
    p_eq6 = p ** 6
    p_ge4_3blocks = 1 - ((1 - p_ge4) ** 3)

    alert_level = 'low'
    if forecast['next_block_expected'] >= 4.5 or p_eq6 >= 0.12:
        alert_level = 'high'
    elif forecast['next_block_expected'] >= 3.8 or p_ge4 >= 0.55:
        alert_level = 'medium'

    if alert_level == 'high':
        msg = f"Alert alto: forecast {forecast['next_block_expected']} GG, P(4+)= {p_ge4:.1%}, P(6)= {p_eq6:.1%}."
    elif alert_level == 'medium':
        msg = f"Alert medio: forecast {forecast['next_block_expected']} GG, P(4+)= {p_ge4:.1%}."
    else:
        msg = f"Scenario standard: forecast {forecast['next_block_expected']} GG, P(4+)= {p_ge4:.1%}."

    return {
        'p_ge4': p_ge4,
        'p_ge5': p_ge5,
        'p_eq6': p_eq6,
        'p_ge4_3blocks': p_ge4_3blocks,
        'alert_level': alert_level,
        'alert_message': msg,
    }


if st.button('Aggiorna risultati', type='primary'):
    try:
        matches = fetch_matches()
        st.session_state['matches'] = matches
        st.session_state['last_update'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        st.success(f'Partite trovate: {len(matches)}')
    except Exception as e:
        st.error(f'Errore API: {e}')

matches = st.session_state.get('matches', [])
last_update = st.session_state.get('last_update', '-')

if not matches:
    st.info("Premi 'Aggiorna risultati' per caricare i dati.")
    st.stop()

df = pd.DataFrame(matches)
df = df.sort_values(['orario', 'timestamp'], ascending=False)

st.markdown(f'**Ultimo aggiornamento:** {last_update}')

trend = build_trend_metrics(df)
col1, col2, col3 = st.columns(3)
col1.metric('Partite GG ultimi 5 blocchi', trend['last5'], trend['last5'] - trend['prev5'])
col2.metric('Partite GG ultimi 10 blocchi', trend['last10'], trend['last10'] - trend['prev10'])
col3.metric('% partite GG ultimo blocco', f"{trend['latest_block_pct']}%")

st.subheader('Previsione prossimi blocchi')
forecast = build_forecast(df)
fc1, fc2, fc3 = st.columns(3)
fc1.metric('GG attesi prossimo blocco', forecast['next_block_expected'])
fc2.metric('Stima arrotondata prossimo blocco', forecast['next_block_rounded'])
fc3.metric('GG attesi prossimi 3 blocchi', forecast['next_3_blocks_expected'])
st.caption(f"Range stimato prossimo blocco: {forecast['range_min']} - {forecast['range_max']} GG")
st.dataframe(forecast['details'], use_container_width=True, hide_index=True)

st.subheader('Backtest e probabilità')
backtest = build_backtest(df)
prob = build_probabilities(df)

bt1, bt2, bt3 = st.columns(3)
bt1.metric('MAE ultimi 10 blocchi', backtest['mae_10'])
bt2.metric('MAE ultimi 20 blocchi', backtest['mae_20'])
bt3.metric('Bias medio', backtest['bias'])

pb1, pb2, pb3 = st.columns(3)
pb1.metric('Probabilità 4+ GG', f"{prob['p_ge4']:.1%}")
pb2.metric('Probabilità 5+ GG', f"{prob['p_ge5']:.1%}")
pb3.metric('Probabilità 6 GG', f"{prob['p_eq6']:.1%}")

if prob['alert_level'] == 'high':
    st.error(prob['alert_message'])
elif prob['alert_level'] == 'medium':
    st.warning(prob['alert_message'])
else:
    st.info(prob['alert_message'])

with st.expander('Dettaglio backtest', expanded=False):
    st.dataframe(backtest['table'], use_container_width=True, hide_index=True)

st.subheader('Blocchi con 6 GG su 6')
all_gg_stats = build_all_gg_stats(df)
col4, col5 = st.columns(2)
col4.metric('Totale blocchi 6 su 6', all_gg_stats['total_all_gg_blocks'])
col5.metric('Serie aperta 6 su 6', all_gg_stats['latest_streak'])

with st.expander('Dettaglio blocchi 6 GG su 6', expanded=False):
    st.dataframe(all_gg_stats['blocks_table'], use_container_width=True, hide_index=True)

with st.expander('Storico risultati per blocchi orari', expanded=False):
    storico_df = df[['orario', 'giornata', 'codice_avvenimento', 'descrizione_avventimento', 'esito']].copy()
    storico_df = storico_df.sort_values(['orario', 'giornata', 'codice_avvenimento'], ascending=[False, False, False])
    orari_unici = storico_df['orario'].dropna().unique().tolist()
    for i, ora in enumerate(orari_unici):
        blocco = storico_df[storico_df['orario'] == ora].copy()
        st.markdown(f'### Blocco {ora}')
        st.dataframe(blocco[['orario', 'giornata', 'codice_avvenimento', 'descrizione_avventimento', 'esito']], use_container_width=True, hide_index=True)
        if i < len(orari_unici) - 1:
            st.divider()

st.subheader('Blocchi orari')
blocks_df = build_blocks(df)
st.dataframe(blocks_df, use_container_width=True, hide_index=True)

if not blocks_df.empty:
    st.subheader('Grafico blocchi orari')
    bar_df = blocks_df.set_index('orario')[['GOL']]
    st.bar_chart(bar_df, height=320)

    st.subheader('Trend percentuale')
    trend_df = blocks_df.set_index('orario')[['% sul totale']]
    st.line_chart(trend_df, height=280)
