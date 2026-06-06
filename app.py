import re
from datetime import datetime, timedelta
from math import comb

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='FAS League Tracker', layout='wide')

st.title('FAS League Tracker')
st.caption("Archivio risultati Sisal con statistiche complete, grafici, container partite giorno per giorno, forecast su massimo 10 blocchi, predict Top-N e reset giornaliero dopo l'1:00")

TEAM_NAME_MAP = {
    'GEN': 'GEN', 'NAP': 'NAP', 'UDI': 'UDI', 'MIL': 'MIL', 'INT': 'INT', 'ROM': 'ROM',
    'FIO': 'FIO', 'LAZ': 'LAZ', 'SAM': 'SAM', 'ATA': 'ATA', 'VER': 'VER', 'JUV': 'JUV'
}


# -------------------------
# Utility tempo / reset
# -------------------------
def get_operational_datetime():
    now = datetime.now()
    if now.hour < 1:
        return now - timedelta(days=1)
    return now


def maybe_reset_daily_after_one():
    now = datetime.now()
    today = now.date().isoformat()
    current_hour = now.hour
    active_data_day = st.session_state.get('active_data_day')

    if active_data_day is None:
        st.session_state['active_data_day'] = get_operational_datetime().date().isoformat()
        return False

    if active_data_day != today and current_hour >= 1:
        st.session_state['matches'] = []
        st.session_state['last_update'] = '-'
        st.session_state['active_data_day'] = today
        st.session_state['reset_notice'] = f"Reset giornaliero eseguito automaticamente alle {now.strftime('%H:%M:%S')}."
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
        ev.get('descrizioneAvventimento'), ev.get('descrizioneAvvenimento'), ev.get('descrizioneEvento'),
        ev.get('evento'), ev.get('match'), ev.get('avvenimento'), ev.get('nomeEvento'), ev.get('labelEvento')
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


def fetch_matches():
    operational_dt = get_operational_datetime()
    date_str = operational_dt.strftime('%d-%m-%Y')
    api_url = f'https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}'
    r = requests.get(api_url, timeout=30, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://www.sisal.it/'
    })
    r.raise_for_status()
    data = r.json()
    matches = []
    if not isinstance(data, list):
        return matches, date_str
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
                    home_team, away_team = split_teams(desc)
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
                        'home_team': home_team,
                        'away_team': away_team,
                        'esito': esito,
                    })
    dedup = {}
    for m in matches:
        dedup[m['match_id']] = m
    results = list(dedup.values())
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    return results, date_str


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
            'rate_5': 0.0, 'rate_10': 0.0, 'weighted_rate': 0.0,
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
    weighted_rate = max(0.0, min(1.0, (0.6 * rate_5) + (0.4 * rate_10)))
    next_block_expected = round(weighted_rate * 6, 2)
    next_block_rounded = int(round(next_block_expected))
    next_3_blocks_expected = round(next_block_expected * 3, 2)
    range_min = max(0, int(round(next_block_expected - 1)))
    range_max = min(6, int(round(next_block_expected + 1)))
    details = pd.DataFrame([
        {'finestra': 'Ultimi 5 blocchi', 'percentuale_GG': round(rate_5 * 100, 2)},
        {'finestra': 'Ultimi 10 blocchi', 'percentuale_GG': round(rate_10 * 100, 2)},
        {'finestra': 'Media pesata finale', 'percentuale_GG': round(weighted_rate * 100, 2)},
    ])
    return {
        'rate_5': rate_5, 'rate_10': rate_10, 'weighted_rate': weighted_rate,
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
    grouped['rate'] = groupe
