import re
from datetime import datetime, timedelta, timezone
from math import comb

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='FAS League Tracker', layout='wide')

st.title('FAS League Tracker')
st.caption(
    'Archivio risultati Sisal con giornate Sisal 1-22 senza duplicati, cicli distinti, '
    'forecast su blocchi da 6, ranking manuale GG/NG e reset giornaliero dopo l\'1:00'
)

LOCAL_TZ_OFFSET_HOURS = 1
MATCHES_PER_BLOCK = 6
MAX_GIORNATA = 22
REQUEST_TIMEOUT = 30

TEAM_NAME_MAP = {
    'GEN': 'GEN', 'NAP': 'NAP', 'UDI': 'UDI', 'MIL': 'MIL', 'INT': 'INT', 'ROM': 'ROM',
    'FIO': 'FIO', 'LAZ': 'LAZ', 'SAM': 'SAM', 'ATA': 'ATA', 'VER': 'VER', 'JUV': 'JUV'
}


# -------------------------
# Utility tempo / reset
# -------------------------
def local_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=LOCAL_TZ_OFFSET_HOURS)


def get_operational_datetime() -> datetime:
    now_utc = datetime.now(timezone.utc)
    local = now_utc + timedelta(hours=LOCAL_TZ_OFFSET_HOURS)
    if local.hour < 1:
        return local - timedelta(days=1)
    return local


def maybe_reset_daily_after_one() -> bool:
    now_utc = datetime.now(timezone.utc)
    local = now_utc + timedelta(hours=LOCAL_TZ_OFFSET_HOURS)
    today = local.date().isoformat()
    current_hour = local.hour
    active_data_day = st.session_state.get('active_data_day')

    if active_data_day is None:
        st.session_state['active_data_day'] = get_operational_datetime().date().isoformat()
        return False

    if active_data_day != today and current_hour >= 1:
        st.session_state['matches'] = []
        st.session_state['last_update'] = '-'
        st.session_state['active_data_day'] = today
        st.session_state['reset_notice'] = (
            f"Reset giornaliero eseguito automaticamente alle {local.strftime('%H:%M:%S')}."
        )
        return True

    return False


# -------------------------
# Storico / API Sisal
# -------------------------
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
        ev.get('descrizioneAvventimento'), ev.get('descrizioneAvvenimento'),
        ev.get('descrizioneEvento'), ev.get('evento'), ev.get('match'),
        ev.get('avvenimento'), ev.get('nomeEvento'), ev.get('labelEvento')
    ]
    for value in candidates:
        value = str(value or '').strip()
        if value:
            return value.replace(' ', '')
    return ''


def normalize_match_name(name):
    name = str(name or '').upper().strip()
    name = name.replace('-', ' ').replace('_', ' ')
    name = ' '.join(name.split())
    return name


def split_teams(match_name):
    cleaned = normalize_match_name(match_name)
    parts = cleaned.split(' ')
    if len(parts) >= 2:
        home = TEAM_NAME_MAP.get(parts[0], parts[0])
        away = TEAM_NAME_MAP.get(parts[1], parts[1])
        return home, away
    return cleaned, ''


def parse_datetime_fields(date_str, data_ora):
    raw = str(data_ora or '').strip()
    combined = f'{date_str} {raw}'.strip()
    dt = pd.to_datetime(combined, dayfirst=True, errors='coerce')
    if pd.isna(dt):
        return pd.NaT, raw[:5] if raw else ''
    return dt, dt.strftime('%H:%M')


def normalize_giornata_value(giornata):
    try:
        g = int(str(giornata).strip())
        if 1 <= g <= MAX_GIORNATA:
            return g
    except Exception:
        pass
    return None


