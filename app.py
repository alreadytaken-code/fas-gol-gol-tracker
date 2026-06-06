import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="FAS League GOL GOL Tracker", layout="wide")

st.title("FAS League GOL GOL Tracker")
st.caption("Dashboard manuale: clicca il pulsante per recuperare risultati, partite GOL GOL e trend per blocchi orari.")


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


def clean_team_name(name):
    name = str(name).strip()
    name = re.sub(r"\s+", " ", name)
    return name.title() if name else ""


def try_extract_from_text(text):
    text = str(text or "").strip().replace("–", "-").replace("—", "-")
    if not text:
        return None

    if " - " in text:
        parts = text.split(" - ", 1)
    elif "-" in text:
        parts = text.split("-", 1)
    else:
        return None

    home = clean_team_name(parts[0])
    away = clean_team_name(parts[1])
    if home and away:
        return home, away, text
    return None


def extract_teams(ev, result_list=None):
    candidates = []

    for key in [
        "descrizioneAvvenimento",
        "descrizioneEvento",
        "evento",
        "match",
        "avvenimento",
        "nomeEvento",
        "labelEvento",
        "competitor1",
        "competitor2",
        "descEvento",
    ]:
        if key in ev and ev.get(key):
            candidates.append((f"ev.{key}", str(ev.get(key))))

    if result_list:
        for i, rr in enumerate(result_list[:5]):
            for key in [
                "descrizioneAvvenimento",
                "descrizioneEvento",
                "evento",
                "match",
                "avvenimento",
                "nomeEvento",
                "labelEvento",
            ]:
                if key in rr and rr.get(key):
                    candidates.append((f"rr[{i}].{key}", str(rr.get(key))))

    for source, text in candidates:
        parsed = try_extract_from_text(text)
        if parsed:
            home, away, raw = parsed
            return home, away, raw, source

    return "Casa", "Trasferta", "", "not_found"


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
        giornata = giornata_block.get("giornata")
        risultato_map = giornata_block.get("risultatoModelloScommessaCampionatoMap", {})
        if not isinstance(risultato_map, dict):
            continue

        for _, model_list in risultato_map.items():
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

                    result_list = ev.get("risultatoScommessaUfficialeList", [])
                    if not isinstance(result_list, list):
                        result_list = []

                    home_team, away_team, event_name_raw, team_source = extract_teams(ev, result_list)
                    gol_gol = infer_gol_gol(result_list)

                    raw_markets = []
                    for rr in result_list[:15]:
                        market = rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or ""
                        result = rr.get("risultato") or rr.get("descrizioneEsito") or ""
                        raw_markets.append(f"{market}: {result}")

                    debug_event_fields = {
                        k: ev.get(k)
                        for k in ev.keys()
                        if any(token in k.lower() for token in ["desc", "event", "avven", "match", "team", "compet"])
                    }

                    matches.append({
                        "match_id": f"{date_str}-{codice_palinsesto}-{codice_avvenimento}",
                        "data": date_str,
                        "orario": data_ora,
                        "timestamp": f"{date_str} {data_ora}",
                        "giornata": giornata,
                        "home_team": home_team,
                        "away_team": away_team,
                        "match_name": f"{home_team} - {away_team}",
                        "descrizione_avvenimento": desc,
                        "event_name_raw": event_name_raw,
                        "team_source": team_source,
                        "gol_gol": gol_gol,
                        "markets_count": len(result_list),
                        "raw_markets": " | ".join(raw_markets),
                        "debug_event_fields": str(debug_event_fields)
                    })

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


def build_time_blocks(df):
    if df.empty:
        return pd.DataFrame(columns=["orario", "totale_partite", "gol_gol_si", "gol_gol_no", "non_classificate", "perc_gol_gol"])

    grouped = (
        df.groupby(["orario", "gol_gol"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    for col in ["SI", "NO", "N/D"]:
        if col not in grouped.columns:
            grouped[col] = 0

    grouped["totale_partite"] = grouped["SI"] + grouped["NO"] + grouped["N/D"]
    grouped["gol_gol_si"] = grouped["SI"]
    grouped["gol_gol_no"] = grouped["NO"]
    grouped["non_classificate"] = grouped["N/D"]
    grouped["perc_gol_gol"] = ((grouped["gol_gol_si"] / grouped["totale_partite"]) * 100).round(2)
    grouped = grouped.sort_values("orario", ascending=False)

    return grouped[["orario", "totale_partite", "gol_gol_si", "gol_gol_no", "non_classificate", "perc_gol_gol"]]


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
df = df.sort_values(["orario", "timestamp"], ascending=False)

valid_df = df[df["gol_gol"].isin(["SI", "NO"])].copy()
stats10 = build_stats(valid_df, 10)
stats25 = build_stats(valid_df, 25)
stats50 = build_stats(valid_df, 50)

c1, c2, c3 = st.columns(3)
c1.metric("GOL GOL ultime 10", f"{stats10['pct']}%", f"{stats10['gg']}/{stats10['count']}")
c2.metric("GOL GOL ultime 25", f"{stats25['pct']}%", f"{stats25['gg']}/{stats25['count']}")
c3.metric("GOL GOL ultime 50", f"{stats50['pct']}%", f"{stats50['gg']}/{stats50['count']}")

time_blocks = build_time_blocks(df)

st.subheader("Blocchi orari")
st.dataframe(time_blocks, use_container_width=True, hide_index=True)

if not time_blocks.empty:
    st.subheader("Grafico per blocchi orari")
    chart_blocks = time_blocks.set_index("orario")[["gol_gol_si", "gol_gol_no", "non_classificate"]]
    st.bar_chart(chart_blocks, height=320)

    st.subheader("Trend percentuale GOL GOL per orario")
    trend_blocks = time_blocks.set_index("orario")[["perc_gol_gol"]]
    st.line_chart(trend_blocks, height=280)

if not valid_df.empty:
    chart_df = valid_df.copy()
    chart_df = chart_df.iloc[::-1].reset_index(drop=True)
    chart_df["gol_gol_num"] = (chart_df["gol_gol"] == "SI").astype(int)
    chart_df["media_mobile_10"] = chart_df["gol_gol_num"].rolling(10, min_periods=1).mean() * 100
    st.subheader("Trend GOL GOL partita per partita")
    st.line_chart(chart_df[["gol_gol_num", "media_mobile_10"]], height=300)

st.subheader("Partite uscite GOL GOL (SI)")
st.dataframe(
    df[df["gol_gol"] == "SI"][["timestamp", "orario", "match_name", "home_team", "away_team", "team_source", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Partite uscite NO GOL GOL (NO)")
st.dataframe(
    df[df["gol_gol"] == "NO"][["timestamp", "orario", "match_name", "home_team", "away_team", "team_source", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Partite non ancora classificate (N/D)")
st.dataframe(
    df[df["gol_gol"] == "N/D"][["timestamp", "orario", "match_name", "home_team", "away_team", "descrizione_avvenimento", "event_name_raw", "team_source", "gol_gol", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

st.subheader("Storico completo")
st.dataframe(
    df[["timestamp", "orario", "giornata", "match_name", "home_team", "away_team", "team_source", "descrizione_avvenimento", "event_name_raw", "gol_gol", "markets_count", "raw_markets"]],
    use_container_width=True,
    hide_index=True
)

with st.expa
