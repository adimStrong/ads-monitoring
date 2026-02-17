"""
Team KPI Scoring Dashboard
Shows per-team KPI metrics from Team Channel data with manual collaboration scoring.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_team_channel_data, refresh_team_channel_data
from config import CHANNEL_ROI_ENABLED, SIDEBAR_HIDE_CSS

# Team-to-channel mapping
TEAM_CHANNEL_MAP = {
    'JASON / SHILA / ADRIAN': 'Promo - 07 - 1, 2 - 13',
    'RON / KRISSA': 'Promo - 10 - 11',
    'JOMAR / MIKA': 'Promo - 6 - 8',
    'DER': 'Promo 9',
}

TEAM_COLORS = {
    'JASON / SHILA / ADRIAN': '#3b82f6',
    'RON / KRISSA': '#22c55e',
    'JOMAR / MIKA': '#a855f7',
    'DER': '#f59e0b',
}


def score_badge(score):
    if score == 0:
        return '<span style="color:#64748b">-</span>'
    colors = {1: '#ef4444', 2: '#f97316', 3: '#eab308', 4: '#22c55e'}
    color = colors.get(score, '#64748b')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold">{score}</span>'


def format_currency(value):
    if pd.isna(value) or value == 0:
        return "$0.00"
    return f"${value:,.2f}"


def format_php(value):
    if pd.isna(value) or value == 0:
        return "₱0.00"
    return f"₱{value:,.2f}"


def render_content(key_prefix="tk"):
    """Render Team KPI content. key_prefix avoids widget key conflicts when embedded in tabs."""

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    with st.spinner("Loading Team Channel data..."):
        data = load_team_channel_data()
        overall_df = data.get('overall', pd.DataFrame())

    if overall_df.empty:
        st.error("No Team Channel data available.")
        st.info("Check that the 'Team Channel' sheet exists and has data.")
        return

    # Refresh button (moved from sidebar into content area)
    rcol1, rcol2 = st.columns([4, 1])
    with rcol2:
        if st.button("Refresh Data", type="primary", key=f"{key_prefix}_refresh"):
            refresh_team_channel_data()
            st.cache_data.clear()
            st.rerun()

    # Initialize session state for collaboration scores
    ss_collab = f"{key_prefix}_team_collab_scores"
    if ss_collab not in st.session_state:
        st.session_state[ss_collab] = {}

    # --- Team-Channel Mapping ---
    st.markdown('<div class="section-header"><h3>Team → Channel Mapping</h3></div>', unsafe_allow_html=True)

    mapping_html = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:15px">'
    mapping_html += '<tr style="background:#1e293b;color:#fff"><th style="padding:8px;border:1px solid #334155;text-align:left">Team</th><th style="padding:8px;border:1px solid #334155;text-align:left">Channel Source</th></tr>'
    for team, channels in TEAM_CHANNEL_MAP.items():
        color = TEAM_COLORS.get(team, '#64748b')
        mapping_html += f'<tr style="background:#0f172a;color:#e2e8f0;border:1px solid #334155">'
        mapping_html += f'<td style="padding:8px;border:1px solid #334155;font-weight:bold;color:{color}">{team}</td>'
        mapping_html += f'<td style="padding:8px;border:1px solid #334155">{channels}</td></tr>'
    mapping_html += '</table>'
    st.markdown(mapping_html, unsafe_allow_html=True)

    # --- Aggregate by team ---
    team_agg = overall_df.groupby('team').agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    team_agg['cpr'] = team_agg.apply(lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    team_agg['cpfd'] = team_agg.apply(lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    team_agg['arppu'] = team_agg.apply(lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    team_agg['roas'] = team_agg.apply(lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    # --- KPI Metrics Cards ---
    st.markdown('<div class="section-header"><h3>Team KPI Metrics</h3></div>', unsafe_allow_html=True)

    html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
    html += '<tr style="background:#1e293b;color:#fff">'
    for col in ['Team', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'CPR ($)', 'CPFD ($)', 'ARPPU (₱)', 'ROAS', 'Collab']:
        html += f'<th style="padding:8px;text-align:center;border:1px solid #334155">{col}</th>'
    html += '</tr>'

    for _, r in team_agg.iterrows():
        team = r['team']
        color = TEAM_COLORS.get(team, '#64748b')
        collab = st.session_state[ss_collab].get(team, 0)

        html += f'<tr style="background:#0f172a;color:#e2e8f0;border:1px solid #334155">'
        html += f'<td style="padding:8px;border:1px solid #334155;font-weight:bold;color:{color}">{team}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">${r["cost"]:,.0f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{r["registrations"]:,.0f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{r["first_recharge"]:,.0f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">₱{r["total_amount"]:,.0f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">${r["cpr"]:.2f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">${r["cpfd"]:.2f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">₱{r["arppu"]:.0f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{r["roas"]:.2f}</td>'
        html += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{score_badge(collab)}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # --- Manual Collaboration Scoring ---
    st.markdown("")
    st.markdown("**Manual Collaboration Scoring (1-4):**")
    cols = st.columns(len(team_agg))
    for i, (_, r) in enumerate(team_agg.iterrows()):
        team = r['team']
        with cols[i]:
            current = st.session_state[ss_collab].get(team, 0)
            val = st.selectbox(
                team,
                options=[0, 1, 2, 3, 4],
                index=current,
                key=f"{key_prefix}_collab_{team}",
                help="4: Excellent | 3: Good | 2: Fair | 1: Poor",
            )
            st.session_state[ss_collab][team] = val

    # --- Bar Charts ---
    st.divider()
    st.markdown('<div class="section-header"><h3>Team Comparison</h3></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure(go.Bar(
            x=team_agg['team'], y=team_agg['cost'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
            text=[f"${v:,.0f}" for v in team_agg['cost']], textposition='outside',
        ))
        fig.update_layout(title='Total Cost ($)', height=380, yaxis_title="USD")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cost_chart")

    with col2:
        fig = go.Figure(go.Bar(
            x=team_agg['team'], y=team_agg['first_recharge'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
            text=[f"{v:,}" for v in team_agg['first_recharge']], textposition='outside',
        ))
        fig.update_layout(title='1st Recharge Count', height=380, yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_recharge_chart")

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure(go.Bar(
            x=team_agg['team'], y=team_agg['roas'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
            text=[f"{v:.2f}" for v in team_agg['roas']], textposition='outside',
        ))
        fig.update_layout(title='ROAS', height=380, yaxis_title="Ratio")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_roas_chart")

    with col2:
        fig = go.Figure(go.Bar(
            x=team_agg['team'], y=team_agg['cpfd'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
            text=[f"${v:.2f}" for v in team_agg['cpfd']], textposition='outside',
        ))
        fig.update_layout(title='CPFD ($)', height=380, yaxis_title="USD")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cpfd_chart")

    st.caption("Team KPI Scoring | Data from Team Channel sheet")


def main():
    st.set_page_config(page_title="Team KPI", page_icon="🏆", layout="wide")

    st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("🏆 Team KPI Scoring")
    render_content(key_prefix="tk")


if not hasattr(st, '_is_recharge_import'):
    main()
