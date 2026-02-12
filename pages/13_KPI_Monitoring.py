"""
KPI Monitoring Dashboard
Auto-calculates advertising KPI scores from P-tab data.
Manual KPIs can be scored via input fields per agent.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from channel_data_loader import (
    load_agent_performance_data,
    refresh_agent_performance_data,
    calculate_kpi_scores,
)
from config import (
    AGENT_PERFORMANCE_TABS,
    KPI_SCORING,
    KPI_MANUAL,
    KPI_ORDER,
    KPI_PHP_USD_RATE,
)

st.set_page_config(page_title="KPI Monitoring", page_icon="📊", layout="wide")
st.title("📊 KPI Monitoring")

# Initialize session state for manual scores
if 'manual_scores' not in st.session_state:
    st.session_state.manual_scores = {}

ALL_KPIS = {**KPI_SCORING, **KPI_MANUAL}
MANUAL_KEYS = list(KPI_MANUAL.keys())

PARAM_TEXT = {
    'cpa': '4: $9-$9.9 | 3: $10-$13 | 2: $14-$15 | 1: >$15',
    'roas': '4: >0.40x | 3: 0.20-0.39x | 2: 0.10-0.19x | 1: <0.10x',
    'cvr': '4: 7-9% | 3: 4-6% | 2: 2-3% | 1: <2%',
    'campaign_setup': '4: 95-97% | 3: 90-94% | 2: 85-89% | 1: <85%',
    'ctr': '4: 3-4% | 3: 2-2.9% | 2: 1-1.9% | 1: <0.9%',
    'ab_testing': '4: 20-24/wk | 3: 11-19/wk | 2: 6-10/wk | 1: <6/wk',
    'reporting': '4: 95-100% | 3: 85-94% | 2: 75-84% | 1: <75%',
    'data_insights': '4: Excellent | 3: Good | 2: Fair | 1: Poor',
    'account_dev': '4: 95-100% | 3: 85-94% | 2: 75-84% | 1: <75%',
    'profile_dev': '4: Excellent | 3: Good | 2: Fair | 1: Poor',
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


def get_manual_score(agent, key):
    """Get manual score from session state."""
    return st.session_state.manual_scores.get(f"{agent}_{key}", 0)


def calc_manual_weighted(agent):
    """Calculate total manual weighted score for an agent."""
    total = 0
    for key, info in KPI_MANUAL.items():
        score = get_manual_score(agent, key)
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


# Sidebar
st.sidebar.header("KPI Settings")

agent_names = ["All Agents"] + [t['agent'] for t in AGENT_PERFORMANCE_TABS]
selected_agent = st.sidebar.selectbox("Agent", agent_names)

if st.sidebar.button("🔄 Refresh Data"):
    refresh_agent_performance_data()
    st.rerun()

# Load P-tab data
ptab_data = load_agent_performance_data()
monthly_df = ptab_data.get('monthly', pd.DataFrame()) if ptab_data else pd.DataFrame()
daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()

# Calculate live auto scores from P-tab
live_scores = {}
for tab_info in AGENT_PERFORMANCE_TABS:
    agent = tab_info['agent']
    live_scores[agent] = calculate_kpi_scores(monthly_df, agent, daily_df=daily_df)


# ============================================================
# ALL AGENTS VIEW
# ============================================================
if selected_agent == "All Agents":
    st.subheader("Team KPI Overview")
    st.markdown(f"**ROAS Formula:** `ARPPU / {KPI_PHP_USD_RATE} / Cost_per_FTD`")

    rows = []
    for tab_info in AGENT_PERFORMANCE_TABS:
        agent = tab_info['agent']
        s = live_scores[agent]

        cpa_s = s.get('cpa', {}).get('score', 0)
        roas_s = s.get('roas', {}).get('score', 0)
        cvr_s = s.get('cvr', {}).get('score', 0)
        ctr_s = s.get('ctr', {}).get('score', 0)

        cpa_v = s.get('cpa', {}).get('value', 0)
        roas_v = s.get('roas', {}).get('value', 0)
        cvr_v = s.get('cvr', {}).get('value', 0)
        ctr_v = s.get('ctr', {}).get('value', 0)

        auto_wt = calc_auto_weighted(s)
        manual_wt = calc_manual_weighted(agent)
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
            'Auto': auto_wt,
            'Manual': manual_wt,
            'Total': total_wt,
        })

    summary_df = pd.DataFrame(rows)

    # HTML table with all columns
    html = '<table style="width:100%;border-collapse:collapse;font-size:14px">'
    html += '<tr style="background:#1e293b;color:#fff">'
    for col in ['Agent', 'CPA', 'Score', 'ROAS', 'Score', 'CVR', 'Score', 'CTR', 'Score', 'Auto', 'Manual', 'Total']:
        html += f'<th style="padding:8px;text-align:center;border:1px solid #334155">{col}</th>'
    html += '</tr>'

    for _, r in summary_df.iterrows():
        html += '<tr style="border:1px solid #334155">'
        html += f'<td style="padding:6px;font-weight:bold;border:1px solid #334155">{r["Agent"]}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["CPA"]}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_badge(r["CPA Score"])}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["ROAS"]}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_badge(r["ROAS Score"])}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["CVR"]}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_badge(r["CVR Score"])}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["CTR"]}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_badge(r["CTR Score"])}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["Auto"]}</td>'
        m = r["Manual"]
        m_color = "#22c55e" if m > 0 else "#64748b"
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155;color:{m_color}">{m}</td>'
        t = r["Total"]
        t_color = "#22c55e" if t >= 2.0 else "#eab308" if t >= 1.5 else "#f97316" if t >= 1.0 else "#ef4444"
        html += f'<td style="padding:6px;text-align:center;font-weight:bold;border:1px solid #334155;color:{t_color}">{t}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Bar chart - all 12 KPIs grouped
    st.subheader("Auto Scores by Agent")
    agents = summary_df['Agent'].tolist()
    fig = go.Figure()
    for metric, label, color in [
        ('CPA Score', 'CPA', '#3b82f6'),
        ('ROAS Score', 'ROAS', '#22c55e'),
        ('CVR Score', 'CVR', '#a855f7'),
        ('CTR Score', 'CTR', '#f59e0b'),
    ]:
        fig.add_trace(go.Bar(name=label, x=agents, y=summary_df[metric].tolist(), marker_color=color))
    fig.update_layout(
        barmode='group',
        yaxis=dict(title='Score (1-4)', range=[0, 4.5]),
        height=400, margin=dict(t=30, b=40),
        legend=dict(orientation='h', y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Stacked weighted chart
    st.subheader("Total Weighted Score (out of 2.80 max)")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=agents, y=summary_df['Auto'].tolist(),
        name='Auto (CPA 25% + CVR 15%)', marker_color='#3b82f6',
    ))
    fig2.add_trace(go.Bar(
        x=agents, y=summary_df['Manual'].tolist(),
        name='Manual (Report 10% + Acct 10% + Team 10%)', marker_color='#a855f7',
    ))
    fig2.update_layout(
        barmode='stack',
        yaxis=dict(title='Weighted Score', range=[0, 3.0]),
        height=350, margin=dict(t=30, b=40),
        legend=dict(orientation='h', y=1.1),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Manual scoring section
    st.divider()
    st.subheader("Manual KPI Scoring")
    st.caption("Select an agent from sidebar to score individual manual KPIs, or score all agents below.")

    for tab_info in AGENT_PERFORMANCE_TABS:
        agent = tab_info['agent']
        with st.expander(f"📝 {agent} - Manual Scores"):
            cols = st.columns(4)
            for i, key in enumerate(MANUAL_KEYS):
                info = KPI_MANUAL[key]
                col = cols[i % 4]
                with col:
                    current = get_manual_score(agent, key)
                    val = st.selectbox(
                        info['name'],
                        options=[0, 1, 2, 3, 4],
                        index=current,
                        key=f"all_{agent}_{key}",
                        help=PARAM_TEXT.get(key, ''),
                    )
                    st.session_state.manual_scores[f"{agent}_{key}"] = val

# ============================================================
# INDIVIDUAL AGENT VIEW
# ============================================================
else:
    agent_name = selected_agent
    agent_scores = live_scores.get(agent_name, {})

    st.subheader(f"KPI Card: {agent_name}")
    st.markdown(f"**ROAS Formula:** `ARPPU / {KPI_PHP_USD_RATE} / Cost_per_FTD`")

    # Auto KPI metric cards
    col1, col2, col3, col4 = st.columns(4)
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

    st.divider()

    # Manual scoring inputs
    st.subheader("Manual KPI Scoring")
    cols = st.columns(4)
    for i, key in enumerate(MANUAL_KEYS):
        info = KPI_MANUAL[key]
        col = cols[i % 4]
        with col:
            current = get_manual_score(agent_name, key)
            val = st.selectbox(
                info['name'],
                options=[0, 1, 2, 3, 4],
                index=current,
                key=f"ind_{agent_name}_{key}",
                help=PARAM_TEXT.get(key, ''),
            )
            st.session_state.manual_scores[f"{agent_name}_{key}"] = val

    st.divider()

    # Full KPI table (auto + manual combined)
    auto_weighted_total = calc_auto_weighted(agent_scores)
    manual_weighted_total = calc_manual_weighted(agent_name)
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
            else:
                raw_display = str(raw)
            weighted = round(score * weight_val, 2) if weight_val > 0 else ''
            score_html = score_badge(score)
            tag = ' <span style="font-size:10px;color:#60a5fa">[AUTO]</span>'
        else:
            score = get_manual_score(agent_name, key)
            raw_display = ''
            weighted = round(score * weight_val, 2) if (weight_val > 0 and score > 0) else ''
            score_html = score_badge(score) if score > 0 else '<span style="color:#64748b">Not scored</span>'
            tag = ' <span style="font-size:10px;color:#c084fc">[MANUAL]</span>'

        krs_display = krs if krs != prev_krs else ''
        prev_krs = krs

        bg = '#0f172a' if is_auto else '#1a1a2e'
        html += f'<tr style="background:{bg};border:1px solid #334155">'
        html += f'<td style="padding:6px;border:1px solid #334155;font-weight:bold">{krs_display}</td>'
        html += f'<td style="padding:6px;border:1px solid #334155">{name}{tag}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{weight}</td>'
        html += f'<td style="padding:6px;font-size:11px;border:1px solid #334155">{params}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{score_html}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{weighted}</td>'
        html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{raw_display}</td>'
        html += '</tr>'

    # Total row
    t_color = "#22c55e" if grand_total >= 2.0 else "#eab308" if grand_total >= 1.5 else "#f97316" if grand_total >= 1.0 else "#ef4444"
    html += f'<tr style="background:#1e293b;color:#fff;font-weight:bold;border:1px solid #334155">'
    html += f'<td style="padding:8px;border:1px solid #334155" colspan="2">TOTAL SCORE</td>'
    html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">70%</td>'
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
        st.markdown(f"**Auto (40%):** {auto_weighted_total} / 1.60")
        st.progress(min(auto_weighted_total / 1.60, 1.0) if auto_weighted_total > 0 else 0)
    with col2:
        st.markdown(f"**Manual (30%):** {manual_weighted_total} / 1.20")
        st.progress(min(manual_weighted_total / 1.20, 1.0) if manual_weighted_total > 0 else 0)
    with col3:
        st.markdown(f"**Grand Total (70%):** {grand_total} / 2.80")
        st.progress(min(grand_total / 2.80, 1.0) if grand_total > 0 else 0)