def fetch_matches():
    operational_dt = get_operational_datetime()
    date_str = operational_dt.strftime('%d-%m-%Y')
    api_url = f'https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}'
    response = requests.get(
        api_url,
        timeout=REQUEST_TIMEOUT,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Referer': 'https://www.sisal.it/'
        }
    )
    response.raise_for_status()
    data = response.json()
    matches = []

    if not isinstance(data, list):
        return matches, date_str

    for giornata_block in data:
        giornata_api = normalize_giornata_value(giornata_block.get('giornata'))
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
                    home_team, away_team = split_teams(desc)
                    data_ora = str(ev.get('dataOra') or '').strip()
                    codice_palinsesto = str(ev.get('codicePalinsesto') or '').strip()
                    codice_avvenimento = str(ev.get('codiceAvvenimento') or '').strip()
                    result_list = ev.get('risultatoScommessaUfficialeList', [])
                    if not isinstance(result_list, list):
                        result_list = []
                    esito = infer_gol_gol(result_list)
                    dt_value, orario = parse_datetime_fields(date_str, data_ora)

                    matches.append({
                        'match_id': f'{date_str}-{codice_palinsesto}-{codice_avvenimento}',
                        'api_day': date_str,
                        'timestamp': dt_value,
                        'timestamp_str': f'{date_str} {data_ora}',
                        'orario': orario,
                        'giornata': giornata_api,
                        'codice_palinsesto': codice_palinsesto,
                        'codice_avvenimento': codice_avvenimento,
                        'descrizione_avventimento': desc,
                        'home_team': home_team,
                        'away_team': away_team,
                        'esito': esito,
                    })

    dedup = {}
    for m in matches:
        current = dedup.get(m['match_id'])
        if current is None:
            dedup[m['match_id']] = m
        else:
            current_score = (pd.notna(current['timestamp']), current['esito'] != 'N/D')
            new_score = (pd.notna(m['timestamp']), m['esito'] != 'N/D')
            if new_score >= current_score:
                dedup[m['match_id']] = m

    results = list(dedup.values())
    return results, date_str


# -------------------------
# Normalizzazione dataset
# -------------------------
def assign_cycle_ids(df):
    if df.empty:
        df['cycle_id'] = []
        return df

    cycle_ids = []
    current_cycle = 1
    prev_giornata = None

    for giornata in df['giornata'].tolist():
        if prev_giornata is not None and giornata is not None:
            if giornata < prev_giornata:
                current_cycle += 1
        cycle_ids.append(current_cycle)
        prev_giornata = giornata

    df = df.copy()
    df['cycle_id'] = cycle_ids
    return df


def assign_match_number_within_group(group):
    group = group.sort_values(
        by=['sort_timestamp', 'orario', 'codice_avvenimento', 'match_id'],
        ascending=[True, True, True, True],
        kind='stable'
    ).reset_index(drop=True)
    group['match_nel_blocco'] = range(1, len(group) + 1)
    return group


def prepare_matches_df(matches):
    base_columns = [
        'match_id', 'api_day', 'timestamp', 'timestamp_str', 'orario', 'giornata',
        'codice_palinsesto', 'codice_avvenimento', 'descrizione_avventimento',
        'home_team', 'away_team', 'esito'
    ]
    if not matches:
        return pd.DataFrame(columns=base_columns + [
            'sort_timestamp', 'cycle_id', 'group_key', 'group_label', 'match_nel_blocco'
        ])

    df = pd.DataFrame(matches).copy()
    for col in base_columns:
        if col not in df.columns:
            df[col] = None

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    fallback_time = pd.to_datetime(df['timestamp_str'], dayfirst=True, errors='coerce')
    df['sort_timestamp'] = df['timestamp'].fillna(fallback_time)
    df['giornata'] = df['giornata'].apply(normalize_giornata_value)
    df['orario'] = df['orario'].fillna('').astype(str)
    df['codice_avvenimento'] = df['codice_avvenimento'].fillna('').astype(str)
    df['descrizione_avventimento'] = df['descrizione_avventimento'].fillna('').astype(str)

    df = df.dropna(subset=['giornata']).copy()
    df['giornata'] = df['giornata'].astype(int)

    df = df.sort_values(
        by=['sort_timestamp', 'giornata', 'orario', 'codice_avvenimento', 'match_id'],
        ascending=[True, True, True, True, True],
        kind='stable'
    ).reset_index(drop=True)

    df = assign_cycle_ids(df)
    df['group_key'] 
