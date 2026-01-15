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
from data_loader import load_agent_performance_data, load_agent_content_data, get_date_range

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
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True)

# Load data FIRST to determine date range
team_ads_df = pd.DataFrame()
team_creative_df = pd.DataFrame()
team_content_df = pd.DataFrame()

if use_real_data:
    with st.spinner("Loading team data from Google Sheets..."):
        team_ads_df, team_creative_df, team_content_df = load_all_team_data(AGENTS)

    if team_ads_df.empty and team_creative_df.empty:
        st.warning("Could not load team data from Google Sheets. Using sample data.")
        use_real_data = False

# Date range - constrained to available data
min_date, max_date = get_date_range(team_ads_df if not team_ads_df.empty else team_content_df)

# Convert to date objects
if hasattr(min_date, 'date'):
    min_date = min_date.date()
if hasattr(max_date, 'date'):
    max_date = max_date.date()

has_data = min_date is not None and max_date is not None and (not team_ads_df.empty or not team_content_df.empty)

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

# Data source toggle
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True)

if use_real_data:
    with st.spinner("Loading team data from Google Sheets..."):
        running_ads_df, creative_df, content_df = load_all_team_data(AGENTS)

    if running_ads_df.empty:
        st.warning("Could not load Google Sheets data. Using sample data.")
        use_real_data = False
        df = generate_team_data(AGENTS, start_date, end_date)
    else:
        # Build combined df from real data
        # Aggregate running ads by date and agent
        df = running_ads_df.copy()

        # Add content metrics if available
        if not content_df.empty and 'agent_name' in content_df.columns and 'primary_content' in content_df.columns:
            content_summary = content_df.groupby(['date', 'agent_name']).agg(
                content_posts=('primary_content', 'count'),
                unique_content=('primary_content', 'nunique')
            ).reset_index()
            df = df.merge(content_summary, on=['date', 'agent_name'], how='left')
            df['content_posts'] = df['content_posts'].fillna(0).astype(int)
            df['unique_content'] = df['unique_content'].fillna(0).astype(int)
        else:
            df['content_posts'] = 0
            df['unique_content'] = 0

        st.sidebar.success(f"Loaded {len(df)} records from Google Sheets")
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
st.subheader("📊 Team Totals")

if df.empty:
    st.info("No data available. Check if Google Sheets have data or use sample data.")
else:
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        total_ads = df['total_ad'].sum() if 'total_ad' in df.columns else 0
        st.metric("🎯 Total Ads", f"{total_ads:,}")
    with col2:
        impressions = df['impressions'].sum() if 'impressions' in df.columns else 0
        st.metric("👁️ Impressions", f"{impressions:,}")
    with col3:
        clicks = df['clicks'].sum() if 'clicks' in df.columns else 0
        st.metric("👆 Clicks", f"{clicks:,}")
    with col4:
        avg_ctr = df['ctr_percent'].mean() if 'ctr_percent' in df.columns else 0
        st.metric("📊 Avg CTR", f"{avg_ctr:.2f}%")
    with col5:
        avg_cpc = df['cpc'].mean() if 'cpc' in df.columns else 0
        st.metric("💰 Avg CPC", f"${avg_cpc:.2f}")
    with col6:
        avg_conv = df['conversion_rate'].mean() if 'conversion_rate' in df.columns else 0
        st.metric("🎯 Avg Conv", f"{avg_conv:.2f}%")

st.divider()

# Agent Cards
st.subheader("👤 Individual Agent Summary")

