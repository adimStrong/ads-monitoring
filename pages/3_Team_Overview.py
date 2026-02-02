"""
Team Overview Page - Compare all agents side by side
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AGENTS
from data_loader import load_agent_performance_data, load_agent_content_data, get_date_range, load_facebook_ads_data

st.set_page_config(page_title="Team Overview", page_icon="👥", layout="wide")

# Sidebar logo
logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.jpg")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)

st.title("👥 Team Overview & Comparison")

# ============================================================
# DATA LOADING - Load real data from Google Sheets
# ============================================================

@st.cache_data(ttl=300)
def load_all_team_data(agents):
    """Load performance data for all agents from Google Sheets"""
    all_running_ads = []
    all_creative = []
    all_content = []

    for agent in agents:
        # Load performance data (running ads, creative, sms)
        running_ads_df, creative_df, sms_df = load_agent_performance_data(
            agent['name'],
            agent['sheet_performance']
        )

        if running_ads_df is not None and not running_ads_df.empty:
            all_running_ads.append(running_ads_df)

        if creative_df is not None and not creative_df.empty:
            all_creative.append(creative_df)

        # Load content data
        content_df = load_agent_content_data(
            agent['name'],
            agent['sheet_content']
        )

        if content_df is not None and not content_df.empty:
            all_content.append(content_df)

    combined_ads = pd.concat(all_running_ads, ignore_index=True) if all_running_ads else pd.DataFrame()
    combined_creative = pd.concat(all_creative, ignore_index=True) if all_creative else pd.DataFrame()
    combined_content = pd.concat(all_content, ignore_index=True) if all_content else pd.DataFrame()

    return combined_ads, combined_creative, combined_content

# Sidebar
st.sidebar.header("Filters")

# Data source toggle
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True, key="team_overview_toggle")

# Load data FIRST to determine date range
team_ads_df = pd.DataFrame()
team_creative_df = pd.DataFrame()
team_content_df = pd.DataFrame()
fb_ads_df = pd.DataFrame()

if use_real_data:
    with st.spinner("Loading team data from Google Sheets..."):
        team_ads_df, team_creative_df, team_content_df = load_all_team_data(AGENTS)

        # Load Facebook Ads data (primary source for ads metrics)
        fb_ads_df = load_facebook_ads_data()
        if fb_ads_df is not None and not fb_ads_df.empty:
            st.sidebar.success(f"Loaded {len(fb_ads_df)} Facebook Ads records")
        else:
            fb_ads_df = pd.DataFrame()

    if fb_ads_df.empty and team_creative_df.empty:
        st.warning("Could not load team data from Google Sheets. Using sample data.")
        use_real_data = False

# Date range - constrained to available data (prefer Facebook Ads)
if not fb_ads_df.empty:
    min_date, max_date = get_date_range(fb_ads_df)
elif not team_ads_df.empty:
    min_date, max_date = get_date_range(team_ads_df)
else:
    min_date, max_date = get_date_range(team_content_df)

# Convert to date objects
if hasattr(min_date, 'date'):
    min_date = min_date.date()
if hasattr(max_date, 'date'):
    max_date = max_date.date()

has_data = min_date is not None and max_date is not None and (not fb_ads_df.empty or not team_content_df.empty)

if has_data:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        default_start = max(min_date, max_date - timedelta(days=14))
        start_date = st.date_input(
            "From",
            value=default_start,
            min_value=min_date,
            max_value=max_date
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=max_date,
            min_value=min_date,
            max_value=max_date
        )
    st.sidebar.caption(f"Data: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("To", datetime.now())

# Generate sample data (fallback)
def generate_team_data(agents, start_date, end_date):
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    data = []

    for agent in agents:
        random.seed(hash(agent['name']))
        for date in dates:
            data.append({
                'date': date,
                'agent_name': agent['name'],
                'total_ad': random.randint(5, 25),
                'impressions': random.randint(2000, 15000),
                'clicks': random.randint(100, 800),
                'ctr_percent': round(random.uniform(1.5, 5.5), 2),
                'cpc': round(random.uniform(0.3, 2.5), 2),
                'conversion_rate': round(random.uniform(0.8, 4.0), 2),
                'active_count': random.randint(5, 20),
                'content_posts': random.randint(3, 8),
                'unique_content': random.randint(2, 6),
            })

    return pd.DataFrame(data)

# Build df from Facebook Ads data (primary source)
if use_real_data and not fb_ads_df.empty:
    # Use Facebook Ads as primary data source
    df = fb_ads_df.copy()
    df['agent_name'] = df['person_name']  # Map person_name to agent_name for compatibility
else:
    df = generate_team_data(AGENTS, start_date, end_date)

# Header
st.markdown(f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
    <h2 style="margin: 0;">Team Performance Overview</h2>
    <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')} • {len(AGENTS)} agents</p>
</div>
""", unsafe_allow_html=True)

# Team Summary Metrics
st.subheader("📊 Team Totals (Facebook Ads)")

if df.empty:
    st.info("No data available. Check if Google Sheets have data or use sample data.")
