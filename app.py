import re
from datetime import datetime
from math import comb

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='FAS League Tracker', layout='wide')

st.title('FAS League Tracker')
st.caption('Archivio risultati Sisal con forecast blocchi, backtest e ranking GG manuale con trend storico dominante')


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
        'alert_level': alert_level,
        'alert_message': msg,
    }


# -------------------------
# Ranking manuale con trend all'80%
# -------------------------
def clean_decimal(val):
    try:
        val = str(val).replace(',', '.').strip()
        return float(val)
    except Exception:
        return None


def implied_probability_from_odds(odds):
    if odds is None or odds <= 1:
        return None
    return 1 / odds


def score_label(score):
    if score >= 0.62:
        return 'Alta'
    if score >= 0.52:
        return 'Media'
    return 'Bassa'


def ranking_bonus(home_rank, away_rank):
    if home_rank is None or away_rank is None:
        return 0.0
    diff = abs(home_rank - away_rank)
    avg_rank = (home_rank + away_rank) / 2
    bonus = 0.0
    if diff <= 2:
        bonus += 0.03
    elif diff <= 5:
        bonus += 0.015
    elif diff >= 12:
        bonus -= 0.03
    if avg_rank <= 6:
        bonus += 0.01
    if avg_rank >= 14:
        bonus += 0.005
    return bonus


