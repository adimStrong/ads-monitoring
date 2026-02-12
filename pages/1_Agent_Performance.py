"""
Agent Performance Page - Individual agent detailed view
Tabs: Overview, Individual Overall (INDIVIDUAL KPI), By Campaign (P-tabs), Creative Work, SMS
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AGENTS, SMS_TYPES, FACEBOOK_ADS_PERSONS, EXCLUDED_PERSONS
from data_loader import load_agent_performance_data, load_agent_content_data, get_date_range
from channel_data_loader import (
    load_agent_performance_data as load_ptab_data, refresh_agent_performance_data,
    load_individual_kpi_data, refresh_individual_kpi_data,
)

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

# ============================================================
# DATA LOADING FUNCTIONS
# ============================================================

@st.cache_data(ttl=300)
def get_agent_data(agent_name, sheet_name):
    """Load data for selected agent from Google Sheets"""
    return load_agent_performance_data(agent_name, sheet_name)

# Load P-tab data early (shared across By Campaign tab)
try:
    ptab_all = load_ptab_data()
    ptab_errors = ptab_all.get('errors', [])
    if ptab_errors:
        for err in ptab_errors:
            st.sidebar.warning(f"P-tab: {err}")
except Exception as e:
    st.sidebar.error(f"P-tab load error: {e}")
    ptab_all = {'monthly': pd.DataFrame(), 'daily': pd.DataFrame(), 'ad_accounts': pd.DataFrame(), 'errors': [str(e)]}

# Load INDIVIDUAL KPI data (with DER redistribution) for Individual Overall tab
try:
    kpi_df = load_individual_kpi_data()
    if kpi_df is None:
        kpi_df = pd.DataFrame()
except Exception as e:
    st.sidebar.error(f"Individual KPI load error: {e}")
    kpi_df = pd.DataFrame()

# Sidebar filters
st.sidebar.header("Filters")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    refresh_agent_performance_data()
    refresh_individual_kpi_data()
    st.cache_data.clear()
    st.rerun()

# Agent selector - use all Facebook Ads persons
selected_agent = st.sidebar.selectbox(
    "Select Agent",
    FACEBOOK_ADS_PERSONS,
    index=0
)

# Get agent config (for legacy sheets - may be None for FB-only agents like RON, JASON, DER)
agent_config = next((a for a in AGENTS if a['name'] == selected_agent), None)

# Data source toggle
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True, key="agent_perf_data_source")

# Load data FIRST to determine date range
running_ads_df = None
creative_df = None
sms_df = None

if use_real_data and agent_config:
    with st.spinner(f"Loading data for {selected_agent}..."):
        running_ads_df, creative_df, sms_df = get_agent_data(
            selected_agent,
            agent_config['sheet_performance']
        )

    if running_ads_df is None or running_ads_df.empty:
        use_real_data = False

# P-tab data for this agent (By Campaign tab)
ptab_agent = PTAB_AGENT_MAP.get(selected_agent)
ptab_daily = ptab_all.get('daily', pd.DataFrame())
ptab_monthly = ptab_all.get('monthly', pd.DataFrame())
ptab_ad = ptab_all.get('ad_accounts', pd.DataFrame())

has_ptab = ptab_agent and not ptab_daily.empty and ptab_agent in ptab_daily['agent'].values

# INDIVIDUAL KPI data for this agent (Individual Overall tab)
# DER is excluded/redistributed - check if agent has data
is_excluded = selected_agent.upper() in [p.upper() for p in EXCLUDED_PERSONS]
agent_kpi_df = pd.DataFrame()
if not kpi_df.empty and not is_excluded:
    agent_kpi_df = kpi_df[kpi_df['person_name'] == selected_agent].copy()
has_kpi = not agent_kpi_df.empty

# Date range from INDIVIDUAL KPI, P-tab, or legacy
if has_kpi:
    min_date = agent_kpi_df['date'].min().date()
    max_date = agent_kpi_df['date'].max().date()
elif has_ptab:
    agent_ptab_daily = ptab_daily[ptab_daily['agent'] == ptab_agent]
    min_date = agent_ptab_daily['date'].min().date()
    max_date = agent_ptab_daily['date'].max().date()
elif running_ads_df is not None and not running_ads_df.empty:
    _min, _max = get_date_range(running_ads_df)
    min_date = _min.date() if hasattr(_min, 'date') else _min
    max_date = _max.date() if hasattr(_max, 'date') else _max
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

# Sidebar data info
if has_kpi:
    st.sidebar.success(f"KPI: {len(agent_kpi_df)} days loaded")
elif is_excluded:
    st.sidebar.info(f"{selected_agent}'s data redistributed to other agents")
if has_ptab:
    n_accts = ptab_ad[ptab_ad['agent'] == ptab_agent]['ad_account'].nunique() if not ptab_ad.empty and ptab_agent in ptab_ad['agent'].values else 0
    st.sidebar.success(f"P-tab: {n_accts} ad accounts")

# Fallback sample data for creative/SMS
if not use_real_data or running_ads_df is None or running_ads_df.empty:
    random.seed(hash(selected_agent + "ads"))
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    running_ads_data = []
    for date in dates:
        running_ads_data.append({
            'date': date, 'total_ad': random.randint(5, 25),
            'campaign': f"Campaign_{random.randint(1, 5)}",
            'impressions': random.randint(2000, 15000),
            'clicks': random.randint(100, 800),
            'ctr_percent': round(random.uniform(1.5, 5.5), 2),
            'cpc': round(random.uniform(0.3, 2.5), 2),
            'conversion_rate': round(random.uniform(0.8, 4.0), 2),
            'rejected_count': random.randint(0, 5),
            'deleted_count': random.randint(0, 3),
            'active_count': random.randint(5, 20),
        })
    running_ads_df = pd.DataFrame(running_ads_data)

    random.seed(hash(selected_agent + "creative"))
    creative_data = []
    for date in dates:
        for _ in range(random.randint(1, 4)):
            creative_data.append({
                'date': date, 'creative_folder': f'Folder_{random.choice(["A","B","C"])}',
                'creative_type': random.choice(['Video', 'Image', 'Carousel']),
                'creative_content': f"Content_{random.randint(1000, 9999)}",
                'caption': f"Caption {random.randint(1, 100)}",
            })
    creative_df = pd.DataFrame(creative_data)

    random.seed(hash(selected_agent + "sms"))
    sms_data = []
    for date in dates:
        for _ in range(random.randint(1, 3)):
            sms_data.append({
                'date': date, 'sms_type': random.choice(SMS_TYPES),
                'sms_total': random.randint(50, 300),
            })
    sms_df = pd.DataFrame(sms_data)

# ============================================================
# AGENT HEADER
# ============================================================

st.markdown(f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
    <h1 style="margin: 0; font-size: 2.5rem;">{selected_agent}</h1>
    <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">Performance Overview • {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION TABS
# ============================================================

tab1, tab5, tab6, tab3, tab4 = st.tabs([
    "📊 Overview",
    "📈 Individual Overall", "🎯 By Campaign",
    "🎨 Creative Work", "📱 SMS",
])

# ============================================================
# TAB 1: OVERVIEW
# ============================================================

with tab1:
    st.subheader("Quick Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); padding: 1.5rem; border-radius: 12px; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">INDIVIDUAL KPI</h4>
        </div>
        """, unsafe_allow_html=True)
        if has_kpi:
            st.metric("Total Spend", f"${agent_kpi_df['spend'].sum():,.2f}")
            st.metric("Register", f"{int(agent_kpi_df['register'].sum()):,}")
            st.metric("FTD", f"{int(agent_kpi_df['ftd'].sum()):,}")
        else:
            st.metric("Total Spend", "$0")
            st.metric("Register", "0")
            st.metric("FTD", "0")

    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); padding: 1.5rem; border-radius: 12px; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">WITHOUT (Creative Work)</h4>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Total Creatives", f"{len(creative_df):,}")
        st.metric("Unique Types", f"{creative_df['creative_type'].nunique() if not creative_df.empty and 'creative_type' in creative_df.columns else 0}")
        st.metric("Unique Folders", f"{creative_df['creative_folder'].nunique() if not creative_df.empty and 'creative_folder' in creative_df.columns else 0}")

    with col3:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #27ae60 0%, #229954 100%); padding: 1.5rem; border-radius: 12px; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">SMS</h4>
        </div>
        """, unsafe_allow_html=True)
        if not sms_df.empty and 'sms_total' in sms_df.columns and 'date' in sms_df.columns:
            sms_daily_totals = sms_df.groupby(sms_df['date'].dt.date if hasattr(sms_df['date'], 'dt') else sms_df['date'])['sms_total'].first()
            total_sms = int(sms_daily_totals.sum())
            avg_sms_daily = sms_daily_totals.mean()
        else:
            total_sms = 0
            avg_sms_daily = 0
        st.metric("Total SMS Sent", f"{total_sms:,}")
        st.metric("SMS Types Used", f"{sms_df['sms_type'].nunique()}" if not sms_df.empty and 'sms_type' in sms_df.columns else "0")
        st.metric("Avg per Day", f"{avg_sms_daily:.0f}")

    st.divider()

    # Daily trend from P-tab data
    st.subheader("📈 Daily Activity Trend")

    fig = go.Figure()
    if has_kpi:
        a_daily = agent_kpi_df.sort_values('date')
        fig.add_trace(go.Scatter(x=a_daily['date'], y=a_daily['spend'], name='Spend ($)', line=dict(color='#3498db', width=3), mode='lines+markers'))
        fig.add_trace(go.Scatter(x=a_daily['date'], y=a_daily['ftd'], name='FTD', line=dict(color='#27ae60', width=3), mode='lines+markers', yaxis='y2'))
        fig.update_layout(
            height=350,
            yaxis=dict(title='Spend ($)', side='left'),
            yaxis2=dict(title='FTD', side='right', overlaying='y'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(l=20, r=20, t=40, b=20),
        )
    else:
        daily_creative_chart = creative_df.groupby('date').size().reset_index(name='creative_count') if not creative_df.empty else pd.DataFrame({'date': [], 'creative_count': []})
        fig.add_trace(go.Scatter(x=daily_creative_chart['date'], y=daily_creative_chart['creative_count'], name='Creatives', line=dict(color='#9b59b6', width=3), mode='lines+markers'))
        fig.update_layout(height=350, legend=dict(orientation='h', yanchor='bottom', y=1.02), margin=dict(l=20, r=20, t=40, b=20))

    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 5: INDIVIDUAL OVERALL (INDIVIDUAL KPI data)
# ============================================================

with tab5:
    st.subheader("📈 Individual Overall (INDIVIDUAL KPI)")

    if has_kpi:
        # Aggregate daily data (sum redistributed rows per date)
        agent_daily = agent_kpi_df.groupby('date').agg({
            'spend': 'sum', 'spend_php': 'sum', 'ftd': 'sum', 'register': 'sum',
            'reach': 'sum', 'impressions': 'sum', 'clicks': 'sum',
        }).reset_index().sort_values('date')

        # Recalculate derived metrics after aggregation
        agent_daily['ctr'] = agent_daily.apply(lambda r: round((r['clicks'] / r['impressions'] * 100) if r['impressions'] > 0 else 0, 2), axis=1)
        agent_daily['cpc'] = agent_daily.apply(lambda r: round((r['spend'] / r['clicks']) if r['clicks'] > 0 else 0, 2), axis=1)
        agent_daily['cpm'] = agent_daily.apply(lambda r: round((r['spend'] / r['impressions'] * 1000) if r['impressions'] > 0 else 0, 2), axis=1)
        agent_daily['cost_per_register'] = agent_daily.apply(lambda r: round((r['spend'] / r['register']) if r['register'] > 0 else 0, 2), axis=1)
        agent_daily['cost_per_ftd'] = agent_daily.apply(lambda r: round((r['spend'] / r['ftd']) if r['ftd'] > 0 else 0, 2), axis=1)
        agent_daily['conv_rate'] = agent_daily.apply(lambda r: round((r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, 2), axis=1)

        # KPI cards
        total_spend = agent_daily['spend'].sum()
        total_reg = int(agent_daily['register'].sum())
        total_ftd = int(agent_daily['ftd'].sum())
        avg_cpr = total_spend / total_reg if total_reg > 0 else 0
        avg_cpd = total_spend / total_ftd if total_ftd > 0 else 0
        conv_rate = (total_ftd / total_reg * 100) if total_reg > 0 else 0
        total_reach = int(agent_daily['reach'].sum())
        total_impr = int(agent_daily['impressions'].sum())
        total_clicks = int(agent_daily['clicks'].sum())

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Spend", f"${total_spend:,.2f}")
        c2.metric("Register", f"{total_reg:,}")
        c3.metric("FTD", f"{total_ftd:,}")
        c4.metric("CPR", f"${avg_cpr:.2f}")
        c5.metric("Cost/FTD", f"${avg_cpd:.2f}")
        c6.metric("Conv Rate", f"{conv_rate:.1f}%")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("People Reach", f"{total_reach:,}")
        c2.metric("Impressions", f"{total_impr:,}")
        c3.metric("Clicks", f"{total_clicks:,}")
        c4.metric("CTR", f"{(total_clicks / total_impr * 100) if total_impr > 0 else 0:.2f}%")

        st.divider()

        # Daily trend charts
        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['spend'], name='Spend', marker_color='#667eea'))
            fig.update_layout(height=300, title='Daily Spend', xaxis_tickformat='%m/%d', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['register'], name='Register', marker_color='#3498db'))
            fig.add_trace(go.Bar(x=agent_daily['date'], y=agent_daily['ftd'], name='FTD', marker_color='#27ae60'))
            fig.update_layout(height=300, title='Register vs FTD', xaxis_tickformat='%m/%d', barmode='group', margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # Daily data table
        st.subheader("Daily Data")
        d_display = agent_daily[['date', 'spend', 'register', 'cost_per_register', 'ftd', 'cost_per_ftd', 'conv_rate', 'reach', 'impressions', 'clicks', 'ctr', 'cpm']].copy()
        d_display = d_display.sort_values('date', ascending=False)
        d_display['date'] = d_display['date'].dt.strftime('%m/%d/%Y')
        # Format numbers with commas for display
        d_display['spend'] = d_display['spend'].apply(lambda x: f"${x:,.2f}")
        d_display['cost_per_register'] = d_display['cost_per_register'].apply(lambda x: f"${x:,.2f}")
        d_display['cost_per_ftd'] = d_display['cost_per_ftd'].apply(lambda x: f"${x:,.2f}")
        d_display['cpm'] = d_display['cpm'].apply(lambda x: f"${x:,.2f}")
        d_display['reach'] = d_display['reach'].apply(lambda x: f"{int(x):,}")
        d_display['impressions'] = d_display['impressions'].apply(lambda x: f"{int(x):,}")
        d_display['clicks'] = d_display['clicks'].apply(lambda x: f"{int(x):,}")
        d_display['conv_rate'] = d_display['conv_rate'].apply(lambda x: f"{x:.2f}%")
        d_display['ctr'] = d_display['ctr'].apply(lambda x: f"{x:.2f}%")
        st.dataframe(
            d_display,
            use_container_width=True, hide_index=True,
            column_config={
                "spend": "Spend", "cost_per_register": "CPR",
                "cost_per_ftd": "Cost/FTD", "conv_rate": "Conv %",
                "reach": "Reach", "impressions": "Impressions",
                "clicks": "Clicks", "ctr": "CTR", "cpm": "CPM",
            },
        )
    elif is_excluded:
        st.info(f"{selected_agent}'s data has been redistributed across other agents.")
    else:
        st.warning(f"No INDIVIDUAL KPI data available for {selected_agent}.")

# ============================================================
# TAB 6: BY CAMPAIGN (Ad Account breakdown from P-tabs)
# ============================================================

with tab6:
    st.subheader("🎯 By Campaign (Ad Accounts)")

    has_ad = ptab_agent and not ptab_ad.empty and ptab_agent in ptab_ad['agent'].values

    if has_ad:
        agent_ad = ptab_ad[ptab_ad['agent'] == ptab_agent].copy()

        # Aggregate by ad account
        acct_summary = agent_ad.groupby('ad_account').agg({
            'cost': 'sum', 'impressions': 'sum', 'clicks': 'sum',
        }).reset_index()
        acct_summary['ctr'] = acct_summary.apply(
            lambda x: (x['clicks'] / x['impressions'] * 100) if x['impressions'] > 0 else 0, axis=1)
        acct_summary = acct_summary.sort_values('cost', ascending=False)

        # KPI
        total_cost = acct_summary['cost'].sum()
        total_impr = int(acct_summary['impressions'].sum())
        total_clicks = int(acct_summary['clicks'].sum())
        avg_ctr = (total_clicks / total_impr * 100) if total_impr > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cost", f"${total_cost:,.2f}")
        col2.metric("Impressions", f"{total_impr:,}")
        col3.metric("Clicks", f"{total_clicks:,}")
        col4.metric("CTR", f"{avg_ctr:.2f}%")

        st.divider()

        # Cost by ad account
        fig = px.bar(
            acct_summary.sort_values('cost', ascending=True),
            y='ad_account', x='cost', orientation='h',
            title='Cost by Ad Account',
            text_auto='$.2s',
            color_discrete_sequence=['#667eea'],
        )
        fig.update_layout(height=max(300, len(acct_summary) * 45), showlegend=False, yaxis_title='')
        st.plotly_chart(fig, use_container_width=True)

        # Ad account summary table
        st.subheader("Ad Account Summary")
        acct_display = acct_summary.copy()
        acct_display['cost'] = acct_display['cost'].apply(lambda x: f"${x:,.2f}")
        acct_display['impressions'] = acct_display['impressions'].apply(lambda x: f"{int(x):,}")
        acct_display['clicks'] = acct_display['clicks'].apply(lambda x: f"{int(x):,}")
        acct_display['ctr'] = acct_display['ctr'].apply(lambda x: f"{x:.2f}%")
        acct_display = acct_display.rename(columns={
            'ad_account': 'Ad Account', 'cost': 'Cost',
            'impressions': 'Impressions', 'clicks': 'Clicks', 'ctr': 'CTR',
        })
        st.dataframe(acct_display, use_container_width=True, hide_index=True)

        # Per-account daily detail
        st.subheader("Daily Breakdown by Ad Account")
        acct_daily = agent_ad.copy()
        acct_daily['date'] = acct_daily['date'].dt.strftime('%m/%d/%Y')
        acct_daily_disp = acct_daily[['date', 'ad_account', 'cost', 'impressions', 'clicks', 'ctr']].sort_values(['date', 'ad_account'], ascending=[False, True]).copy()
        acct_daily_disp['cost'] = acct_daily_disp['cost'].apply(lambda x: f"${x:,.2f}")
        acct_daily_disp['impressions'] = acct_daily_disp['impressions'].apply(lambda x: f"{int(x):,}")
        acct_daily_disp['clicks'] = acct_daily_disp['clicks'].apply(lambda x: f"{int(x):,}")
        acct_daily_disp['ctr'] = acct_daily_disp['ctr'].apply(lambda x: f"{x:.2f}%")
        st.dataframe(
            acct_daily_disp,
            use_container_width=True, hide_index=True,
            column_config={
                "cost": "Cost", "impressions": "Impressions",
                "clicks": "Clicks", "ctr": "CTR",
            },
        )
    elif ptab_agent:
        st.warning(f"No ad account data available for {selected_agent} ({ptab_agent}).")
    else:
        st.info(f"{selected_agent} does not have a P-tab in Channel ROI.")

# ============================================================
# TAB 3: CREATIVE WORK
# ============================================================

with tab3:
    st.subheader("🎨 WITHOUT (Creative Work)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 Total Creatives", f"{len(creative_df):,}")
    with col2:
        st.metric("🎬 Unique Types", f"{creative_df['creative_type'].nunique() if not creative_df.empty and 'creative_type' in creative_df.columns else 0}")
    with col3:
        st.metric("📂 Folders Used", f"{creative_df['creative_folder'].nunique() if not creative_df.empty and 'creative_folder' in creative_df.columns else 0}")
    with col4:
        unique_content = creative_df['creative_content'].nunique() if not creative_df.empty and 'creative_content' in creative_df.columns else 0
        freshness = (unique_content / len(creative_df) * 100) if len(creative_df) > 0 else 0
        st.metric("✨ Freshness", f"{freshness:.1f}%")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🎬 Creative Type Distribution")
        if not creative_df.empty and 'creative_type' in creative_df.columns:
            type_counts = creative_df['creative_type'].value_counts().reset_index()
            type_counts.columns = ['type', 'count']
            fig = px.pie(type_counts, values='count', names='type', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No creative data available")

    with col2:
        st.subheader("📂 Content by Folder")
        if not creative_df.empty and 'creative_folder' in creative_df.columns:
            folder_counts = creative_df['creative_folder'].value_counts().reset_index()
            folder_counts.columns = ['folder', 'count']
            fig = px.bar(folder_counts, x='folder', y='count', color='count', color_continuous_scale='Purples')
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No creative data available")

    st.subheader("📅 Daily Creative Output")
    if not creative_df.empty and 'creative_type' in creative_df.columns:
        daily_creative = creative_df.groupby(['date', 'creative_type']).size().reset_index(name='count')
        fig = px.bar(daily_creative, x='date', y='count', color='creative_type', barmode='stack')
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily creative data available")

    st.subheader("📋 Creative Work Data")
    if not creative_df.empty:
        display_creative = creative_df.copy()
        display_creative['date'] = display_creative['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_creative, use_container_width=True, hide_index=True)
    else:
        st.info("No creative work data available")

# ============================================================
# TAB 4: SMS
# ============================================================

with tab4:
    st.subheader("📱 SMS Performance")

    if not sms_df.empty and 'sms_total' in sms_df.columns and 'date' in sms_df.columns:
        sms_daily = sms_df.groupby(sms_df['date'].dt.date if hasattr(sms_df['date'], 'dt') else sms_df['date'])['sms_total'].first()
        total_sms_tab4 = int(sms_daily.sum())
        avg_daily_tab4 = sms_daily.mean()
    else:
        total_sms_tab4 = 0
        avg_daily_tab4 = 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📨 Total SMS Sent", f"{total_sms_tab4:,}")
    with col2:
        st.metric("📋 SMS Types", f"{sms_df['sms_type'].nunique()}" if not sms_df.empty and 'sms_type' in sms_df.columns else "0")
    with col3:
        st.metric("📅 Days Active", f"{sms_df['date'].nunique()}" if not sms_df.empty and 'date' in sms_df.columns else "0")
    with col4:
        st.metric("📊 Avg Daily", f"{avg_daily_tab4:.0f}")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 SMS by Type")
        if not sms_df.empty and 'sms_type' in sms_df.columns and 'sms_total' in sms_df.columns:
            if 'date' in sms_df.columns:
                type_date_df = sms_df.groupby(['sms_type', sms_df['date'].dt.date if hasattr(sms_df['date'], 'dt') else sms_df['date']])['sms_total'].first().reset_index()
                sms_by_type = type_date_df.groupby('sms_type')['sms_total'].sum().reset_index()
            else:
                sms_by_type = sms_df.groupby('sms_type')['sms_total'].sum().reset_index()
            sms_by_type = sms_by_type.sort_values('sms_total', ascending=True)
            fig = px.bar(sms_by_type, x='sms_total', y='sms_type', orientation='h', color='sms_total', color_continuous_scale='Greens')
            fig.update_layout(height=400, showlegend=False, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No SMS data available")

    with col2:
        st.subheader("📈 Daily SMS Volume")
        if not sms_df.empty and 'sms_total' in sms_df.columns:
            daily_sms = sms_df.groupby('date')['sms_total'].first().reset_index()
            fig = px.area(daily_sms, x='date', y='sms_total', color_discrete_sequence=['#27ae60'])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No SMS data available")

    st.subheader("🏆 Top SMS Types")
    if not sms_df.empty and 'sms_type' in sms_df.columns:
        if 'date' in sms_df.columns:
            type_date_df = sms_df.groupby(['sms_type', sms_df['date'].dt.date if hasattr(sms_df['date'], 'dt') else sms_df['date']])['sms_total'].first().reset_index()
            top_sms = type_date_df.groupby('sms_type')['sms_total'].agg(['sum', 'count', 'mean']).reset_index()
        else:
            top_sms = sms_df.groupby('sms_type')['sms_total'].agg(['sum', 'count', 'mean']).reset_index()
        top_sms.columns = ['SMS Type', 'Total Sent', 'Days Used', 'Avg per Day']
        top_sms = top_sms.sort_values('Total Sent', ascending=False)
        st.dataframe(top_sms, use_container_width=True, hide_index=True)
    else:
        st.info("No SMS types data available")

# ============================================================
# DOWNLOAD SECTION
# ============================================================

st.divider()
st.subheader("📥 Export Data")

col1, col2 = st.columns(2)

with col1:
    csv_creative = creative_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Creative Work",
        data=csv_creative,
        file_name=f"{selected_agent}_creative_{start_date}_{end_date}.csv",
        mime="text/csv"
    )

with col2:
    csv_sms = sms_df.to_csv(index=False)
    st.download_button(
        label="📥 Download SMS Data",
        data=csv_sms,
        file_name=f"{selected_agent}_sms_{start_date}_{end_date}.csv",
        mime="text/csv"
    )
