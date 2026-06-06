import streamlit as st
import requests
import pandas as pd
from datetime import datetime

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
        ev.get('descrizioneAvventimento'),
        ev.get('descrizioneAvvenimento'),
        ev.get('descrizioneEvento'),
        ev.get('evento'),
        ev.get('match'),
        ev.get('avvenimento'),
        ev.get('nomeEvento'),
        ev.get('labelEvento'),
    ]

    for value in candidates:
        value = str(value or '').strip()
        if value:
            return value.replace(' ', '')
    return ''


def fetch_matches():
    date_str = datetime.now().strftime('%d-%m-%Y')
    api_url = f'https://betting.sisal.it/api/vrol-api/vrol/archivio/getArchivioGareCampionato/1/3/6/{date_str}'

    r = requests.get(
        api_url,
        timeout=30,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Referer': 'https://www.sisal.it/',
        },
    )
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

    last5 = int(grouped.head(5)['gol'].sum())
    prev5 = int(grouped.iloc[5:10]['gol'].sum()) if len(grouped) > 5 else 0
    last10 = int(grouped.head(10)['gol'].sum())
    prev10 = int(grouped.iloc[10:20]['gol'].sum()) if len(grouped) > 10 else 0
    latest_block_pct = float(grouped.iloc[0]['pct']) if not grouped.empty else 0.0

    return {
        'last5': last5,
        'prev5': prev5,
        'last10': last10,
        'prev10': prev10,
        'latest_block_pct': latest_block_pct,
    }


def build_all_gg_stats(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy()
    if valid_df.empty:
        return {
            'total_all_gg_blocks': 0,
            'latest_streak': 0,
            'blocks_table': pd.DataFrame(columns=['orario', 'GG', 'totale', 'all_gg_6su6'])
        }

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
            'rate_5': 0.0,
            'rate_10': 0.0,
            'rate_20': 0.0,
            'weighted_rate': 0.0,
            'next_block_expected': 0.0,
            'next_block_rounded': 0,
            'next_3_blocks_expected': 0.0,
            'range_min': 0,
            'range_max': 0,
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
        if subset.empty:
            return 0.0
        return float(subset['rate'].mean())

    rate_5 = mean_rate(5)
    rate_10 = mean_rate(10)
    rate_20 = mean_rate(20)

    weighted_rate = (0.5 * rate_5) + (0.3 * rate_10) + (0.2 * rate_20)
    weighted_rate = max(0.0, min(1.0, weighted_rate))

    matches_per_block = 6
    next_block_expected = round(weighted_rate * matches_per_block, 2)
    next_block_rounded = int(round(next_block_expected))
    next_3_blocks_expected = round(next_block_expected * 3, 2)

    range_min = max(0, int(round(next_block_expected - 1)))
    range_max = min(matches_per_block, int(round(next_block_expected + 1)))

    details = pd.DataFrame([
        {'finestra': 'Ultimi 5 blocchi', 'percentuale_GG': round(rate_5 * 100, 2)},
        {'finestra': 'Ultimi 10 blocchi', 'percentuale_GG': round(rate_10 * 100, 2)},
        {'finestra': 'Ultimi 20 blocchi', 'percentuale_GG': round(rate_20 * 100, 2)},
        {'finestra': 'Media pesata finale', 'percentuale_GG': round(weighted_rate * 100, 2)},
    ])

    return {
        'rate_5': rate_5,
        'rate_10': rate_10,
        'rate_20': rate_20,
        'weighted_rate': weighted_rate,
        'next_block_expected': next_block_expected,
        'next_block_rounded': next_block_rounded,
        'next_3_blocks_expected': next_3_blocks_expected,
        'range_min': range_min,
        'range_max': range_max,
        'details': details
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

st.subheader('Blocchi con 6 GG su 6')
all_gg_stats = build_all_gg_stats(df)
col4, col5 = st.columns(2)
col4.metric('Totale blocchi 6 su 6', all_gg_stats['total_all_gg_blocks'])
col5.metric('Serie aperta 6 su 6', all_gg_stats['latest_streak'])

with st.expander('Dettaglio blocchi 6 GG su 6', expanded=False):
    st.dataframe(all_gg_stats['blocks_tabl