else:
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        total_spend = df['spend'].sum() if 'spend' in df.columns else 0
        st.metric("💵 Total Spend", f"${total_spend:,.2f}")
    with col2:
        impressions = int(df['impressions'].sum()) if 'impressions' in df.columns else 0
        st.metric("👁️ Impressions", f"{impressions:,}")
    with col3:
        clicks = int(df['clicks'].sum()) if 'clicks' in df.columns else 0
        st.metric("👆 Clicks", f"{clicks:,}")
    with col4:
        avg_ctr = (clicks / impressions * 100) if impressions > 0 else 0
        st.metric("📊 CTR", f"{avg_ctr:.2f}%")
    with col5:
        register = int(df['register'].sum()) if 'register' in df.columns else 0
        st.metric("📝 Register", f"{register:,}")
    with col6:
        ftd = int(df['result_ftd'].sum()) if 'result_ftd' in df.columns else 0
        st.metric("💰 FTD", f"{ftd:,}")

st.divider()

# Agent Cards
st.subheader("👤 Individual Agent Summary")

if not df.empty and 'agent_name' in df.columns:
    # Get unique agents from Facebook Ads data
    fb_agents = df['agent_name'].unique().tolist()
    cols = st.columns(3)

    for idx, agent_name in enumerate(fb_agents):
        agent_df = df[df['agent_name'] == agent_name]

        with cols[idx % 3]:
            spend = agent_df['spend'].sum() if 'spend' in agent_df.columns else 0
            impressions = int(agent_df['impressions'].sum()) if 'impressions' in agent_df.columns else 0
            reach = int(agent_df['reach'].sum()) if 'reach' in agent_df.columns else 0
            clicks = int(agent_df['clicks'].sum()) if 'clicks' in agent_df.columns else 0
            register = int(agent_df['register'].sum()) if 'register' in agent_df.columns else 0
            ftd = int(agent_df['result_ftd'].sum()) if 'result_ftd' in agent_df.columns else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (spend / clicks) if clicks > 0 else 0
            cpr = (spend / register) if register > 0 else 0
            cpftd = (spend / ftd) if ftd > 0 else 0

            # Determine performance color based on FTD
            if ftd >= 30:
                perf_color = '#28a745'
                perf_badge = '🏆 Top Performer'
            elif ftd >= 15:
                perf_color = '#ffc107'
                perf_badge = '⭐ Good'
            else:
                perf_color = '#17a2b8'
                perf_badge = '📈 Active'

            # Format CPR and CPFTD display
            cpr_display = f"${cpr:,.2f}" if cpr > 0 else "-"
            cpftd_display = f"${cpftd:,.2f}" if cpftd > 0 else "-"

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 1.5rem; border-radius: 12px; border-left: 5px solid {perf_color}; margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #333;">{agent_name}</h3>
                    <span style="background: {perf_color}; color: white; padding: 4px 10px; border-radius: 15px; font-size: 0.75rem;">{perf_badge}</span>
                </div>
            <hr style="margin: 10px 0; border-color: #dee2e6;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
                <div><strong>Spend:</strong> ${spend:,.2f}</div>
                <div><strong>FTD:</strong> {ftd:,}</div>
                <div><strong>Impressions:</strong> {impressions:,}</div>
                <div><strong>Register:</strong> {register:,}</div>
                <div><strong>Reach:</strong> {reach:,}</div>
                <div><strong>Clicks:</strong> {clicks:,}</div>
                <div><strong>CTR:</strong> {ctr:.2f}%</div>
                <div><strong>CPC:</strong> ${cpc:.2f}</div>
                <div><strong>CPR:</strong> {cpr_display}</div>
                <div><strong>Cost/FTD:</strong> {cpftd_display}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    st.info("No agent data available for display.")

st.divider()

# Comparison Charts
st.subheader("📈 Performance Comparison")

if df.empty or 'agent_name' not in df.columns:
    st.info("No data available for comparison charts.")
