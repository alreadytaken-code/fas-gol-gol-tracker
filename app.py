import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="FAS League Tracker", layout="wide")

st.title("FAS League Tracker")
st.caption("Archivio risultati Sisal con focus GOL / NO GOL")


def infer_gol_gol(result_list):
    for rr in result_list:
        market = str(rr.get("descrizioneScommessa") or rr.get("modelloScommessa") or "").lower()
        result = str(rr.get("risultato") or rr.get("descrizioneEsito") or "").lower()

        if "goal/no goal" in market or "gol/no gol" in market:
            if "+ goal" in result or result.strip() in ["goal", "gol", "gg"]:
                return "GOL"
            if "+ no goal" in result or "+ no gol" in result or result.strip() in ["no goal", "no gol", "nogol", "ng"]:
                return "NO GOL"
    return "N/D"


def get_event_description(ev):
    candidates = [
        ev.get("descrizioneAvventimento"),
        ev.get("descrizioneAvvenimento"),
        ev.get("descrizioneEvento"),
        ev.get("evento"),
        ev.get("match"),
        ev.get("avvenimento"),
        ev.get("nomeEvento"),
        ev.get("labelEvento"),
    ]

    for value in candidates:
        value = str(value or "").strip()
        if value:
            return value.replace(" ", "")
    return ""


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
                    desc = get_event_description(ev)
                    data_ora = str(ev.get("dataOra") or "").strip()
                    codice_palinsesto = str(ev.get("codicePalinsesto") or "").strip()
                    codice_avvenimento = str(ev.get("codiceAvvenimento") or "").strip()

                    result_list = ev.get("risultatoScommessaUfficialeList", [])
                    if not isinstance(result_list, list):
                        result_list = []

                    esito = infer_gol_gol(result_list)

                    matches.append({
                        "match_id": f"{date_str}-{codice_palinsesto}-{codice_avvenimento}",
                        "timestamp": f"{date_str} {data_ora}",
                        "orario": data_ora,
                        "giornata": giornata,
                        "descrizione_avventimento": desc,
                        "esito": esito,
                    })

    dedup = {}
    for m in matches:
        dedup[m["match_id"]] = m

    results = list(dedup.values())
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results


def build_blocks(df):
    if df.empty:
        return pd.DataFrame(columns=["orario", "GOL", "% sul totale"])

    grouped = df.groupby("orario").agg(
        totale=("esito", "count"),
        GOL=("esito", lambda x: (x == "GOL").sum())
    ).reset_index()

    grouped["% sul totale"] = ((grouped["GOL"] / grouped["totale"]) * 100).round(2)
    grouped = grouped.sort_values("orario", ascending=False)

    return grouped[["orario", "GOL", "% sul totale"]]


def build_stats_20(df):
    valid_df = df[df["esito"].isin(["GOL", "NO GOL"])].copy()
    if valid_df.empty:
        return []

    stats = []
    total_rows = len(valid_df)

    for start in range(0, total_rows, 20):
        chunk = valid_df.iloc[start:start + 20].copy()
        gol_count = int((chunk["esito"] == "GOL").sum())
        no_gol_count = int((chunk["esito"] == "NO GOL").sum())

        label = f"Partite {start + 1}-{start + len(chunk)}"
        stats.append({
            "label": label,
            "gol": gol_count,
            "no_gol": no_gol_count,
        })

    return stats


if st.button("Aggiorna risultati", type="primary"):
    try:
        matches = fetch_matches()
        st.session_state["matches"] = matches
        st.session_state["last_update"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        st.success(f"Partite trovate: {len(matches)}")
    except Exception as e:
        st.error(f"Errore API: {e}")

matches = st.session_state.get("matches", [])
last_update = st.session_state.get("last_update", "-")

if not matches:
    st.info("Premi 'Aggiorna risultati' per caricare i dati.")
    st.stop()

df = pd.DataFrame(matches)
df = df.sort_values(["orario", "timestamp"], ascending=False)

st.markdown(f"**Ultimo aggiornamento:** {last_update}")

st.subheader("Statistiche ogni 20 partite")
stats_20 = build_stats_20(df)

if stats_20:
    visible_stats = stats_20[:4]
    cols = st.columns(len(visible_stats))
    for i, stat in enumerate(visible_stats):
        cols[i].metric(stat["label"], f"GOL {stat['gol']}", f"NO GOL {stat['no_gol']}")
else:
    st.info("Nessuna statistica disponibile.")

st.subheader("Storico risultati")
storico_df = df[["orario", "giornata", "descrizione_avventimento", "esito"]].copy()
storico_df = storico_df.sort_values(["orario", "giornata"], ascending=[False, False])

orari_unici = storico_df["orario"].dropna().unique().tolist()

for i, ora in enumerate(orari_unici):
    blocco = storico_df[storico_df["orario"] == ora].copy()
    st.markdown(f"### Blocco {ora}")
    st.dataframe(
        blocco[["orario", "giornata", "descrizione_avventimento", "esito"]],
        use_container_width=True,
        hide_index=True,
    )

    if i < len(orari_unici) - 1:
        st.divider()

st.subheader("Blocchi orari")
blocks_df = build_blocks(df)
st.dataframe(blocks_df, use_container_width=True, hide_index=True)

if not blocks_df.empty:
    st.subheader("Grafico blocchi orari")
    bar_df = blocks_df.set_index("orario")[["GOL"]]
    st.bar_chart(bar_df, height=320)

    st.subheader("Trend percentuale")
    trend_df = blocks_df.set_index("orario")[["% sul totale"]]
    st.line_chart(trend_df, height=280)
