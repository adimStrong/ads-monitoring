"""
KPI Monitoring Dashboard
Auto-calculates advertising KPI scores from P-tab data.
Manual KPIs can be scored via input fields per agent.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
from channel_data_loader import (
    load_agent_performance_data,
    refresh_agent_performance_data,
    calculate_kpi_scores,
    load_updated_accounts_data,
    refresh_updated_accounts_data,
    write_kpi_scores_to_sheet,
    load_created_assets_data,
    refresh_created_assets_data,
    count_created_assets,
    load_ab_testing_data,
    refresh_ab_testing_data,
    count_ab_testing,
    get_available_months,
    month_to_label,
    score_kpi,
    month_to_date_range,
)
import os
import requests as http_requests
from config import (
    AGENT_PERFORMANCE_TABS,
    KPI_SCORING,
    KPI_MANUAL,
    KPI_ORDER,
    KPI_PHP_USD_RATE,
    EXCLUDED_FROM_REPORTING,
    SIDEBAR_HIDE_CSS,
)

# Railway Chat Listener API config
CHAT_API_URL = os.getenv("CHAT_API_URL", "https://humble-illumination-production-713f.up.railway.app")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "juan365chat")

ALL_KPIS = {**KPI_SCORING, **KPI_MANUAL}
MANUAL_KEYS = list(KPI_MANUAL.keys())

PARAM_TEXT = {
    'cpa': '4: <=$9.99 | 3: $10-$13.99 | 2: $14-$15 | 1: >$15',
    'roas': '4: >0.40x | 3: 0.20-0.39x | 2: 0.10-0.19x | 1: <0.10x',
    'cvr': '4: 7-9% | 3: 4-6% | 2: 2-3% | 1: <2%',
    'campaign_setup': '4: 95-97% | 3: 90-94% | 2: 85-89% | 1: <85%',
    'ctr': '4: 3-4% | 3: 2-2.9% | 2: 1-1.9% | 1: <0.9%',
    'ab_testing': '4: >=20 published | 3: 11-19 | 2: 6-10 | 1: <6 (auto from Text/AbTest)',
    'reporting': '4: <15min | 3: 15-24min | 2: 25-34min | 1: 35+min (auto from Telegram)',
    'data_insights': '4: Excellent | 3: Good | 2: Fair | 1: Poor',
    'account_dev': '4: >=5 gmail+fb | 3: 3-4 | 2: 2 | 1: <2 (auto from Created Assets)',
    'collaboration': '4: Excellent | 3: Good | 2: Fair | 1: Poor',
    'communication': '4: Excellent | 3: Good | 2: Fair | 1: Poor',
}


def score_color(score):
    if score >= 4:
        return "#22c55e"
    elif score >= 3:
        return "#eab308"
    elif score >= 2:
        return "#f97316"
    return "#ef4444"


def score_badge(score):
    if score == 0:
        return '<span style="color:#64748b">-</span>'
    color = score_color(score)
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold">{int(score)}</span>'


def get_manual_score(agent, key, key_prefix="km"):
    """Get manual score from session state."""
    ss_key = f"{key_prefix}_manual_scores"
    scores = st.session_state.get(ss_key, {})
    return scores.get(f"{agent}_{key}", 0)


def calc_manual_weighted(agent, key_prefix="km"):
    """Calculate total manual weighted score for an agent."""
    total = 0
    for key, info in KPI_MANUAL.items():
        score = get_manual_score(agent, key, key_prefix)
        if score > 0 and info['weight'] > 0:
            total += score * info['weight']
    return round(total, 2)


def calc_auto_weighted(agent_scores):
    """Calculate total auto weighted score."""
    total = 0
    for key in KPI_SCORING:
        s = agent_scores.get(key, {}).get('score', 0)
        w = KPI_SCORING[key]['weight']
        if w > 0:
            total += s * w
    return round(total, 2)


def calculate_kpi_from_daily(daily_df, agent_name, date_from, date_to, created_assets_data=None, ab_testing_data=None, reporting_data=None):
    """Calculate KPI scores from filtered daily data for a custom date range.
    Aggregates daily rows into a single period, then scores each metric.
    """
    scores = {}
    agent_daily = daily_df[daily_df['agent'] == agent_name].copy()
    if agent_daily.empty or 'date' not in agent_daily.columns:
        for key in KPI_SCORING:
            if key in ('account_dev', 'ab_testing', 'reporting'):
                continue
            scores[key] = {'score': 0, 'value': 0, 'name': KPI_SCORING[key]['name']}
    else:
        agent_daily['date_dt'] = pd.to_datetime(agent_daily['date'], errors='coerce')
        agent_daily = agent_daily[(agent_daily['date_dt'] >= pd.Timestamp(date_from)) &
                                  (agent_daily['date_dt'] <= pd.Timestamp(date_to))]
        if agent_daily.empty:
            for key in KPI_SCORING:
                if key in ('account_dev', 'ab_testing', 'reporting'):
                    continue
                scores[key] = {'score': 0, 'value': 0, 'name': KPI_SCORING[key]['name']}
        else:
            cost = agent_daily['cost'].sum()
            register = agent_daily['register'].sum()
            ftd = agent_daily['ftd'].sum()
            impressions = agent_daily['impressions'].sum()
            clicks = agent_daily['clicks'].sum()

            # ARPPU: last non-zero
            arppu_col = pd.to_numeric(agent_daily['arppu'], errors='coerce').fillna(0)
            nonzero = arppu_col[arppu_col > 0]
            arppu = nonzero.iloc[-1] if len(nonzero) > 0 else 0

            cpa = cost / ftd if ftd > 0 else 0
            s, v = score_kpi('cpa', cpa)
            scores['cpa'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['cpa']['name']}

            cpd = cost / ftd if ftd > 0 else 0
            try:
                roas = arppu / KPI_PHP_USD_RATE / cpd if (cpd > 0 and arppu > 0) else 0
            except:
                roas = 0
            s, v = score_kpi('roas', roas)
            scores['roas'] = {'score': s, 'value': round(v, 4), 'name': KPI_SCORING['roas']['name']}

            cvr = (ftd / register * 100) if register > 0 else 0
            s, v = score_kpi('cvr', cvr)
            scores['cvr'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['cvr']['name']}

            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            s, v = score_kpi('ctr', ctr)
            scores['ctr'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['ctr']['name']}

    # Account Dev, AB Testing, Reporting — use date range
    from channel_data_loader import count_created_assets as _count_ca, count_ab_testing as _count_ab, score_account_dev, score_ab_testing
    kpi_date_range = (pd.Timestamp(date_from), pd.Timestamp(date_to))
    agent_upper = agent_name.upper()

    asset_counts = {}
    if created_assets_data is not None and not created_assets_data.empty:
        asset_counts = _count_ca(created_assets_data, date_range=kpi_date_range).get(agent_upper, {})
    acct_total = asset_counts.get('total_accounts', 0)
    scores['account_dev'] = {
        'score': score_account_dev(acct_total), 'value': acct_total,
        'name': KPI_SCORING['account_dev']['name'],
        'gmail': asset_counts.get('gmail', 0), 'fb_accounts': asset_counts.get('fb_accounts', 0),
    }

    ab_counts = {}
    if ab_testing_data is not None:
        ab_counts = _count_ab(ab_testing_data, date_range=kpi_date_range).get(agent_upper, {})
    ab_published = ab_counts.get('published_ad', 0)
    scores['ab_testing'] = {
        'score': score_ab_testing(ab_published), 'value': ab_published,
        'name': KPI_SCORING['ab_testing']['name'],
        'primary_text': ab_counts.get('primary_text', 0), 'published_ad': ab_published,
    }

    # Reporting
    rep_score = rep_avg_min = rep_count = 0
    if reporting_data and agent_name in reporting_data:
        ri = reporting_data[agent_name]
        rep_score, rep_avg_min, rep_count = ri.get('score', 0), ri.get('avg_minute', 0), ri.get('report_count', 0)
    scores['reporting'] = {
        'score': rep_score, 'value': rep_avg_min,
        'name': KPI_SCORING['reporting']['name'],
        'avg_minute': rep_avg_min, 'report_count': rep_count,
    }

    return scores


def render_content(key_prefix="km"):
    """Render KPI Monitoring content. key_prefix avoids widget key conflicts when embedded in tabs."""

    # Initialize session state for manual scores
    ss_manual = f"{key_prefix}_manual_scores"
    if ss_manual not in st.session_state:
        st.session_state[ss_manual] = {}

    # Filter agents excluded from reporting
    KPI_AGENTS = [t for t in AGENT_PERFORMANCE_TABS if t['agent'].upper() not in EXCLUDED_FROM_REPORTING]
    agent_names = ["All Agents"] + [t['agent'] for t in KPI_AGENTS]

    # Controls row (moved from sidebar)
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 1])
    with ctrl_col1:
        selected_agent = st.selectbox("Agent", agent_names, key=f"{key_prefix}_agent")
    # Load P-tab data
    ptab_data = load_agent_performance_data()
    monthly_df = ptab_data.get('monthly', pd.DataFrame()) if ptab_data else pd.DataFrame()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()

    # Month selector
    available_months = get_available_months(monthly_df)
    if available_months:
        month_options = available_months
        month_labels = [month_to_label(m) for m in month_options]
        with ctrl_col2:
            selected_month_idx = st.selectbox(
                "Month",
                range(len(month_options)),
                index=len(month_options) - 1,
                format_func=lambda i: month_labels[i],
                key=f"{key_prefix}_month",
            )
        selected_month = month_options[selected_month_idx]
        selected_month_label = month_labels[selected_month_idx]
    else:
        selected_month = None
        selected_month_label = "N/A"

    with ctrl_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh Data", type="primary", key=f"{key_prefix}_refresh"):
            refresh_agent_performance_data()
            refresh_updated_accounts_data()
            refresh_created_assets_data()
            refresh_ab_testing_data()
            st.rerun()

    # Date range filter (optional — overrides month selector when enabled)
    use_date_range = False
    date_from = date_to = None
    with st.expander("Custom Date Range Filter", expanded=False):
        st.caption("When enabled, KPI scores are calculated from daily data within this date range (overrides month selector for CPA/ROAS/CVR/CTR).")
        dr_col1, dr_col2, dr_col3 = st.columns([2, 2, 1])
        # Default: start/end of selected month
        if selected_month:
            m_start, m_end = month_to_date_range(selected_month)
            default_from = m_start.date()
            default_to = m_end.date()
        else:
            default_from = date.today().replace(day=1)
            default_to = date.today()
        with dr_col1:
            date_from = st.date_input("From", value=default_from, key=f"{key_prefix}_dr_from")
        with dr_col2:
            date_to = st.date_input("To", value=default_to, key=f"{key_prefix}_dr_to")
        with dr_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            use_date_range = st.checkbox("Enable", key=f"{key_prefix}_dr_enable")

    if use_date_range and date_from and date_to:
        selected_month_label = f"{date_from.strftime('%b %d')} – {date_to.strftime('%b %d, %Y')}"

    # Load Updated Accounts data (kept for backward compat)
    accounts_data = load_updated_accounts_data()

    # Load Created Assets data for Account Dev scoring
    created_assets_data = load_created_assets_data()

    # Load A/B Testing data
    ab_testing_data = load_ab_testing_data()

    # Fetch reporting scores - pass month param if selected
    try:
        report_params = {'key': CHAT_API_KEY}
        if selected_month:
            report_params['month'] = selected_month
        resp = http_requests.get(f"{CHAT_API_URL}/api/reporting", params=report_params, timeout=10)
        resp.raise_for_status()
        chat_reporting = resp.json()
    except Exception:
        chat_reporting = {}

    # Calculate live auto scores from P-tab + Created Assets + AB Testing + Reporting
    live_scores = {}
    for tab_info in AGENT_PERFORMANCE_TABS:
        agent = tab_info['agent']
        if use_date_range and date_from and date_to:
            live_scores[agent] = calculate_kpi_from_daily(
                daily_df, agent, date_from, date_to,
                created_assets_data=created_assets_data,
                ab_testing_data=ab_testing_data,
                reporting_data=chat_reporting,
            )
        else:
            live_scores[agent] = calculate_kpi_scores(
                monthly_df, agent, daily_df=daily_df,
                accounts_data=accounts_data,
                created_assets_data=created_assets_data,
                ab_testing_data=ab_testing_data,
                reporting_data=chat_reporting,
                month_filter=selected_month,
            )

    # ============================================================
    # ALL AGENTS VIEW
    # ============================================================
    if selected_agent == "All Agents":
        st.subheader(f"Team KPI Overview - {selected_month_label}")
        st.markdown(f"**ROAS Formula:** `ARPPU / {KPI_PHP_USD_RATE} / Cost_per_FTD`")

        rows = []
        for tab_info in KPI_AGENTS:
            agent = tab_info['agent']
            s = live_scores.get(agent, {})

            cpa_s = s.get('cpa', {}).get('score', 0)
            roas_s = s.get('roas', {}).get('score', 0)
            cvr_s = s.get('cvr', {}).get('score', 0)
            ctr_s = s.get('ctr', {}).get('score', 0)
            acct_s = s.get('account_dev', {}).get('score', 0)
            ab_s = s.get('ab_testing', {}).get('score', 0)
            rep_s = s.get('reporting', {}).get('score', 0)

            cpa_v = s.get('cpa', {}).get('value', 0)
            roas_v = s.get('roas', {}).get('value', 0)
            cvr_v = s.get('cvr', {}).get('value', 0)
            ctr_v = s.get('ctr', {}).get('value', 0)
            acct_v = s.get('account_dev', {}).get('value', 0)
            ab_v = s.get('ab_testing', {}).get('value', 0)
            rep_count = s.get('reporting', {}).get('report_count', 0)
            rep_min = s.get('reporting', {}).get('avg_minute', 0)

            auto_wt = calc_auto_weighted(s)
            manual_wt = calc_manual_weighted(agent, key_prefix)
            total_wt = round(auto_wt + manual_wt, 2)

            rows.append({
                'Agent': agent,
                'CPA': f"${cpa_v:.2f}" if cpa_v > 0 else "-",
                'CPA Score': cpa_s,
                'ROAS': f"{roas_v:.4f}x" if roas_v > 0 else "-",
                'ROAS Score': roas_s,
                'CVR': f"{cvr_v:.1f}%" if cvr_v > 0 else "-",
                'CVR Score': cvr_s,
                'CTR': f"{ctr_v:.2f}%" if ctr_v > 0 else "-",
                'CTR Score': ctr_s,
                'Acct': f"{int(acct_v)}" if acct_v > 0 else "-",
                'Acct Score': acct_s,
                'AB': f"{int(ab_v)}" if ab_v > 0 else "-",
                'AB Score': ab_s,
                'Rep': f"{rep_min:.0f}m ({rep_count})" if rep_count > 0 else "-",
                'Rep Score': rep_s,
                'Auto': auto_wt,
                'Manual': manual_wt,
                'Total': total_wt,
            })

        summary_df = pd.DataFrame(rows)

        # HTML table with all columns including Account Dev, Profile Dev and Reporting
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += '<tr style="background:#1e293b;color:#fff">'
        for col in ['Agent', 'CPA', 'Score', 'ROAS', 'Score', 'CVR', 'Score', 'CTR', 'Score', 'Acct', 'Score', 'A/B', 'Score', 'Report', 'Score', 'Auto', 'Manual', 'Total']:
            html += f'<th style="padding:6px;text-align:center;border:1px solid #334155">{col}</th>'
        html += '</tr>'

        for _, r in summary_df.iterrows():
            html += '<tr style="background:#0f172a;color:#e2e8f0;border:1px solid #334155">'
            html += f'<td style="padding:5px;font-weight:bold;border:1px solid #334155;color:#f1f5f9">{r["Agent"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{r["CPA"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["CPA Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{r["ROAS"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["ROAS Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{r["CVR"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["CVR Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{r["CTR"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["CTR Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155;font-size:12px">{r["Acct"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["Acct Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155;font-size:12px">{r["AB"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["AB Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155;font-size:12px">{r["Rep"]}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{score_badge(r["Rep Score"])}</td>'
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155">{r["Auto"]}</td>'
            m = r["Manual"]
            m_color = "#22c55e" if m > 0 else "#64748b"
            html += f'<td style="padding:5px;text-align:center;border:1px solid #334155;color:{m_color}">{m}</td>'
            t = r["Total"]
            t_color = "#22c55e" if t >= 2.0 else "#eab308" if t >= 1.5 else "#f97316" if t >= 1.0 else "#ef4444"
            html += f'<td style="padding:5px;text-align:center;font-weight:bold;border:1px solid #334155;color:{t_color}">{t}</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

        # Calculation explanation using Streamlit expander for clean layout
        with st.expander("How is the Total KPI Score calculated?", expanded=False):
            st.markdown("""