if not df.empty and 'agent_name' in df.columns:
    cols = st.columns(3)
    for idx, agent in enumerate(AGENTS):
        agent_df = df[df['agent_name'] == agent['name']]

        with cols[idx % 3]:
            total_ads = agent_df['total_ad'].sum() if 'total_ad' in agent_df.columns else 0
            avg_ctr = agent_df['ctr_percent'].mean() if 'ctr_percent' in agent_df.columns and not agent_df.empty else 0
            avg_conv = agent_df['conversion_rate'].mean() if 'conversion_rate' in agent_df.columns and not agent_df.empty else 0
            impressions = agent_df['impressions'].sum() if 'impressions' in agent_df.columns else 0
            content_posts = agent_df['content_posts'].sum() if 'content_posts' in agent_df.columns else 0
            unique_content = agent_df['unique_content'].sum() if 'unique_content' in agent_df.columns else 0
            freshness = (unique_content / content_posts * 100) if content_posts > 0 else 0

            # Handle NaN values
            avg_ctr = 0 if pd.isna(avg_ctr) else avg_ctr
            avg_conv = 0 if pd.isna(avg_conv) else avg_conv

            # Determine performance color
            if avg_ctr >= 3.5:
                perf_color = '#28a745'
                perf_badge = '🏆 Top Performer'
            elif avg_ctr >= 2.5:
                perf_color = '#ffc107'
                perf_badge = '⭐ Good'
            else:
                perf_color = '#dc3545'
                perf_badge = '📈 Needs Improvement'

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 1.5rem; border-radius: 12px; border-left: 5px solid {perf_color}; margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #333;">{agent['name']}</h3>
                    <span style="background: {perf_color}; color: white; padding: 4px 10px; border-radius: 15px; font-size: 0.75rem;">{perf_badge}</span>
                </div>
            <hr style="margin: 10px 0; border-color: #dee2e6;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.9rem;">
                <div><strong>Ads:</strong> {total_ads:,}</div>
                <div><strong>CTR:</strong> {avg_ctr:.2f}%</div>
                <div><strong>Impressions:</strong> {impressions:,}</div>
                <div><strong>Conv:</strong> {avg_conv:.2f}%</div>
                <div><strong>Content:</strong> {content_posts}</div>
                <div><strong>Freshness:</strong> {freshness:.0f}%</div>
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
    tab1, tab2, tab3 = st.tabs(["Performance Metrics", "Content Analysis", "Trends"])

    with tab1:
        # Check if required columns exist
        required_cols = ['ctr_percent', 'conversion_rate', 'total_ad']
        has_required = all(col in df.columns for col in required_cols)

        if has_required:
            col1, col2 = st.columns(2)

            with col1:
                # CTR Comparison
                agent_summary = df.groupby('agent_name').agg({
                    'ctr_percent': 'mean',
                    'conversion_rate': 'mean',
                    'total_ad': 'sum'
                }).reset_index()

                fig = px.bar(
                    agent_summary,
                    x='agent_name',
                    y='ctr_percent',
                    color='ctr_percent',
                    color_continuous_scale='RdYlGn',
                    title='Average CTR by Agent'
                )
                fig.add_hline(y=agent_summary['ctr_percent'].mean(), line_dash="dash", annotation_text="Team Avg")
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Conversion Rate Comparison
                fig = px.bar(
                    agent_summary,
                    x='agent_name',
                    y='conversion_rate',
                    color='conversion_rate',
                    color_continuous_scale='RdYlGn',
                    title='Average Conversion Rate by Agent'
                )
                fig.add_hline(y=agent_summary['conversion_rate'].mean(), line_dash="dash", annotation_text="Team Avg")
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            # Radar Chart
            st.subheader("🎯 Agent Performance Radar")

            # Normalize metrics for radar - only use columns that exist
            metrics = [col for col in ['total_ad', 'impressions', 'clicks', 'ctr_percent', 'conversion_rate', 'active_count'] if col in df.columns]

            if len(metrics) >= 3:
                agent_metrics = df.groupby('agent_name')[metrics].mean().reset_index()

                # Normalize to 0-100 scale
                for col in metrics:
                    max_val = agent_metrics[col].max()
                    if max_val > 0:
                        agent_metrics[col + '_norm'] = agent_metrics[col] / max_val * 100
                    else:
                        agent_metrics[col + '_norm'] = 0

                fig = go.Figure()

                metric_labels = {'total_ad': 'Total Ads', 'impressions': 'Impressions', 'clicks': 'Clicks',
                                 'ctr_percent': 'CTR', 'conversion_rate': 'Conversion', 'active_count': 'Active Ads'}

                for agent in [a['name'] for a in AGENTS]:
                    agent_data = agent_metrics[agent_metrics['agent_name'] == agent]
                    if not agent_data.empty:
                        agent_data = agent_data.iloc[0]
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
            else:
                st.info("Not enough metrics available for radar chart")
        else:
            st.info("Required columns (CTR, Conversion Rate, Total Ad) not found in data")

    with tab2:
        if 'content_posts' in df.columns and 'unique_content' in df.columns:
            col1, col2 = st.columns(2)

            with col1:
                # Content volume by agent
                content_summary = df.groupby('agent_name').agg({
                    'content_posts': 'sum',
                    'unique_content': 'sum'
                }).reset_index()
                content_summary['recycled'] = content_summary['content_posts'] - content_summary['unique_content']

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=content_summary['agent_name'],
                    y=content_summary['unique_content'],
                    name='Unique Content',
                    marker_color='#28a745'
                ))
                fig.add_trace(go.Bar(
                    x=content_summary['agent_name'],
                    y=content_summary['recycled'],
                    name='Recycled Content',
                    marker_color='#ffc107'
                ))
                fig.update_layout(barmode='stack', title='Content Volume by Agent', height=350)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Freshness score by agent
                content_summary['freshness'] = content_summary.apply(
                    lambda row: (row['unique_content'] / row['content_posts'] * 100) if row['content_posts'] > 0 else 0,
                    axis=1
                ).round(1)

                fig = px.bar(
                    content_summary,
                    x='agent_name',
                    y='freshness',
                    color='freshness',
                    color_continuous_scale='RdYlGn',
                    title='Content Freshness Score by Agent'
                )
                fig.add_hline(y=70, line_dash="dash", line_color="green", annotation_text="Target (70%)")
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Content data not available. Make sure content sheets are loaded.")

    with tab3:
        # Daily trend by agent
        trend_cols = ['total_ad', 'impressions', 'ctr_percent']
        available_trend_cols = [col for col in trend_cols if col in df.columns]

        if available_trend_cols and 'date' in df.columns:
            daily_by_agent = df.groupby(['date', 'agent_name'])[available_trend_cols].agg({
                col: 'sum' if col != 'ctr_percent' else 'mean' for col in available_trend_cols
            }).reset_index()

            metric_choice = st.selectbox("Select Metric", available_trend_cols)
            metric_labels = {'total_ad': 'Total Ads', 'impressions': 'Impressions', 'ctr_percent': 'CTR %'}

            fig = px.line(
                daily_by_agent,
                x='date',
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
    # Build aggregation dict with only available columns
    agg_dict = {}
    if 'total_ad' in df.columns:
        agg_dict['total_ad'] = 'sum'
    if 'impressions' in df.columns:
        agg_dict['impressions'] = 'sum'
    if 'clicks' in df.columns:
        agg_dict['clicks'] = 'sum'
    if 'ctr_percent' in df.columns:
        agg_dict['ctr_percent'] = 'mean'
    if 'conversion_rate' in df.columns:
        agg_dict['conversion_rate'] = 'mean'
    if 'content_posts' in df.columns:
        agg_dict['content_posts'] = 'sum'
    if 'unique_content' in df.columns:
        agg_dict['unique_content'] = 'sum'

    if agg_dict:
        leaderboard = df.groupby('agent_name').agg(agg_dict).reset_index()

        # Calculate freshness if content columns exist
        if 'content_posts' in leaderboard.columns and 'unique_content' in leaderboard.columns:
            leaderboard['freshness'] = leaderboard.apply(
                lambda row: (row['unique_content'] / row['content_posts'] * 100) if row['content_posts'] > 0 else 0,
                axis=1
            ).round(1)
        else:
            leaderboard['freshness'] = 0

        # Calculate overall score (weighted average) - use only available metrics
        score_components = []
        if 'ctr_percent' in leaderboard.columns:
            score_components.append(leaderboard['ctr_percent'].fillna(0) * 0.3)
        if 'conversion_rate' in leaderboard.columns:
            score_components.append(leaderboard['conversion_rate'].fillna(0) * 0.3)
        if 'freshness' in leaderboard.columns:
            score_components.append(leaderboard['freshness'].fillna(0) * 0.2)
        if 'total_ad' in leaderboard.columns:
            max_ads = leaderboard['total_ad'].max()
            if max_ads > 0:
                score_components.append((leaderboard['total_ad'] / max_ads * 100) * 0.2)

        if score_components:
            leaderboard['score'] = sum(score_components).round(1)
        else:
            leaderboard['score'] = 0

        leaderboard = leaderboard.sort_values('score', ascending=False).reset_index(drop=True)
        leaderboard.index = leaderboard.index + 1  # Start from 1

        # Build display columns dynamically
        display_cols = ['agent_name']
        col_names = ['Agent']
        col_config = {}

        for col, name, fmt in [
            ('total_ad', 'Total Ads', None),
            ('impressions', 'Impressions', None),
            ('clicks', 'Clicks', None),
            ('ctr_percent', 'Avg CTR %', st.column_config.NumberColumn(format="%.2f%%")),
            ('conversion_rate', 'Avg Conv %', st.column_config.NumberColumn(format="%.2f%%")),
            ('freshness', 'Freshness %', st.column_config.NumberColumn(format="%.1f%%")),
            ('score', 'Overall Score', st.column_config.ProgressColumn(min_value=0, max_value=100))
        ]:
            if col in leaderboard.columns:
                display_cols.append(col)
                col_names.append(name)
                if fmt:
                    col_config[name] = fmt

        display_leaderboard = leaderboard[display_cols].copy()
        display_leaderboard.columns = col_names

        st.dataframe(
            display_leaderboard,
            use_container_width=True,
            column_config=col_config
        )
