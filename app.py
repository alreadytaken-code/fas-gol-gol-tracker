import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
import requests
import streamlit as st

ARCHIVE_URL = "https://www.sisal.it/virtual-race/archivio-gare"
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
    DATA_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_gol_gol(home_goals: int, away_goals: int) -> bool:
    return home_goals > 0 and away_goals > 0


def add_flags(matches: List[Dict]) -> List[Dict]:
    enriched = []
    for m in matches:
        hg = int(m.get("home_goals", 0))
        ag = int(m.get("away_goals", 0))
        gg = is_gol_gol(hg, ag)
        row = dict(m)
        row["gol_gol"] = "SI" if gg else "NO"
        row["tot_goals"] = hg + ag
        enriched.append(row)
    return enriched


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


def parse_score(text: str) -> Optional[tuple]:
    text = text.replace("–", "-").replace("—", "-").strip()
    if "-" not in text:
        return None
    left, right = [x.strip() for x in text.split("-", 1)]
    if left.isdigit() and right.isdigit():
        return int(left), int(right)
    return None


def fetch_results_from_sisal() -> List[Dict]:
    r = requests.get(
        ARCHIVE_URL,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    html = r.text

    tables = pd.read_html(html)
    matches = []

    for table in tables:
        cols = [str(c).strip().lower() for c in table.columns]
        joined = " ".join(cols)
        if not any(k in joined for k in ["risult", "squadr", "team", "gara", "esito"]):
            continue

        for _, row in table.iterrows():
            row_dict = {
                str(k).strip().lower(): str(v).strip()
                for k, v in row.to_dict().items()
            }
            raw = " | ".join(row_dict.values())

            score = None
            for val in row_dict.values():
                score = parse_score(val)
                if score:
                    break
            if not score:
                continue

            home_team = (
                row_dict.get("squadra casa")
                or row_dict.get("home")
                or row_dict.get("team 1")
                or row_dict.get("gara")
                or "Casa"
            )
            away_team = (
                row_dict.get("squadra trasferta")
                or row_dict.get("away")
                or row_dict.get("team 2")
                or "Trasferta"
            )
            event_time = (
                row_dict.get("data")
                or row_dict.get("giornata")
                or row_dict.get("orario")
                or datetime.now().isoformat(timespec="minutes")
            )

            matches.append(
                {
                    "match_id": f"{event_time}-{home_team}-{away_team}-{score[0]}-{score[1]}",
                    "timestamp": event_time,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_goals": score[0],
                    "away_goals": score[1],
                    "raw_row": raw,
                }
            )

    dedup = {m["match_id"]: m for m in matches}
    results = list(dedup.values())
    results.sort(key=lambda x: str(x["timestamp"]), reverse=True)
    return results


st.title("FAS League GOL GOL Tracker")
st.caption(
    "Dashboard manuale: clicca il pulsante per recuperare risultati, partite GOL GOL e trend."
)

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
            st.success(f"Recuperate {len(fresh_matches)} partite.")
        else:
            st.warning(
                "Nessuna partita trovata. Potrebbe servire adattare il parser alla struttura reale della pagina Sisal."
            )
    except Exception as e:
        st.error(f"Errore nel recupero dati: {e}")

matches = add_flags(store.get("matches", []))
df = pd.DataFrame(matches)

if df.empty:
    st.info("Non ci sono ancora dati. Premi 'Aggiorna risultati'.")
    st.stop()

if "timestamp" in df.columns:
    df = df.sort_values(by="timestamp", ascending=False)

stats10 = build_stats(df, 10)
stats25 = build_stats(df, 25)
stats50 = build_stats(df, 50)
baseline_pct = stats50["pct"] if stats50["count"] else stats10["pct"]
trend = trend_label(stats10["pct"], baseline_pct)

k1, k2, k3, k4 = st.columns(4)
k1.metric("GOL GOL ultime 10", f"{stats10['pct']}%", f"{stats10['gg']}/{stats10['count']}")
k2.metric("GOL GOL ultime 25", f"{stats25['pct']}%", f"{stats25['gg']}/{stats25['count']}")
k3.metric("GOL GOL ultime 50", f"{stats50['pct']}%", f"{stats50['gg']}/{stats50['count']}")
k4.metric("Trend", trend)

chart_df = df.copy()
chart_df["gol_gol_num"] = (chart_df["gol_gol"] == "SI").astype(int)
chart_df = chart_df.iloc[::-1].reset_index(drop=True)
chart_df["media_mobile_10"] = chart_df["gol_gol_num"].rolling(10, min_periods=1).mean() * 100

st.subheader("Trend GOL GOL")
st.line_chart(chart_df[["gol_gol_num", "media_mobile_10"]], height=280)

st.subheader("Partite uscite GOL GOL (SI)")
gg_df = df[df["gol_gol"] == "SI"][
    ["timestamp", "home_team", "away_team", "home_goals", "away_goals", "gol_gol"]
]
st.dataframe(gg_df, use_container_width=True, hide_index=True)

st.subheader("Partite uscite NO GOL GOL (NO)")
no_df = df[df["gol_gol"] == "NO"][
    ["timestamp", "home_team", "away_team", "home_goals", "away_goals", "gol_gol"]
]
st.dataframe(no_df, use_container_width=True, hide_index=True)

st.subheader("Storico completo")
view_df = df[
    [
        "timestamp",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "tot_goals",
        "gol_gol",
        "raw_row",
    ]
]
st.dataframe(view_df, use_container_width=True, hide_index=True)

with st.expander("Note tecniche"):
    st.markdown(
        """
        - Il parser HTML è generico e potrebbe richiedere un adattamento alla struttura reale di Sisal.
        - Se la pagina carica i risultati via JavaScript/XHR, conviene intercettare l'endpoint JSON dal browser e sostituire `fetch_results_from_sisal()`.
        - La colonna `gol_gol` mostra chiaramente quali partite sono uscite SI e quali NO.
        """
    )