def get_current_trend_score(df):
    valid_df = df[df['esito'].isin(['GOL', 'NO GOL'])].copy() if not df.empty else pd.DataFrame()
    if valid_df.empty:
        return {
            'rate_5': 0.0,
            'rate_10': 0.0,
            'rate_20': 0.0,
            'trend_score': 0.0,
            'momentum_bonus': 0.0,
            'expected_total_rate': 0.0,
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
    trend_score = (0.5 * rate_5) + (0.3 * rate_10) + (0.2 * rate_20)

    momentum_bonus = 0.0
    if rate_5 > rate_10:
        momentum_bonus = min(0.03, (rate_5 - rate_10) * 0.25)
    elif rate_5 < rate_10:
        momentum_bonus = max(-0.03, (rate_5 - rate_10) * 0.25)

    trend_score = max(0.0, min(1.0, trend_score + momentum_bonus))
    return {
        'rate_5': rate_5,
        'rate_10': rate_10,
        'rate_20': rate_20,
        'trend_score': trend_score,
        'momentum_bonus': momentum_bonus,
        'expected_total_rate': trend_score,
    }


def parse_text_lines(raw_text):
    rows = []
    pattern = re.compile(r'^(.*?)\s+([0-9]+[\.,][0-9]+)\s+([0-9]{1,2})\s+([0-9]{1,2})$')
    for line in raw_text.splitlines():
        line = ' '.join(line.strip().split())
        if not line:
            continue
        m = pattern.match(line)
        if m:
            rows.append({
                'match': m.group(1),
                'quota_gg': clean_decimal(m.group(2)),
                'rank_home': int(m.group(3)),
                'rank_away': int(m.group(4)),
            })
    return pd.DataFrame(rows)


def build_match_ranking(input_df, trend_info):
    if input_df.empty:
        return pd.DataFrame(columns=[
            'match', 'quota_gg', 'prob_mercato', 'trend_score', 'bonus_classifica',
            'rank_home', 'rank_away', 'score_finale', 'fascia'
        ])

    df = input_df.copy()
    df['prob_mercato'] = df['quota_gg'].apply(implied_probability_from_odds)
    df['bonus_classifica'] = df.apply(lambda r: ranking_bonus(r['rank_home'], r['rank_away']), axis=1)
    df['trend_score'] = trend_info['trend_score']
    df['score_finale'] = (
        (0.80 * df['trend_score']) +
        (0.15 * df['prob_mercato'].fillna(0)) +
        (0.05 * df['bonus_classifica'].clip(lower=-0.05, upper=0.05))
    ).clip(lower=0, upper=0.95)
    df['fascia'] = df['score_finale'].apply(score_label)
    df = df.sort_values(['score_finale', 'prob_mercato'], ascending=False)
    return df[[
        'match', 'quota_gg', 'prob_mercato', 'trend_score', 'bonus_classifica',
        'rank_home', 'rank_away', 'score_finale', 'fascia'
    ]]


def build_manual_summary(ranking_df):
    if ranking_df.empty:
        return {
            'matches_count': 0,
            'expected_gg_total': 0.0,
            'expected_gg_rounded': 0,
            'high_band_count': 0,
            'medium_plus_count': 0,
        }
    expected_total = float(ranking_df['score_finale'].sum())
    return {
        'matches_count': int(len(ranking_df)),
        'expected_gg_total': round(expected_total, 2),
        'expected_gg_rounded': int(round(expected_total)),
        'high_band_count': int((ranking_df['fascia'] == 'Alta').sum()),
        'medium_plus_count': int(ranking_df['fascia'].isin(['Alta', 'Media']).sum()),
    }


# -------------------------
# UI principale storico
# -------------------------
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

df = pd.DataFrame(matches) if matches else pd.DataFrame(columns=['orario', 'timestamp', 'esito'])
if not df.empty:
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
else:
    st.info("Premi 'Aggiorna risultati' per caricare i dati storici del giorno. Il ranking manuale userà questo trend come motore principale.")


# -------------------------
# UI ranking manuale
# -------------------------
st.divider()
st.subheader('Ranking GG da input manuale con trend storico all\'80%')
st.caption('Inserisci una riga per partita nel formato: NomePartita quotaGG rankCasa rankTrasferta')
st.caption('Esempio: Alpha-Beta 1.75 4 6')

trend_info = get_current_trend_score(df)
t1, t2, t3, t4, t5 = st.columns(5)
t1.metric('Trend rate ultimi 5', f"{trend_info['rate_5']:.1%}")
t2.metric('Trend rate ultimi 10', f"{trend_info['rate_10']:.1%}")
t3.metric('Trend rate ultimi 20', f"{trend_info['rate_20']:.1%}")
t4.metric('Trend score attivo', f"{trend_info['trend_score']:.1%}")
t5.metric('Momentum trend', f"{trend_info['momentum_bonus']:.1%}")

raw_text = st.text_area(
    'Inserimento manuale partite',
    height=220,
    placeholder='Alpha-Beta 1.75 4 6\nGamma-Delta 1.92 8 10\nEpsilon-Zeta 2.05 3 14'
)

parsed_df = parse_text_lines(raw_text) if raw_text.strip() else pd.DataFrame(columns=['match', 'quota_gg', 'rank_home', 'rank_away'])

if not raw_text.strip():
    st.info('Inserisci le righe manualmente per ottenere il ranking GG con trend storico dominante.')
elif parsed_df.empty:
    st.error('Nessuna riga riconosciuta. Controlla il formato: NomePartita quotaGG rankCasa rankTrasferta')
else:
    ranking_df = build_match_ranking(parsed_df, trend_info)
    summary = build_manual_summary(ranking_df)

    st.markdown('### Sintesi attesa totale')
    s1, s2, s3, s4 = st.columns(4)
    s1.metric('Partite inserite', summary['matches_count'])
    s2.metric('GG attesi totali', summary['expected_gg_total'])
    s3.metric('GG attesi arrotondati', summary['expected_gg_rounded'])
    s4.metric('Match fascia Alta', summary['high_band_count'])
    st.caption(f"Match in fascia Alta o Media: {summary['medium_plus_count']}")

    st.markdown('### Partite riconosciute')
    st.dataframe(parsed_df, use_container_width=True, hide_index=True)

    st.markdown('### Ranking finale GG')
    top1, top2, top3 = st.columns(3)
    top_row = ranking_df.iloc[0]
    top1.metric('Top match GG', str(top_row['match']))
    top2.metric('Score finale top', f"{top_row['score_finale']:.3f}")
    top3.metric('Probabilità mercato top', f"{top_row['prob_mercato']:.1%}")

    display_df = ranking_df.copy()
    display_df['prob_mercato'] = (display_df['prob_mercato'] * 100).round(2)
    display_df['trend_score'] = (display_df['trend_score'] * 100).round(2)
    display_df['bonus_classifica'] = (display_df['bonus_classifica'] * 100).round(2)
    display_df['score_finale'] = (display_df['score_finale'] * 100).round(2)
    display_df.columns = [
        'Match', 'Quota GG', 'Prob. mercato %', 'Trend score %', 'Bonus classifica %',
        'Rank casa', 'Rank trasferta', 'Score finale %', 'Fascia'
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    chart_df = ranking_df.set_index('match')[['score_finale']]
    st.bar_chart(chart_df, height=320)

    with st.expander('Formula ranking usata', expanded=False):
        st.write('Score finale = 80% trend storico + 15% probabilità mercato + 5% bonus classifica.')
        st.write('Trend storico = 50% rate ultimi 5 blocchi + 30% rate ultimi 10 blocchi + 20% rate ultimi 20 blocchi, con correttivo momentum.')
        st.write('GG attesi totali = somma degli score finali delle partite inserite.')
        st.write('Bonus classifica:')
        st.write('- differenza classifica <= 2: +3%')
        st.write('- differenza classifica <= 5: +1.5%')
        st.write('- differenza classifica >= 12: -3%')
        st.write('- media classifica <= 6: +1%')
        st.write('- media classifica >= 14: +0.5%')