Each KPI is scored **1 to 4**, then multiplied by its **weight**.
**Total = sum of all weighted scores. Maximum = 4.00**
""")
            st.markdown("#### AUTO KPIs (75% = max 3.00)")
            auto_explain = pd.DataFrame([
                {"KPI": "CPA", "Weight": "12.5%", "Formula": "Cost / FTD", "4 (Best)": "<=$9.99", "3": "$10-$13.99", "2": "$14-$15", "1 (Worst)": ">$15"},
                {"KPI": "ROAS", "Weight": "12.5%", "Formula": "ARPPU / 57.7 / CPD", "4 (Best)": ">=0.40x", "3": "0.20-0.399x", "2": "0.10-0.199x", "1 (Worst)": "<0.10x"},
                {"KPI": "CVR", "Weight": "15%", "Formula": "FTD / Register x100", "4 (Best)": ">=7%", "3": "4-6.99%", "2": "2-3.99%", "1 (Worst)": "<2%"},
                {"KPI": "CTR", "Weight": "7.5%", "Formula": "Clicks / Impressions x100", "4 (Best)": ">=3%", "3": "2-2.99%", "2": "1-1.99%", "1 (Worst)": "<1%"},
                {"KPI": "Account Dev", "Weight": "10%", "Formula": "Gmail + FB accounts", "4 (Best)": ">=5", "3": "3-4", "2": "2", "1 (Worst)": "<2"},
                {"KPI": "A/B Testing", "Weight": "7.5%", "Formula": "Published ads count", "4 (Best)": ">=20", "3": "11-19", "2": "6-10", "1 (Worst)": "<6"},
                {"KPI": "Reporting", "Weight": "10%", "Formula": "Avg min after hour", "4 (Best)": "<15 min", "3": "15-24 min", "2": "25-34 min", "1 (Worst)": "35+ min"},
            ])
            st.dataframe(auto_explain, hide_index=True, use_container_width=True)

            st.markdown("#### MANUAL KPIs (25% = max 1.00)")
            manual_explain = pd.DataFrame([
                {"KPI": "Campaign Setup Accuracy", "Weight": "15%", "Scored By": "Manager (1-4)"},
                {"KPI": "Collaboration", "Weight": "10%", "Scored By": "Manager (1-4)"},
            ])
            st.dataframe(manual_explain, hide_index=True, use_container_width=True)

            st.markdown("""
