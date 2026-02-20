"""
Agent Performance Page - Individual agent detailed view
Tabs: Overview, Individual Overall (P-tabs)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FACEBOOK_ADS_PERSONS, SIDEBAR_HIDE_CSS
from channel_data_loader import (
    load_agent_performance_data as load_ptab_data, refresh_agent_performance_data,
)

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Map FACEBOOK_ADS_PERSONS (uppercase) to P-tab agent names (title case)
PTAB_AGENT_MAP = {
    'MIKA': 'Mika', 'ADRIAN': 'Adrian', 'JOMAR': 'Jomar',
    'SHILA': 'Shila', 'KRISSA': 'Krissa', 'JASON': 'Jason',
    'RON': 'Ron', 'DER': 'Derr',
}

# Sidebar logo
logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.jpg")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)

st.title("👤 Agent Performance Dashboard")

# Load P-tab data
try:
    ptab_all = load_ptab_data()
    ptab_errors = ptab_all.get('errors', [])
    if ptab_errors:
        for err in ptab_errors:
            st.sidebar.warning(f"P-tab: {err}")
except Exception as e:
    st.sidebar.error(f"P-tab load error: {e}")
    ptab_all = {'monthly': pd.DataFrame(), 'daily': pd.DataFrame(), 'ad_accounts': pd.DataFrame(), 'errors': [str(e)]}

# Sidebar filters
st.sidebar.header("Filters")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    refresh_agent_performance_data()
    st.cache_data.clear()
    st.rerun()

# Agent selector - use all Facebook Ads persons, with "All" option
selected_agent = st.sidebar.selectbox(
    "Select Agent",
    ["All"] + list(FACEBOOK_ADS_PERSONS),
    index=0
)

is_all_agents = selected_agent == "All"

# P-tab data
ptab_daily = ptab_all.get('daily', pd.DataFrame())

if is_all_agents:
    # All agents: use all P-tab data
    ptab_agent = None  # not filtering by single agent
    has_ptab = not ptab_daily.empty
    agent_ptab_daily = ptab_daily.copy() if has_ptab else pd.DataFrame()
    # Aggregate daily across all agents (sum per date)
    if has_ptab:
        agent_ptab_daily = agent_ptab_daily.groupby('date').agg({
            'cost': 'sum', 'register': 'sum', 'ftd': 'sum',
            'impressions': 'sum', 'clicks': 'sum',
            'cpr': 'mean', 'cpd': 'mean', 'conv_rate': 'mean',
            'arppu': 'mean', 'roas': 'mean', 'ctr': 'mean',
        }).reset_index()
else:
    ptab_agent = PTAB_AGENT_MAP.get(selected_agent)
    has_ptab = ptab_agent and not ptab_daily.empty and ptab_agent in ptab_daily['agent'].values
    agent_ptab_daily = pd.DataFrame()
    if has_ptab:
        agent_ptab_daily = ptab_daily[ptab_daily['agent'] == ptab_agent].copy()

# Date range from P-tab
if has_ptab:
    min_date = agent_ptab_daily['date'].min().date()
    max_date = agent_ptab_daily['date'].max().date()
else:
    min_date, max_date = None, None

if min_date and max_date:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        default_start = max(min_date, max_date - timedelta(days=7))
        start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)
    st.sidebar.caption(f"Data: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("To", datetime.now())

# Apply date filter to P-tab data
if has_ptab and not agent_ptab_daily.empty:
    agent_ptab_daily = agent_ptab_daily[
        (agent_ptab_daily['date'] >= pd.Timestamp(start_date)) &
        (agent_ptab_daily['date'] <= pd.Timestamp(end_date))
    ]
    has_ptab = not agent_ptab_daily.empty

# Sidebar data info
if has_ptab:
    st.sidebar.success(f"P-tab: {len(agent_ptab_daily)} days loaded")

# ============================================================
# AGENT HEADER
# ============================================================

header_name = "ALL AGENTS" if is_all_agents else selected_agent
header_subtitle = f"Combined Performance • {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}" if is_all_agents else f"Performance Overview • {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
st.markdown(f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
    <h1 style="margin: 0; font-size: 2.5rem;">{header_name}</h1>
    <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">{header_subtitle}</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION TABS
# ============================================================

tab1, tab5 = st.tabs([
    "📊 Overview",
    "📈 Individual Overall",
])

# ============================================================
# TAB 1: OVERVIEW
# ============================================================

with tab1:
    st.subheader("Quick Summary")

    if has_ptab:
        total_cost = agent_ptab_daily['cost'].sum()
        total_reg = int(agent_ptab_daily['register'].sum())
        total_ftd = int(agent_ptab_daily['ftd'].sum())
        total_impr = int(agent_ptab_daily['impressions'].sum())
        total_clicks = int(agent_ptab_daily['clicks'].sum())
        avg_cpr = total_cost / total_reg if total_reg > 0 else 0
        avg_cpd = total_cost / total_ftd if total_ftd > 0 else 0
        conv_rate = (total_ftd / total_reg * 100) if total_reg > 0 else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Cost", f"${total_cost:,.2f}")
        c2.metric("Register", f"{total_reg:,}")
        c3.metric("FTD", f"{total_ftd:,}")
        c4.metric("CPR", f"${avg_cpr:.2f}")
        c5.metric("Cost/FTD", f"${avg_cpd:.2f}")
        c6.metric("Conv Rate", f"{conv_rate:.1f}%")

        c1, c2, c3 = st.columns(3)
        c1.metric("Impressions", f"{total_impr:,}")
        c2.metric("Clicks", f"{total_clicks:,}")
        c3.metric("CTR", f"{(total_clicks / total_impr * 100) if total_impr > 0 else 0:.2f}%")
    else:
        st.info("No P-tab data available.")

    st.divider()

    # Daily trend from P-tab data
    st.subheader("Daily Activity Trend")

    fig = go.Figure()
    if has_ptab:
        a_daily = agent_ptab_daily.sort_values('date')
        fig.add_trace(go.Scatter(x=a_daily['date'], y=a_daily['cost'], name='Cost ($)', line=dict(color='#3498db', width=3), mode='lines+markers'))
        fig.add_trace(go.Scatter(x=a_daily['date'], y=a_daily['ftd'], name='FTD', line=dict(color='#27ae60', width=3), mode='lines+markers', yaxis='y2'))
        fig.update_layout(
            height=350,
            yaxis=dict(title='Cost ($)', side='left'),
            yaxis2=dict(title='FTD', side='right', overlaying='y'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(l=20, r=20, t=40, b=20),
        )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 5: INDIVIDUAL OVERALL (INDIVIDUAL KPI data)
# ============================================================

with tab5:
    st.subheader("📈 Individual Overall (P-tab)")

    if has_ptab:
        agent_daily = agent_ptab_daily.sort_values('date').copy()

        # KPI cards
        total_cost = agent_daily['cost'].sum()
        total_reg = int(agent_daily['register'].sum())
        total_ftd = int(agent_daily['ftd'].sum())
        avg_cpr = total_cost / total_reg if total_reg > 0 else 0
        avg_cpd = total_cost / total_ftd if total_ftd > 0 else 0
        conv_rate = (total_ftd / total_reg * 100) if total_reg > 0 else 0
        total_impr = int(agent_daily['impressions'].sum())
        total_clicks = int(agent_daily['clicks'].sum())
        overall_ctr = (total_clicks / total_impr * 100) if total_impr > 0 else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Cost", f"${total_cost:,.2f}")
        c2.metric("Register", f"{total_reg:,}")
        c3.metric("FTD", f"{total_ftd:,}")
        c4.metric("CPR", f"${avg_cpr:.2f}")
        c5.metric("Cost/FTD", f"${avg_cpd:.2f}")
        c6.metric("Conv Rate", f"{conv_rate:.1f}%")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Impressions", f"{total_impr:,}")
        c2.metric("Clicks", f"{total_clicks:,}")
        c3.metric("CTR", f"{overall_ctr:.2f}%")
        c4.metric("ROAS", f"{agent_daily['roas'].mean():.2f}")

        st.divider()

        # Per-agent breakdown table when "All" selected
        if is_all_agents and not agent_ptab_daily.empty:
            st.subheader("Per Agent Breakdown")
            # Use the unfiltered ptab_daily but apply date filter
            filtered_ptab = ptab_daily[
                (ptab_daily['date'] >= pd.Timestamp(start_date)) &
                (ptab_daily['date'] <= pd.Timestamp(end_date))
            ]
            per_agent = filtered_ptab.groupby('agent').agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum',
                'impressions': 'sum', 'clicks': 'sum',
            }).reset_index()
            per_agent['cpr'] = per_agent.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
            per_agent['cpd'] = per_agent.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            per_agent['conv_rate'] = per_agent.apply(lambda r: (r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, axis=1)
            per_agent['ctr'] = per_agent.apply(lambda r: (r['clicks'] / r['impressions'] * 100) if r['impressions'] > 0 else 0, axis=1)
            per_agent = per_agent.sort_values('cost', ascending=False)

            # Chart: cost by agent
            fig = px.bar(per_agent.sort_values('cost', ascending=True), y='agent', x='cost', orientation='h',
                         title='Cost by Agent', text_auto='$.2s', color_discrete_sequence=['#667eea'])
            fig.update_layout(height=max(300, len(per_agent) * 45), showlegend=False, yaxis_title='')
            st.plotly_chart(fig, use_container_width=True)

            # Format for display
            pa_disp = per_agent.copy()
            pa_disp['cost'] = pa_disp['cost'].apply(lambda x: f"${x:,.2f}")
            pa_disp['cpr'] = pa_disp['cpr'].apply(lambda x: f"${x:,.2f}")
            pa_disp['cpd'] = pa_disp['cpd'].apply(lambda x: f"${x:,.2f}")
            pa_disp['impressions'] = pa_disp['impressions'].apply(lambda x: f"{int(x):,}")
            pa_disp['clicks'] = pa_disp['clicks'].apply(lambda x: f"{int(x):,}")
            pa_disp['conv_rate'] = pa_disp['conv_rate'].apply(lambda x: f"{x:.1f}%")
            pa_disp['ctr'] = pa_disp['ctr'].apply(lambda x: f"{x:.2f}%")
            pa_disp = pa_disp.rename(columns={
                'agent': 'Agent', 'cost': 'Cost', 'register': 'Register', 'ftd': 'FTD',
                'cpr': 'CPR', 'cpd': 'Cost/FTD', 'conv_rate': 'Conv %',
                'impressions': 'Impressions', 'clicks': 'Clicks', 'ctr': 'CTR',
            })
            st.dataframe(pa_disp, use_container_width=True, hide_index=True)
            st.divider()

        # Daily trend charts
        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['cost'], name='Cost', marker_color='#667eea'))
            fig.update_layout(height=300, title='Daily Cost', xaxis_tickformat='%m/%d', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['register'], name='Register', marker_color='#3498db'))
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['ftd'], name='FTD', marker_color='#27ae60'))
            fig.update_layout(height=300, title='Register vs FTD', xaxis_tickformat='%m/%d', barmode='group', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # Daily data table
        st.subheader("Daily Data")
        daily_cols = ['date', 'cost', 'register', 'cpr', 'ftd', 'cpd', 'conv_rate', 'impressions', 'clicks', 'ctr', 'arppu', 'roas']
        available_daily_cols = [c for c in daily_cols if c in agent_daily.columns]
        d_display = agent_daily[available_daily_cols].copy()
        d_display = d_display.sort_values('date', ascending=False)
        d_display['date'] = d_display['date'].dt.strftime('%m/%d/%Y') if hasattr(d_display['date'], 'dt') else d_display['date']
        # Format numbers with commas for display
        d_display['cost'] = d_display['cost'].apply(lambda x: f"${x:,.2f}")
        if 'cpr' in d_display.columns:
            d_display['cpr'] = d_display['cpr'].apply(lambda x: f"${x:,.2f}")
        if 'cpd' in d_display.columns:
            d_display['cpd'] = d_display['cpd'].apply(lambda x: f"${x:,.2f}")
        d_display['impressions'] = d_display['impressions'].apply(lambda x: f"{int(x):,}")
        d_display['clicks'] = d_display['clicks'].apply(lambda x: f"{int(x):,}")
        if 'conv_rate' in d_display.columns:
            d_display['conv_rate'] = d_display['conv_rate'].apply(lambda x: f"{x:.2f}%")
        if 'ctr' in d_display.columns:
            d_display['ctr'] = d_display['ctr'].apply(lambda x: f"{x:.2f}%")
        if 'arppu' in d_display.columns:
            d_display['arppu'] = d_display['arppu'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(
            d_display,
            use_container_width=True, hide_index=True,
            column_config={
                "cost": "Cost", "cpr": "CPR", "cpd": "Cost/FTD",
                "conv_rate": "Conv %", "impressions": "Impressions",
                "clicks": "Clicks", "ctr": "CTR", "arppu": "ARPPU", "roas": "ROAS",
            },
        )
    else:
        st.warning(f"No P-tab data available for {selected_agent}.")
