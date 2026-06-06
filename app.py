import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

import pandas as pd
import requests
import streamlit as st

DATA_FILE = Path("fas_results_store.json")

st.set_page_config(page_title="FAS League GOL GOL Tracker", layout="wide")


def load_store() -> Dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"matches": [], "last_updated": None}


def save_store(store: Dict) -> None:
    DATA_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def build_stats(df: pd.DataFrame, window: int) -> Dict:
    if df.empty:
        return {"count": 0, "gg": 0, "pct": 0.0}
    wdf = df.head(window).copy()
    gg = int((wdf["gol_gol"] == "SI").sum())
    return {
        "count": len(wdf),
        "gg": gg,
        "pct": round((gg / len(wdf)) * 100, 2),
    }


def trend_label(current_pct: float, baseline_pct: float) -> str:
    delta = round(current_pct - baseline_pct, 2)
    if delta > 0:
        return f"In aumento (+{delta}%)"
    if delta < 0:
        return f"In calo ({delta}%)"
    return "Stabile (0%)"


def infer_gol_gol(result_details: List[Dict]) -> str:
    for item in result_details:
        market = str(item.get("market", "")).lower()
        result = str(item.get("result", "")).lower()
        if "gol" in market and "no gol" not in market:
            if result in {"gol", "goal", "gg"}:
                return "SI"
            if result in {"no gol", "nogol", "ng"}:
                return "NO"
    return "N/D"


def fetch_results_from_sisal() -> List[Dict]:
    date_str = datetime.now().strftime("%d-%m-%Y")
    api_url = (
        "https://betting.sisal.it/api/vrol-api/vrol/archivio/"
        f"getArchivioGareCampionato/1/3/6/{date_str}"
    )

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
st.write("TIPO ROOT JSON:", type(data).__name__)
if isinstance(data, dict):
    st.write("CHIAVI ROOT:", list(data.keys())[:30])
elif isinstance(data, list):
    st.write("LUNGHEZZA LISTA ROOT:", len(data))
    st.write("PRIMO ELEMENTO:", data[0] if data else "lista vuota")
    
    matches = []

    def walk(obj):
        if isinstance(obj, dict):
            if "descrizioneAvvenimento" in obj:
                desc = str(obj.get("descrizioneAvvenimento", "")).strip()
                data_ora = str(obj.get("dataOra", "")).strip()
                palinsesto = str(obj.get("codicePalinsesto", "")).strip()
                avv = str(obj.get("codiceAvvenimento", "")).strip()

                home_team = "Casa"
                away_team = "Trasferta"
                if " - " in desc:
                    parts = desc.split(" - ", 1)
                    home_team = parts[0].strip() or "Casa"
                    away_team = parts[1].strip() or "Trasferta"

                official_results = obj.get("risultatoScommessaUfficialeList", []) or []
                result_labels = []
                for rr in official_results:
                    label = rr.get("risultato") or rr.get("descrizioneEsito") or ""
                    market = rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or ""
                    quote = rr.get("quoteComb") or ""
                    result_labels.append(
                        {
                            "market": str(market),
                            "result": str(label),
                            "quote": str(quote),
                        }
                    )

                gol_gol = infer_gol_gol(result_labels)

                matches.append(
                    {
                        "match_id": f"{date_str}-{palinsesto}-{avv}",
                        "timestamp": f"{date_str} {data_ora}",
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_goals": 0,
                        "away_goals": 0,
                        "tot_goals": 0,
                        "gol_gol": gol_gol,
                        "markets_count": len(result_labels),
                        "raw_markets": " | ".join(
                            [f"{x['market']}: {x['result']}" for x in result_labels[:12]]
                        ),
                        "raw_row": json.dumps(obj, ensure_ascii=False),
                    }
                )

            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    dedup = {m["match_id"]: m for m in matches}
    results = list(dedup.values())
    results.sort(key=lambda x: str(x["timestamp"]), reverse=True)
    return results


st.title("FAS League GOL GOL Tracker")
st.caption("Dashboard manuale: clicca il pulsante per recuperare risultati, partite GOL GOL e trend.")

store = load_store()

