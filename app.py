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
