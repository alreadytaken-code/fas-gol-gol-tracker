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
    DATA_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


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

        if "gol" in market:
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
    