col_a, col_b = st.columns([1, 3])
with col_a:
    refresh = st.button("Aggiorna risultati", type="primary", use_container_width=True)
with col_b:
    st.write(f"Ultimo aggiornamento: {store.get('last_updated') or 'mai'}")

if refresh:
    try:
        fresh_matches = fetch_results_from_sisal()
        if fresh_matches:
            store["matches"] = fresh_matches
            store["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_store(store)
            st.success(f"Recuperate {len(fresh_matches)} partite dall'API Sisal.")
        else:
            st.warning("Nessuna partita trovata nell'API Sisal per oggi.")
    except Exception as e:
        st.error(f"Errore nel recupero dati API: {e}")

matches = store.get("matches", [])
df = pd.DataFrame(matches)

if df.empty:
    st.info("Non ci sono ancora dati. Premi 'Aggiorna risultati'.")
    st.stop()

if "timestamp" in df.columns:
    df = df.sort_values(by="timestamp", ascending=False)

stats10 = build_stats(df[df["gol_gol"].isin(["SI", "NO"])], 10)
stats25 = build_stats(df[df["gol_gol"].isin(["SI", "NO"])], 25)
stats50 = build_stats(df[df["gol_gol"].isin(["SI", "NO"])], 50)
baseline_pct = stats50["pct"] if stats50["count"] else stats10["pct"]
trend = trend_label(stats10["pct"], baseline_pct)

k1, k2, k3, k4 = st.columns(4)
k1.metric("GOL GOL ultime 10", f"{stats10['pct']}%", f"{stats10['gg']}/{stats10['count']}")
k2.metric("GOL GOL ultime 25", f"{stats25['pct']}%", f"{stats25['gg']}/{stats25['count']}")
k3.metric("GOL GOL ultime 50", f"{stats50['pct']}%", f"{stats50['gg']}/{stats50['count']}")
k4.metric("Trend", trend)

chart_df = df[df["gol_gol"].isin(["SI", "NO"])].copy()
if not chart_df.empty:
    chart_df["gol_gol_num"] = (chart_df["gol_gol"] == "SI").astype(int)
    chart_df = chart_df.iloc[::-1].reset_index(drop=True)
    chart_df["media_mobile_10"] = chart_df["gol_gol_num"].rolling(10, min_periods=1).mean() * 100
    st.subheader("Trend GOL GOL")
    st.line_chart(chart_df[["gol_gol_num", "media_mobile_10"]], height=280)
else:
    st.warning("L'API è stata letta, ma non ho ancora individuato con certezza il mercato GOL/NO GOL per calcolare il trend.")

st.subheader("Partite uscite GOL GOL (SI)")
gg_df = df[df["gol_gol"] == "SI"][["timestamp", "home_team", "away_team", "gol_gol", "markets_count", "raw_markets"]]
st.dataframe(gg_df, use_container_width=True, hide_index=True)

st.subheader("Partite uscite NO GOL GOL (NO)")
no_df = df[df["gol_gol"] == "NO"][["timestamp", "home_team", "away_team", "gol_gol", "markets_count", "raw_markets"]]
st.dataframe(no_df, use_container_width=True, hide_index=True)

st.subheader("Partite con esito GOL GOL non ancora identificato")
nd_df = df[df["gol_gol"] == "N/D"][["timestamp", "home_team", "away_team", "gol_gol", "markets_count", "raw_markets"]]
st.dataframe(nd_df, use_container_width=True, hide_index=True)

st.subheader("Storico completo")
view_df = df[["timestamp", "home_team", "away_team", "gol_gol", "markets_count", "raw_markets"]]
st.dataframe(view_df, use_container_width=True, hide_index=True)

with st.expander("Note tecniche"):
    st.markdown(
        """
        - Questa versione usa direttamente l'endpoint JSON Sisal individuato dal browser, invece della pagina HTML che andava in timeout.
        - Il campo GOL GOL è dedotto cercando mercati/esiti che contengono "gol" nella risposta JSON.
        - Se alcune partite risultano N/D, dobbiamo affinare la mappatura guardando altri esempi della response API.
        """
    )