else:
    tab1, tab2 = st.tabs(["Performance Metrics", "Trends"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            # Spend by Agent
            agent_summary = df.groupby('agent_name').agg({
                'spend': 'sum',
                'impressions': 'sum',
                'clicks': 'sum',
                'register': 'sum',
                'result_ftd': 'sum'
            }).reset_index()

            fig = px.bar(
                agent_summary,
                x='agent_name',
                y='spend',
                color='spend',
                color_continuous_scale='Blues',
                title='Total Spend by Agent'
            )
            fig.add_hline(y=agent_summary['spend'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # FTD by Agent
            fig = px.bar(
                agent_summary,
                x='agent_name',
                y='result_ftd',
                color='result_ftd',
                color_continuous_scale='Greens',
                title='FTD by Agent'
            )
            fig.add_hline(y=agent_summary['result_ftd'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Radar Chart
        st.subheader("🎯 Agent Performance Radar")

        metrics = ['spend', 'impressions', 'clicks', 'register', 'result_ftd']
        agent_metrics = df.groupby('agent_name')[metrics].sum().reset_index()

        # Normalize to 0-100 scale
        for col in metrics:
            max_val = agent_metrics[col].max()
            if max_val > 0:
                agent_metrics[col + '_norm'] = agent_metrics[col] / max_val * 100
            else:
                agent_metrics[col + '_norm'] = 0

        fig = go.Figure()

        metric_labels = {'spend': 'Spend', 'impressions': 'Impressions', 'clicks': 'Clicks',
                         'register': 'Register', 'result_ftd': 'FTD'}

        for agent in agent_metrics['agent_name'].unique():
            agent_data = agent_metrics[agent_metrics['agent_name'] == agent].iloc[0]
            fig.add_trace(go.Scatterpolar(
                r=[agent_data.get(f'{m}_norm', 0) for m in metrics],
                theta=[metric_labels.get(m, m) for m in metrics],
                fill='toself',
                name=agent
            ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True,
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Daily trend by agent
        if 'date' in df.columns:
            df['date_only'] = pd.to_datetime(df['date']).dt.date
            daily_by_agent = df.groupby(['date_only', 'agent_name']).agg({
                'spend': 'sum',
                'impressions': 'sum',
                'clicks': 'sum',
                'register': 'sum',
                'result_ftd': 'sum'
            }).reset_index()

            metric_choice = st.selectbox("Select Metric", ['spend', 'impressions', 'clicks', 'register', 'result_ftd'])
            metric_labels = {'spend': 'Spend ($)', 'impressions': 'Impressions', 'clicks': 'Clicks', 'register': 'Register', 'result_ftd': 'FTD'}

            fig = px.line(
                daily_by_agent,
                x='date_only',
                y=metric_choice,
                color='agent_name',
                title=f'{metric_labels.get(metric_choice, metric_choice)} Trend by Agent',
                markers=True
            )
            fig.update_layout(height=400, legend=dict(orientation='h', yanchor='bottom', y=1.02))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data available for trend analysis")

# Leaderboard
st.divider()
st.subheader("🏆 Agent Leaderboard")

if df.empty or 'agent_name' not in df.columns:
    st.info("No data available for leaderboard")
else:
    # Build leaderboard from Facebook Ads data
    leaderboard = df.groupby('agent_name').agg({
        'spend': 'sum',
        'impressions': 'sum',
        'clicks': 'sum',
        'reach': 'sum',
        'register': 'sum',
        'result_ftd': 'sum'
    }).reset_index()

    # Calculate derived metrics
    leaderboard['ctr'] = (leaderboard['clicks'] / leaderboard['impressions'] * 100).round(2)
    leaderboard['cpr'] = (leaderboard['spend'] / leaderboard['register']).round(2)
    leaderboard['cpftd'] = (leaderboard['spend'] / leaderboard['result_ftd']).round(2)

    # Handle inf/nan
    leaderboard = leaderboard.replace([float('inf'), float('-inf')], 0).fillna(0)

    # Sort by FTD descending
    leaderboard = leaderboard.sort_values('result_ftd', ascending=False).reset_index(drop=True)

    # Add rank column
    leaderboard['rank'] = range(1, len(leaderboard) + 1)

    # Rename for display - cleaner columns
    display_leaderboard = leaderboard[['rank', 'agent_name', 'spend', 'register', 'result_ftd', 'cpr', 'cpftd']].copy()
    display_leaderboard.columns = ['#', 'Agent', 'Spend', 'Register', 'FTD', 'CPR', 'Cost/FTD']

    st.dataframe(
        display_leaderboard,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Agent": st.column_config.TextColumn(width="medium"),
            "Spend": st.column_config.NumberColumn(format="$,.2f", width="small"),
            "Register": st.column_config.NumberColumn(format=",d", width="small"),
            "FTD": st.column_config.NumberColumn(format=",d", width="small"),
            "CPR": st.column_config.NumberColumn(format="$,.2f", width="small"),
            "Cost/FTD": st.column_config.NumberColumn(format="$,.2f", width="small"),
        }
    )

    # Show detailed metrics in expandable section
    with st.expander("📊 View All Metrics"):
        detail_df = leaderboard[['agent_name', 'spend', 'impressions', 'reach', 'clicks', 'ctr', 'register', 'result_ftd', 'cpr', 'cpftd']].copy()
        detail_df.columns = ['Agent', 'Spend', 'Impressions', 'Reach', 'Clicks', 'CTR %', 'Register', 'FTD', 'CPR', 'Cost/FTD']

        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Spend": st.column_config.NumberColumn(format="$,.2f"),
                "Impressions": st.column_config.NumberColumn(format=",d"),
                "Reach": st.column_config.NumberColumn(format=",d"),
                "Clicks": st.column_config.NumberColumn(format=",d"),
                "CTR %": st.column_config.NumberColumn(format="%.2f%%"),
                "Register": st.column_config.NumberColumn(format=",d"),
                "FTD": st.column_config.NumberColumn(format=",d"),
                "CPR": st.column_config.NumberColumn(format="$,.2f"),
                "Cost/FTD": st.column_config.NumberColumn(format="$,.2f"),
            }
        )