#### Example Calculation
If agent scores: CPA=3, ROAS=3, CVR=4, CTR=4, Acct=4, AB=4, Report=4

```
Auto  = (3 x 12.5%) + (3 x 12.5%) + (4 x 15%) + (4 x 7.5%) + (4 x 10%) + (4 x 7.5%) + (4 x 10%)
      = 0.375 + 0.375 + 0.60 + 0.30 + 0.40 + 0.30 + 0.40
      = 2.75 out of 3.00
```

```
Manual = (Campaign Setup score x 15%) + (Collaboration score x 10%)
       = e.g. (4 x 15%) + (4 x 10%) = 0.60 + 0.40 = 1.00 out of 1.00
```

```
TOTAL = Auto + Manual = 2.75 + 1.00 = 3.75 out of 4.00
```
""")

        # Bar chart - all auto KPIs grouped
        st.subheader("Auto Scores by Agent")
        agents = summary_df['Agent'].tolist()
        fig = go.Figure()
        for metric, label, color in [
            ('CPA Score', 'CPA', '#3b82f6'),
            ('ROAS Score', 'ROAS', '#22c55e'),
            ('CVR Score', 'CVR', '#a855f7'),
            ('CTR Score', 'CTR', '#f59e0b'),
            ('Acct Score', 'Account Dev', '#ec4899'),
            ('AB Score', 'A/B Testing', '#06b6d4'),
            ('Rep Score', 'Reporting', '#14b8a6'),
        ]:
            fig.add_trace(go.Bar(name=label, x=agents, y=summary_df[metric].tolist(), marker_color=color))
        fig.update_layout(
            barmode='group',
            yaxis=dict(title='Score (1-4)', range=[0, 4.5]),
            height=400, margin=dict(t=30, b=40),
            legend=dict(orientation='h', y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_auto_chart")

        # Stacked weighted chart
        st.subheader("Total Weighted Score (out of 4.00 max)")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=agents, y=summary_df['Auto'].tolist(),
            name='Auto (CPA 12.5% + ROAS 12.5% + CVR 15% + CTR 7.5% + Acct 10% + AB 7.5% + Report 10%)', marker_color='#3b82f6',
        ))
        fig2.add_trace(go.Bar(
            x=agents, y=summary_df['Manual'].tolist(),
            name='Manual (Setup 15% + Collab 10%)', marker_color='#a855f7',
        ))
        fig2.update_layout(
            barmode='stack',
            yaxis=dict(title='Weighted Score', range=[0, 4.5]),
            height=350, margin=dict(t=30, b=40),
            legend=dict(orientation='h', y=1.1),
        )
        st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_weighted_chart")

        # Manual scoring section
        st.divider()
        st.subheader("Manual KPI Scoring")
        st.caption("Select an agent from the dropdown above to score individual manual KPIs, or score all agents below.")

        for tab_info in KPI_AGENTS:
            agent = tab_info['agent']
            with st.expander(f"📝 {agent} - Manual Scores"):
                cols = st.columns(4)
                for i, key in enumerate(MANUAL_KEYS):
                    info = KPI_MANUAL[key]
                    col = cols[i % 4]
                    with col:
                        current = get_manual_score(agent, key, key_prefix)
                        val = st.selectbox(
                            info['name'],
                            options=[0, 1, 2, 3, 4],
                            index=current,
                            key=f"{key_prefix}_all_{agent}_{key}",
                            help=PARAM_TEXT.get(key, ''),
                        )
                        st.session_state[ss_manual][f"{agent}_{key}"] = val

        # Save All button
        st.divider()
        st.subheader("Save Auto Scores to Google Sheet")
        if st.button("Save All Agents to KPI Sheet", key=f"{key_prefix}_save_all"):
            results = []
            for tab_info in KPI_AGENTS:
                agent = tab_info['agent']
                scores = live_scores.get(agent, {})
                success, msg = write_kpi_scores_to_sheet(agent, scores)
                results.append((agent, success, msg))
            for agent, success, msg in results:
                if success:
                    st.success(f"{agent}: {msg}")
                else:
                    st.warning(f"{agent}: {msg}")

    # ============================================================
    # INDIVIDUAL AGENT VIEW
    # ============================================================
    else:
        agent_name = selected_agent
        agent_scores = live_scores.get(agent_name, {})

        st.subheader(f"KPI Card: {agent_name} - {selected_month_label}")
        st.markdown(f"**ROAS Formula:** `ARPPU / {KPI_PHP_USD_RATE} / Cost_per_FTD`")

        # Auto KPI metric cards
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            v = agent_scores.get('cpa', {}).get('value', 0)
            s = agent_scores.get('cpa', {}).get('score', 0)
            st.metric("CPA", f"${v:.2f}", f"Score: {s}/4")
        with col2:
            v = agent_scores.get('roas', {}).get('value', 0)
            s = agent_scores.get('roas', {}).get('score', 0)
            st.metric("ROAS", f"{v:.4f}x", f"Score: {s}/4")
        with col3:
            v = agent_scores.get('cvr', {}).get('value', 0)
            s = agent_scores.get('cvr', {}).get('score', 0)
            st.metric("CVR", f"{v:.1f}%", f"Score: {s}/4")
        with col4:
            v = agent_scores.get('ctr', {}).get('value', 0)
            s = agent_scores.get('ctr', {}).get('score', 0)
            st.metric("CTR", f"{v:.2f}%", f"Score: {s}/4")
        with col5:
            acct_info = agent_scores.get('account_dev', {})
            acct_v = acct_info.get('value', 0)
            acct_s = acct_info.get('score', 0)
            acct_gmail = acct_info.get('gmail', 0)
            acct_fb = acct_info.get('fb_accounts', 0)
            st.metric("Account Dev", f"{int(acct_v)} accounts", f"Score: {acct_s}/4")
            st.caption(f"{acct_gmail} gmail, {acct_fb} FB")
        with col6:
            ab_info = agent_scores.get('ab_testing', {})
            ab_v = ab_info.get('value', 0)
            ab_s = ab_info.get('score', 0)
            ab_primary = ab_info.get('primary_text', 0)
            st.metric("A/B Testing", f"{int(ab_v)} published", f"Score: {ab_s}/4")
            st.caption(f"{ab_primary} texts created")

        st.divider()

        # Manual scoring inputs
        st.subheader("Manual KPI Scoring")
        cols = st.columns(4)
        for i, key in enumerate(MANUAL_KEYS):
            info = KPI_MANUAL[key]
            col = cols[i % 4]
            with col:
                current = get_manual_score(agent_name, key, key_prefix)
                val = st.selectbox(
                    info['name'],
                    options=[0, 1, 2, 3, 4],
                    index=current,
                    key=f"{key_prefix}_ind_{agent_name}_{key}",
                    help=PARAM_TEXT.get(key, ''),
                )
                st.session_state[ss_manual][f"{agent_name}_{key}"] = val

        st.divider()

        # Full KPI table (auto + manual combined)
        auto_weighted_total = calc_auto_weighted(agent_scores)
        manual_weighted_total = calc_manual_weighted(agent_name, key_prefix)
        grand_total = round(auto_weighted_total + manual_weighted_total, 2)

        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += '<tr style="background:#1e293b;color:#fff">'
        for col in ['KRs', 'KPI', 'Weight', 'Parameters', 'Score', 'Weighted', 'Raw Value']:
            html += f'<th style="padding:8px;text-align:center;border:1px solid #334155">{col}</th>'
        html += '</tr>'

        prev_krs = ""
        for key in KPI_ORDER:
            kpi_info = ALL_KPIS[key]
            krs = kpi_info['krs']
            name = kpi_info['name']
            weight_val = kpi_info['weight']
            weight = f"{int(weight_val * 100)}%" if weight_val > 0 else ''
            params = PARAM_TEXT.get(key, '')
            is_auto = key in KPI_SCORING

            if is_auto and key in agent_scores:
                score = agent_scores[key]['score']
                raw = agent_scores[key]['value']
                if key == 'cpa':
                    raw_display = f"${raw:.2f}"
                elif key == 'roas':
                    raw_display = f"{raw:.4f}x"
                elif key == 'cvr':
                    raw_display = f"{raw:.1f}%"
                elif key == 'ctr':
                    raw_display = f"{raw:.2f}%"
                elif key == 'account_dev':
                    ag = agent_scores.get('account_dev', {})
                    raw_display = f"{int(raw)} ({ag.get('gmail', 0)} gmail + {ag.get('fb_accounts', 0)} FB)"
                elif key == 'ab_testing':
                    ab = agent_scores.get('ab_testing', {})
                    raw_display = f"{int(raw)} published ({ab.get('primary_text', 0)} texts)"
                elif key == 'reporting':
                    rp = agent_scores.get('reporting', {})
                    raw_display = f"{rp.get('avg_minute', 0):.0f}min avg ({rp.get('report_count', 0)} reports)"
                else:
                    raw_display = str(raw)
                weighted = round(score * weight_val, 2) if weight_val > 0 else ''
                score_html = score_badge(score)
                tag = ' <span style="font-size:10px;color:#60a5fa">[AUTO]</span>'
            else:
                score = get_manual_score(agent_name, key, key_prefix)
                raw_display = ''
                weighted = round(score * weight_val, 2) if (weight_val > 0 and score > 0) else ''
                score_html = score_badge(score) if score > 0 else '<span style="color:#64748b">Not scored</span>'
                tag = ' <span style="font-size:10px;color:#c084fc">[MANUAL]</span>'

            krs_display = krs if krs != prev_krs else ''
            prev_krs = krs

            bg = '#0f172a' if is_auto else '#1a1a2e'
            html += f'<tr style="background:{bg};color:#e2e8f0;border:1px solid #334155">'
            html += f'<td style="padding:6px;border:1px solid #334155;font-weight:bold;color:#94a3b8">{krs_display}</td>'
            html += f'<td style="padding:6px;border:1px solid #334155;color:#f1f5f9">{name}{tag}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{weight}</td>'
            html += f'<td style="padding:6px;font-size:11px;border:1px solid #334155;color:#cbd5e1">{params}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_html}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{weighted}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155;color:#f1f5f9">{raw_display}</td>'
            html += '</tr>'

        # Total row
        t_color = "#22c55e" if grand_total >= 2.0 else "#eab308" if grand_total >= 1.5 else "#f97316" if grand_total >= 1.0 else "#ef4444"
        html += f'<tr style="background:#1e293b;color:#fff;font-weight:bold;border:1px solid #334155">'
        html += f'<td style="padding:8px;border:1px solid #334155" colspan="2">TOTAL SCORE</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">100%</td>'
        html += f'<td style="padding:8px;border:1px solid #334155">Auto: {auto_weighted_total} + Manual: {manual_weighted_total}</td>'
        html += f'<td style="padding:8px;border:1px solid #334155"></td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155;color:{t_color};font-size:16px">{grand_total}</td>'
        html += f'<td style="padding:8px;border:1px solid #334155"></td>'
        html += '</tr></table>'

        st.markdown(html, unsafe_allow_html=True)

        # Progress bars
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Auto (75%):** {auto_weighted_total} / 3.00")
            st.progress(min(auto_weighted_total / 3.00, 1.0) if auto_weighted_total > 0 else 0)
        with col2:
            st.markdown(f"**Manual (25%):** {manual_weighted_total} / 1.00")
            st.progress(min(manual_weighted_total / 1.00, 1.0) if manual_weighted_total > 0 else 0)
        with col3:
            st.markdown(f"**Grand Total (100%):** {grand_total} / 4.00")
            st.progress(min(grand_total / 4.00, 1.0) if grand_total > 0 else 0)

        # Save to Sheet button
        st.divider()
        st.subheader("Save to Google Sheet")
        st.caption("Write Account Dev, A/B Testing, and Reporting scores to KPI sheet.")
        if st.button(f"Save {agent_name} KPI to Sheet", key=f"{key_prefix}_save_{agent_name}"):
            with st.spinner(f"Writing scores to KPI sheet for {agent_name}..."):
                success, msg = write_kpi_scores_to_sheet(agent_name, agent_scores)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)


def main():
    st.set_page_config(page_title="KPI Monitoring", page_icon="📊", layout="wide")
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("📊 KPI Monitoring")
    render_content(key_prefix="km")


if not hasattr(st, '_is_recharge_import'):
    main()
