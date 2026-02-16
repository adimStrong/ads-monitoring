"""
BINGO365 Daily Monitoring Dashboard
Main Streamlit Application - v2.1
"""
import streamlit as st

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Advertiser KPI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import random

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PAGE_TITLE, PAGE_ICON, AGENTS, SMS_TYPES
from data_loader import load_all_data, get_date_range
from channel_data_loader import load_agent_performance_data as load_ptab_data

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .section-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0.8rem;
        border-radius: 8px;
        color: white;
        margin: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .agent-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


def load_sample_data():
    """Load sample data matching actual Google Sheets structure"""
    dates = pd.date_range(start='2026-01-01', end='2026-01-07', freq='D')
    agents = [a['name'] for a in AGENTS]

    # ============================================================
    # SECTION 1: WITH RUNNING ADS data
    # ============================================================
    running_ads_data = []
    for agent in agents:
        random.seed(hash(agent))
        for date in dates:
            running_ads_data.append({
                'date': date,
                'agent_name': agent,
                'total_ad': random.randint(5, 25),
                'campaign': f"Campaign_{random.randint(1, 5)}",
                'impressions': random.randint(2000, 15000),
                'clicks': random.randint(100, 800),
                'ctr_percent': round(random.uniform(1.5, 5.5), 2),
                'cpc': round(random.uniform(0.3, 2.5), 2),
                'conversion_rate': round(random.uniform(0.8, 4.0), 2),
                'rejected_count': random.randint(0, 5),
                'deleted_count': random.randint(0, 3),
                'active_count': random.randint(5, 20),
                'amount_spent': round(random.uniform(500, 5000), 2),  # NEW
                'cpr': round(random.uniform(5, 50), 2),  # NEW - Cost Per Result
            })

    # ============================================================
    # SECTION 2: WITHOUT (Creative Work) data
    # ============================================================
    creative_types = ['WH/G', 'Banner', 'Video', 'Static', 'Carousel']
    creative_data = []
    for agent in agents:
        random.seed(hash(agent) + 1)
        for date in dates:
            num_creatives = random.randint(1, 5)
            for i in range(num_creatives):
                creative_data.append({
                    'date': date,
                    'agent_name': agent,
                    'creative_type': random.choice(creative_types),
                    'creative_content': random.choice([
                        "36.5 SIGN UP BONUS LIBRENG 277, 20 MINIMUM DEPOSIT",
                        "LIBRENG 8,888 Sign Up Bonus!",
                        "277% DEPOSIT BONUS - Limited time!",
                        "Download the app now and get 500!",
                        "No more SANA ALL! Register na!",
                        "BENTE MO, GAWIN NATING LIBO!",
                    ]),
                    'caption': f"Caption {i+1}",
                })

    # ============================================================
    # SECTION 3: SMS data
    # ============================================================
    sms_data = []
    for agent in agents:
        random.seed(hash(agent) + 2)
        for date in dates:
            for sms_type in random.sample(SMS_TYPES, k=random.randint(3, 6)):
                sms_data.append({
                    'date': date,
                    'agent_name': agent,
                    'sms_type': sms_type,
                    'sms_total': random.randint(3, 10),
                })

    # ============================================================
    # CONTENT TAB data (Primary Content Analysis)
    # ============================================================
    content_templates = [
        "36.5 SIGN UP BONUS - Register now!",
        "20 MINIMUM DEPOSIT - Start playing!",
        "277% DEPOSIT BONUS - Limited time!",
        "Libreng 8,888 Sign Up Bonus!",
        "Download the app now!",
        "Claim your Bonus now!",
        "No more SANA ALL! Register na!",
        "BENTE MO, GAWIN NATING LIBO!",
        "Weekly cashback up to 8%",
        "Get up to 150% deposit bonus everyday",
    ]

    content_data = []
    for agent in agents:
        random.seed(hash(agent) + 3)
        for date in dates:
            num_posts = random.randint(2, 6)
            for _ in range(num_posts):
                content_data.append({
                    'date': date,
                    'agent_name': agent,
                    'content_type': random.choice(['Primary Text', 'Headline']),
                    'primary_content': random.choice(content_templates),
                    'condition': random.choice(['New', 'Existing', 'Adjusted']),
                    'status': random.choice(['Active', 'Pending', 'Approved']),
                })

    return (
        pd.DataFrame(running_ads_data),
        pd.DataFrame(creative_data),
        pd.DataFrame(sms_data),
        pd.DataFrame(content_data)
    )


def main():
    # Header with logo
    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.jpg")
        if os.path.exists(logo_path):
            st.image(logo_path, width=100)
    with col_title:
        st.markdown('<h1 class="main-header">Advertiser KPI Dashboard</h1>', unsafe_allow_html=True)

    # Sidebar
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.jpg")
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, width=120)
    st.sidebar.title("Navigation")

    # Data source toggle
    use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True)

    # Force refresh button to clear cache and reload data
    if st.sidebar.button("🔄 Force Refresh", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # Send Real-Time Report button
    if st.sidebar.button("📤 Send Report to Telegram", type="secondary"):
        try:
            from telegram_reporter import TelegramReporter
            from realtime_reporter import (
                get_latest_date_data, load_previous_report, compare_with_previous,
                check_low_spend, detect_no_change_agents, generate_text_summary,
                prepare_report_data, save_current_report
            )
            from config import NO_CHANGE_ALERT

            with st.spinner("Generating and sending report to Telegram..."):
                # Get data
                current_data, latest_date = get_latest_date_data()
                if current_data is None or current_data.empty:
                    st.sidebar.error("No data available")
                else:
                    # Load previous for comparison
                    previous_data = load_previous_report()
                    changes = compare_with_previous(current_data, previous_data, latest_date)
                    low_spend = check_low_spend(current_data)
                    no_change = detect_no_change_agents(changes) if NO_CHANGE_ALERT else []

                    # Generate text summary
                    text_summary = generate_text_summary(
                        current_data, latest_date, changes, low_spend, no_change
                    )

                    # Send to Telegram
                    reporter = TelegramReporter()
                    reporter.send_message(text_summary)

                    # Save for next comparison
                    report_data = prepare_report_data(current_data, latest_date)
                    save_current_report(report_data)

                    st.sidebar.success("✅ Report sent to Telegram!")
        except ValueError as e:
            st.sidebar.error(f"⚠️ Telegram not configured: {e}")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")

    # Load data
    if use_real_data:
        st.sidebar.info("Loading from Google Sheets...")
        running_ads_df, creative_df, sms_df, content_df = load_all_data()

        # Load P-tab data (replaces Facebook Ads data)
        ptab_data = load_ptab_data()
        ptab_daily = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
        if not ptab_daily.empty:
            st.sidebar.success(f"Loaded {len(ptab_daily)} P-tab daily records")
        else:
            ptab_daily = pd.DataFrame()

        if running_ads_df.empty and creative_df.empty and sms_df.empty:
            st.error("Could not load data from Google Sheets. Make sure the sheet is publicly accessible.")
            st.info("Google Sheets ID: 1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ")
            st.warning("Falling back to sample data...")
            running_ads_df, creative_df, sms_df, content_df = load_sample_data()
        else:
            st.sidebar.success(f"Loaded {len(running_ads_df)} ad records")
    else:
        running_ads_df, creative_df, sms_df, content_df = load_sample_data()
        ptab_daily = pd.DataFrame()

    # Date filter with auto-detection from data - prefer P-tab data
    if not ptab_daily.empty and 'date' in ptab_daily.columns:
        ptab_daily['date'] = pd.to_datetime(ptab_daily['date'])
        min_date = ptab_daily['date'].min()
        max_date = ptab_daily['date'].max()
    else:
        min_date, max_date = get_date_range(running_ads_df)

    # Convert to date objects if they're datetime
    if hasattr(min_date, 'date'):
        min_date = min_date.date()
    if hasattr(max_date, 'date'):
        max_date = max_date.date()

    st.sidebar.subheader("Data Date")

    # Check if we have valid data range
    has_data = min_date is not None and max_date is not None and min_date <= max_date

    if has_data:
        # Use latest available date automatically (no dropdown)
        start_date = max_date
        end_date = max_date
        st.sidebar.info(f"📅 Latest: **{max_date.strftime('%b %d, %Y')}**")
        st.sidebar.caption(f"Data range: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")
    else:
        st.sidebar.warning("No data available")
        start_date = datetime.now().date()
        end_date = datetime.now().date()

    # Agent filter
    st.sidebar.subheader("Agent Filter")
    agent_options = ['All Agents'] + [a['name'] for a in AGENTS]
    selected_agent = st.sidebar.selectbox("Select Agent", agent_options)

    # Filter data
    if selected_agent != 'All Agents':
        running_ads_df = running_ads_df[running_ads_df['agent_name'] == selected_agent]
        creative_df = creative_df[creative_df['agent_name'] == selected_agent]
        sms_df = sms_df[sms_df['agent_name'] == selected_agent]
        content_df = content_df[content_df['agent_name'] == selected_agent]

    if selected_agent != 'All Agents' and not ptab_daily.empty and 'agent' in ptab_daily.columns:
        ptab_daily = ptab_daily[ptab_daily['agent'] == selected_agent]

    running_ads_df = running_ads_df[
        (running_ads_df['date'] >= pd.Timestamp(start_date)) &
        (running_ads_df['date'] <= pd.Timestamp(end_date))
    ]
    creative_df = creative_df[
        (creative_df['date'] >= pd.Timestamp(start_date)) &
        (creative_df['date'] <= pd.Timestamp(end_date))
    ]
    sms_df = sms_df[
        (sms_df['date'] >= pd.Timestamp(start_date)) &
        (sms_df['date'] <= pd.Timestamp(end_date))
    ]
    content_df = content_df[
        (content_df['date'] >= pd.Timestamp(start_date)) &
        (content_df['date'] <= pd.Timestamp(end_date))
    ]

    if not ptab_daily.empty and 'date' in ptab_daily.columns:
        ptab_daily = ptab_daily[
            (ptab_daily['date'] >= pd.Timestamp(start_date)) &
            (ptab_daily['date'] <= pd.Timestamp(end_date))
        ]

    # Main content tabs (Running Ads removed - now uses Facebook Ads data)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Facebook Ads",
        "Creative Work",
        "SMS",
        "Content Analysis"
    ])

    with tab1:
        render_overview(running_ads_df, creative_df, sms_df, content_df, ptab_daily)

    with tab2:
        render_facebook_ads(ptab_daily)

    with tab3:
        render_creative_work(creative_df, selected_agent)

    with tab4:
        render_sms(sms_df, selected_agent)

    with tab5:
        render_content_analysis(content_df, selected_agent)


def render_overview(running_ads_df, creative_df, sms_df, content_df, ptab_daily=None):
    """Render overview tab with all sections"""
    st.subheader("Team Overview")

    # ============================================================
    # SECTION 1: WITH RUNNING ADS Summary (from P-tab data)
    # ============================================================
    st.markdown('<div class="section-header"><h3>WITH RUNNING ADS</h3></div>', unsafe_allow_html=True)

    if ptab_daily is not None and not ptab_daily.empty and 'agent' in ptab_daily.columns:
        # Summary metrics from P-tab data
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        total_cost = ptab_daily['cost'].sum()
        total_impressions = ptab_daily['impressions'].sum()
        total_clicks = ptab_daily['clicks'].sum()
        total_register = ptab_daily['register'].sum()
        total_ftd = ptab_daily['ftd'].sum()
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        with col1:
            st.metric("Total Cost", f"${total_cost:,.2f}")
        with col2:
            st.metric("Impressions", f"{int(total_impressions):,}")
        with col3:
            st.metric("Clicks", f"{int(total_clicks):,}")
        with col4:
            st.metric("CTR", f"{avg_ctr:.2f}%")
        with col5:
            st.metric("Register", f"{int(total_register):,}")
        with col6:
            st.metric("FTD", f"{int(total_ftd):,}")

        # Agent breakdown table
        st.subheader("📊 Performance by Agent")

        agent_summary = ptab_daily.groupby('agent').agg({
            'cost': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'register': 'sum',
            'ftd': 'sum',
        }).reset_index()

        # Calculate derived metrics
        agent_summary['ctr'] = (agent_summary['clicks'] / agent_summary['impressions'] * 100).round(2)
        agent_summary['cpr'] = (agent_summary['cost'] / agent_summary['register']).round(2)
        agent_summary['cpftd'] = (agent_summary['cost'] / agent_summary['ftd']).round(2)
        agent_summary['conv_rate'] = (agent_summary['ftd'] / agent_summary['register'] * 100).round(1)

        # Handle inf/nan
        agent_summary = agent_summary.replace([float('inf'), float('-inf')], 0).fillna(0)

        # Sort by FTD descending
        agent_summary = agent_summary.sort_values('ftd', ascending=False)

        # Rename and reorder columns for display
        agent_summary = agent_summary.rename(columns={
            'agent': 'Agent',
            'cost': 'Cost',
            'impressions': 'Impressions',
            'clicks': 'Clicks',
            'ctr': 'CTR',
            'register': 'Register',
            'ftd': 'FTD',
            'cpr': 'CPR',
            'cpftd': 'Cost/FTD',
            'conv_rate': 'Conv %'
        })
        agent_summary = agent_summary[['Agent', 'Cost', 'Impressions', 'Clicks', 'CTR', 'Register', 'FTD', 'CPR', 'Cost/FTD', 'Conv %']]

        # Convert to proper types
        agent_summary['Impressions'] = agent_summary['Impressions'].astype(int)
        agent_summary['Clicks'] = agent_summary['Clicks'].astype(int)
        agent_summary['Register'] = agent_summary['Register'].astype(int)
        agent_summary['FTD'] = agent_summary['FTD'].astype(int)

        # Format for display
        st.dataframe(
            agent_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Agent": st.column_config.TextColumn(width="medium"),
                "Cost": st.column_config.NumberColumn(format="$ %.2f"),
                "Impressions": st.column_config.NumberColumn(format="%d"),
                "Clicks": st.column_config.NumberColumn(format="%d"),
                "CTR": st.column_config.NumberColumn(format="%.2f%%"),
                "Register": st.column_config.NumberColumn(format="%d"),
                "FTD": st.column_config.NumberColumn(format="%d"),
                "CPR": st.column_config.NumberColumn(format="$ %.2f"),
                "Cost/FTD": st.column_config.NumberColumn(format="$ %.2f"),
                "Conv %": st.column_config.NumberColumn(format="%.1f%%"),
            }
        )
    else:
        st.info("No P-tab data available. Check Channel ROI sheet P6-P13 tabs.")

    # ============================================================
    # SECTION 2: WITHOUT (Creative Work) Summary
    # ============================================================
    st.markdown('<div class="section-header"><h3>WITHOUT (Creative Work)</h3></div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Creatives", f"{len(creative_df):,}")
    with col2:
        unique_creatives = creative_df['creative_content'].nunique()
        st.metric("Unique Creatives", f"{unique_creatives:,}")
    with col3:
        creative_types = creative_df['creative_type'].nunique()
        st.metric("Creative Types", f"{creative_types:,}")
    with col4:
        freshness = (unique_creatives / len(creative_df) * 100) if len(creative_df) > 0 else 0
        st.metric("Freshness Score", f"{freshness:.1f}%")

    # ============================================================
    # SECTION 3: SMS Summary
    # ============================================================
    st.markdown('<div class="section-header"><h3>SMS</h3></div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Group by date first to avoid double-counting (sms_total is daily total)
        if 'sms_total' in sms_df.columns and 'date' in sms_df.columns:
            daily_sms_totals = sms_df.groupby(sms_df['date'].dt.date)['sms_total'].first()
            sms_total_sum = daily_sms_totals.sum()
        else:
            sms_total_sum = 0
        st.metric("Total SMS Sent", f"{int(sms_total_sum):,}")
    with col2:
        unique_sms = sms_df['sms_type'].nunique()
        st.metric("SMS Types Used", f"{unique_sms:,}")
    with col3:
        # Average per day
        if 'sms_total' in sms_df.columns and 'date' in sms_df.columns:
            daily_sms_totals = sms_df.groupby(sms_df['date'].dt.date)['sms_total'].first()
            avg_sms = daily_sms_totals.mean() if len(daily_sms_totals) > 0 else 0
        else:
            avg_sms = 0
        st.metric("Avg per Day", f"{avg_sms:.1f}")
    with col4:
        top_sms = sms_df['sms_type'].mode().iloc[0] if len(sms_df) > 0 and 'sms_type' in sms_df.columns else "N/A"
        st.metric("Top SMS", top_sms[:20] + "..." if len(str(top_sms)) > 20 else str(top_sms))

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Daily Ad Results Trend")
        if ptab_daily is not None and not ptab_daily.empty:
            daily_results = ptab_daily.copy()
            daily_results['date_only'] = pd.to_datetime(daily_results['date']).dt.date
            daily_agg = daily_results.groupby('date_only').agg({
                'cost': 'sum',
                'register': 'sum',
                'ftd': 'sum'
            }).reset_index()
            daily_agg = daily_agg.sort_values('date_only')

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=daily_agg['date_only'],
                y=daily_agg['register'],
                name='Register',
                marker_color='#3498db',
                text=daily_agg['register'].astype(int),
                textposition='outside'
            ))
            fig.add_trace(go.Bar(
                x=daily_agg['date_only'],
                y=daily_agg['ftd'],
                name='FTD',
                marker_color='#2ecc71',
                text=daily_agg['ftd'].astype(int),
                textposition='outside'
            ))
            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis_tickformat='%Y-%m-%d',
                barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
            )
            fig.update_xaxes(type='category')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No P-tab data available")

    with col2:
        st.subheader("Agent Ad Results Comparison")
        if ptab_daily is not None and not ptab_daily.empty and 'agent' in ptab_daily.columns:
            agent_results = ptab_daily.groupby('agent').agg({
                'cost': 'sum',
                'register': 'sum',
                'ftd': 'sum'
            }).reset_index()
            agent_results = agent_results[agent_results['agent'] != '']
            agent_results = agent_results.sort_values('ftd', ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=agent_results['agent'],
                y=agent_results['register'],
                name='Register',
                marker_color='#3498db',
                text=agent_results['register'].astype(int),
                textposition='outside'
            ))
            fig.add_trace(go.Bar(
                x=agent_results['agent'],
                y=agent_results['ftd'],
                name='FTD',
                marker_color='#2ecc71',
                text=agent_results['ftd'].astype(int),
                textposition='outside'
            ))
            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No P-tab data available")

    # Agent summary table
    st.subheader("Agent Summary (All Sections)")

    # Use P-tab data for ads metrics (if available)
    if ptab_daily is not None and not ptab_daily.empty and 'agent' in ptab_daily.columns:
        # Aggregate P-tab data by agent
        agent_ads = ptab_daily.groupby('agent').agg({
            'cost': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'register': 'sum',
            'ftd': 'sum'
        }).round(2)
        agent_ads['ctr'] = (agent_ads['clicks'] / agent_ads['impressions'] * 100).round(2)
        agent_ads['cpc'] = (agent_ads['cost'] / agent_ads['clicks']).round(2)
        agent_ads = agent_ads.replace([float('inf'), float('-inf')], 0).fillna(0)
        agent_ads.index.name = 'agent_name'
    else:
        # Fallback to empty DataFrame
        agent_ads = pd.DataFrame(columns=['cost', 'impressions', 'clicks', 'register', 'ftd', 'ctr', 'cpc'])
        agent_ads.index.name = 'agent_name'

    # Creative data
    agent_creative = creative_df.groupby('agent_name').size().rename('creatives') if not creative_df.empty else pd.Series(dtype=int, name='creatives')

    # SMS data - Group by date first to avoid double-counting sms_total
    if not sms_df.empty and 'sms_total' in sms_df.columns and 'date' in sms_df.columns:
        daily_sms = sms_df.groupby(['agent_name', sms_df['date'].dt.date])['sms_total'].first().reset_index()
        agent_sms = daily_sms.groupby('agent_name')['sms_total'].sum().rename('sms_total')
    elif not sms_df.empty:
        agent_sms = sms_df.groupby('agent_name').size().rename('sms_total')
    else:
        agent_sms = pd.Series(dtype=int, name='sms_total')

    # Content data - Only count Primary Text for copywriting
    if not content_df.empty:
        if 'content_type' in content_df.columns:
            primary_content_df = content_df[content_df['content_type'] == 'Primary Text']
        else:
            primary_content_df = content_df
        agent_content = primary_content_df.groupby('agent_name').size().rename('content_posts')
    else:
        agent_content = pd.Series(dtype=int, name='content_posts')

    # Combine all data
    summary = agent_ads.join(agent_creative).join(agent_sms).join(agent_content).reset_index()

    # Rename columns for display
    summary.columns = ['Agent', 'Cost', 'Impressions', 'Clicks', 'Register', 'FTD', 'CTR %', 'CPC', 'Creatives', 'SMS Total', 'Content Posts']
    summary = summary.fillna(0)

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cost": st.column_config.NumberColumn(format="$ %.2f"),
            "Impressions": st.column_config.NumberColumn(format="%d"),
            "Clicks": st.column_config.NumberColumn(format="%d"),
            "Register": st.column_config.NumberColumn(format="%d"),
            "FTD": st.column_config.NumberColumn(format="%d"),
            "CTR %": st.column_config.NumberColumn(format="%.2f%%"),
            "CPC": st.column_config.NumberColumn(format="$ %.2f"),
            "Creatives": st.column_config.NumberColumn(format="%d"),
            "SMS Total": st.column_config.NumberColumn(format="%d"),
            "Content Posts": st.column_config.NumberColumn(format="%d"),
        }
    )


def render_facebook_ads(ptab_daily):
    """Render Facebook Ads tab using P-tab data"""
    st.subheader("💰 Facebook Ads Performance")

    if ptab_daily is None or ptab_daily.empty:
        st.warning("No P-tab data available.")
        return

    # Summary metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    total_cost = ptab_daily['cost'].sum()
    total_impressions = ptab_daily['impressions'].sum()
    total_clicks = ptab_daily['clicks'].sum()
    total_register = ptab_daily['register'].sum()
    total_ftd = ptab_daily['ftd'].sum()
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

    with col1:
        st.metric("Total Cost", f"${total_cost:,.2f}")
    with col2:
        st.metric("Impressions", f"{int(total_impressions):,}")
    with col3:
        st.metric("Clicks", f"{int(total_clicks):,}")
    with col4:
        st.metric("CTR", f"{avg_ctr:.2f}%")
    with col5:
        st.metric("Register", f"{int(total_register):,}")
    with col6:
        st.metric("FTD", f"{int(total_ftd):,}")

    st.divider()

    # AGENT COMPARISON - COST VS RESULTS
    st.subheader("Agent Comparison: Cost vs Results")

    if 'agent' in ptab_daily.columns:
        # Aggregate data by agent
        agent_compare = ptab_daily.groupby('agent').agg({
            'cost': 'sum',
            'register': 'sum',
            'ftd': 'sum'
        }).reset_index()
        agent_compare = agent_compare[agent_compare['agent'] != '']
        agent_compare = agent_compare.sort_values('ftd', ascending=False)

        # Calculate Cost per FTD
        agent_compare['cost_per_ftd'] = (agent_compare['cost'] / agent_compare['ftd']).round(2)
        agent_compare['cost_per_ftd'] = agent_compare['cost_per_ftd'].replace([float('inf')], 0).fillna(0)

        # Combined Cost & FTD Bar Chart
        fig_combined = go.Figure()

        fig_combined.add_trace(go.Bar(
            x=agent_compare['agent'],
            y=agent_compare['cost'],
            name='Cost ($)',
            marker_color='#e74c3c',
            text=agent_compare['cost'].apply(lambda x: f'${x:,.0f}'),
            textposition='outside',
            yaxis='y'
        ))

        fig_combined.add_trace(go.Bar(
            x=agent_compare['agent'],
            y=agent_compare['ftd'],
            name='FTD',
            marker_color='#2ecc71',
            text=agent_compare['ftd'].apply(lambda x: f'{int(x)}'),
            textposition='outside',
            yaxis='y2'
        ))

        fig_combined.update_layout(
            height=400,
            barmode='group',
            yaxis=dict(title='Cost ($)', side='left', showgrid=False),
            yaxis2=dict(title='FTD', side='right', overlaying='y', showgrid=False),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
            margin=dict(l=20, r=20, t=60, b=20)
        )
        st.plotly_chart(fig_combined, use_container_width=True)

        # Cost Efficiency Chart
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Cost per FTD by Agent")
            agent_sorted_cpr = agent_compare.sort_values('cost_per_ftd', ascending=True)

            colors = ['#2ecc71' if x < agent_compare['cost_per_ftd'].median() else '#e74c3c'
                      for x in agent_sorted_cpr['cost_per_ftd']]

            fig_cpr = go.Figure()
            fig_cpr.add_trace(go.Bar(
                x=agent_sorted_cpr['agent'],
                y=agent_sorted_cpr['cost_per_ftd'],
                marker_color=colors,
                text=agent_sorted_cpr['cost_per_ftd'].apply(lambda x: f'${x:,.2f}'),
                textposition='outside'
            ))
            fig_cpr.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title='Cost per FTD ($)'
            )
            st.plotly_chart(fig_cpr, use_container_width=True)

        with col2:
            st.subheader("Cost vs FTD Efficiency")
            fig_scatter = go.Figure()
            fig_scatter.add_trace(go.Scatter(
                x=agent_compare['cost'],
                y=agent_compare['ftd'],
                mode='markers+text',
                text=agent_compare['agent'],
                textposition='top center',
                marker=dict(
                    size=agent_compare['ftd'] * 2 + 10,
                    color=agent_compare['cost_per_ftd'],
                    colorscale='RdYlGn_r',
                    showscale=True,
                    colorbar=dict(title='Cost/FTD')
                )
            ))
            fig_scatter.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title='Total Cost ($)',
                yaxis_title='Total FTD'
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No agent data available for comparison")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Daily Cost Trend")
        df_chart = ptab_daily.copy()
        df_chart['date_only'] = pd.to_datetime(df_chart['date']).dt.date
        daily_cost = df_chart.groupby('date_only')['cost'].sum().reset_index()
        daily_cost = daily_cost.sort_values('date_only')

        fig = px.line(
            daily_cost,
            x='date_only',
            y='cost',
            markers=True,
            line_shape='spline'
        )
        fig.update_traces(line_color='#667eea', line_width=3)
        fig.update_layout(height=350, xaxis_tickformat='%Y-%m-%d')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Daily Registrations & FTD")
        daily_reg = df_chart.groupby('date_only').agg({
            'register': 'sum',
            'ftd': 'sum'
        }).reset_index()
        daily_reg = daily_reg.sort_values('date_only')

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_reg['date_only'],
            y=daily_reg['register'],
            name='Register',
            marker_color='#2ecc71'
        ))
        fig.add_trace(go.Bar(
            x=daily_reg['date_only'],
            y=daily_reg['ftd'],
            name='FTD',
            marker_color='#e74c3c'
        ))
        fig.update_layout(
            height=350,
            barmode='group',
            xaxis_tickformat='%Y-%m-%d'
        )
        st.plotly_chart(fig, use_container_width=True)

    # Detailed table
    st.subheader("Performance by Agent")

    if 'agent' in ptab_daily.columns:
        summary_df = ptab_daily.groupby('agent').agg({
            'cost': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'register': 'sum',
            'ftd': 'sum'
        }).reset_index()

        # Calculate derived metrics
        summary_df['CTR'] = (summary_df['clicks'] / summary_df['impressions'] * 100).round(2)
        summary_df['CPR'] = (summary_df['cost'] / summary_df['register']).round(2)
        summary_df['CPFTD'] = (summary_df['cost'] / summary_df['ftd']).round(2)
        summary_df['Conv'] = (summary_df['ftd'] / summary_df['register'] * 100).round(1)

        # Clean up
        summary_df = summary_df.fillna(0)
        summary_df = summary_df.replace([float('inf')], 0)

        # Sort by FTD descending
        summary_df = summary_df.sort_values('ftd', ascending=False)

        # Rename columns
        summary_df.columns = ['Agent', 'Cost', 'Impressions', 'Clicks', 'Register', 'FTD', 'CTR%', 'CPR', 'Cost/FTD', 'Conv %']

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Agent": st.column_config.TextColumn(width="medium"),
                "Cost": st.column_config.NumberColumn(format="$ %.2f"),
                "Impressions": st.column_config.NumberColumn(format="%d"),
                "Clicks": st.column_config.NumberColumn(format="%d"),
                "Register": st.column_config.NumberColumn(format="%d"),
                "FTD": st.column_config.NumberColumn(format="%d"),
                "CTR%": st.column_config.NumberColumn(format="%.2f%%"),
                "CPR": st.column_config.NumberColumn(format="$ %.2f"),
                "Cost/FTD": st.column_config.NumberColumn(format="$ %.2f"),
                "Conv %": st.column_config.NumberColumn(format="%.1f%%"),
            }
        )
    else:
        st.dataframe(ptab_daily, use_container_width=True, hide_index=True)


def render_creative_work(creative_df, selected_agent):
    """Render Creative Work (WITHOUT section) tab"""
    st.subheader(f"WITHOUT (Creative Work): {selected_agent if selected_agent != 'All Agents' else 'All Agents'}")

    if creative_df.empty:
        st.warning("No creative work data available.")
        return

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Creatives", f"{len(creative_df):,}")
    with col2:
        # Group by date first to avoid double-counting (creative_total is daily total)
        if 'creative_total' in creative_df.columns and 'date' in creative_df.columns:
            daily_totals = creative_df.groupby(creative_df['date'].dt.date)['creative_total'].first()
            creative_total_sum = daily_totals.sum()
        else:
            creative_total_sum = 0
        st.metric("Creative Total", f"{int(creative_total_sum):,}")
    with col3:
        unique = creative_df['creative_content'].nunique()
        st.metric("Unique Content", f"{unique:,}")
    with col4:
        freshness = (unique / len(creative_df) * 100) if len(creative_df) > 0 else 0
        st.metric("Freshness", f"{freshness:.1f}%")
    with col5:
        types = creative_df['creative_type'].nunique()
        st.metric("Types Used", f"{types:,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Creative Type Distribution")
        type_counts = creative_df['creative_type'].value_counts()
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Daily Creative Output")
        daily_creative = creative_df.copy()
        daily_creative['date_only'] = daily_creative['date'].dt.date
        # Take first value per date to avoid double-counting
        daily_agg = daily_creative.groupby('date_only')['creative_total'].first().reset_index()
        daily_agg.columns = ['date', 'total']
        fig = px.bar(
            daily_agg,
            x='date',
            y='total',
            color='total',
            color_continuous_scale='Purples'
        )
        fig.update_layout(height=350, xaxis_tickformat='%Y-%m-%d')
        fig.update_xaxes(type='category')  # Prevent duplicate dates
        st.plotly_chart(fig, use_container_width=True)

    # Creative content table
    st.subheader("Creative Content Details")
    cols_to_show = ['date', 'agent_name', 'creative_type', 'creative_total', 'creative_content', 'caption']
    cols_available = [c for c in cols_to_show if c in creative_df.columns]
    display_df = creative_df[cols_available].copy()
    display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    display_df['creative_content'] = display_df['creative_content'].str[:60] + '...'
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_sms(sms_df, selected_agent):
    """Render SMS tab"""
    st.subheader(f"SMS: {selected_agent if selected_agent != 'All Agents' else 'All Agents'}")

    if sms_df.empty:
        st.warning("No SMS data available.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    # Group by date first to avoid double-counting (sms_total is daily total)
    if 'date' in sms_df.columns:
        daily_sms_totals = sms_df.groupby(sms_df['date'].dt.date)['sms_total'].first()
        total_sms = daily_sms_totals.sum()
        # For type stats, group by type and date first, take first per date, then sum per type
        type_date_totals = sms_df.groupby(['sms_type', sms_df['date'].dt.date])['sms_total'].first().reset_index()
        type_totals = type_date_totals.groupby('sms_type')['sms_total'].sum()
        avg_per_type = type_totals.mean() if len(type_totals) > 0 else 0
        max_total = type_totals.max() if len(type_totals) > 0 else 0
    else:
        total_sms = sms_df['sms_total'].sum()
        avg_per_type = sms_df.groupby('sms_type')['sms_total'].sum().mean()
        max_total = sms_df.groupby('sms_type')['sms_total'].sum().max()

    with col1:
        st.metric("Total SMS Sent", f"{int(total_sms):,}")
    with col2:
        unique_types = sms_df['sms_type'].nunique()
        st.metric("SMS Types Used", f"{unique_types:,}")
    with col3:
        st.metric("Avg per Type", f"{avg_per_type:.1f}")
    with col4:
        st.metric("Max Type Total", f"{int(max_total):,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("SMS Type Distribution")
        # Group by type and date first, take first per date, then sum per type
        if 'date' in sms_df.columns:
            type_date_df = sms_df.groupby(['sms_type', sms_df['date'].dt.date])['sms_total'].first().reset_index()
            sms_by_type = type_date_df.groupby('sms_type')['sms_total'].sum().reset_index()
        else:
            sms_by_type = sms_df.groupby('sms_type')['sms_total'].sum().reset_index()
        sms_by_type = sms_by_type.sort_values('sms_total', ascending=True)

        fig = px.bar(
            sms_by_type,
            x='sms_total',
            y='sms_type',
            orientation='h',
            color='sms_total',
            color_continuous_scale='Oranges'
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Daily SMS Output")
        daily_sms = sms_df.copy()
        daily_sms['date_only'] = daily_sms['date'].dt.date
        # Take first per date to avoid double-counting (sms_total is daily total)
        daily_agg = daily_sms.groupby('date_only')['sms_total'].first().reset_index()
        fig = px.line(
            daily_agg,
            x='date_only',
            y='sms_total',
            markers=True,
            line_shape='spline'
        )
        fig.update_traces(line_color='#ff7f0e', line_width=3)
        fig.update_layout(height=400, xaxis_tickformat='%Y-%m-%d')
        fig.update_xaxes(type='category')  # Prevent duplicate dates
        st.plotly_chart(fig, use_container_width=True)

    # SMS detail table
    st.subheader("SMS Details by Agent")
    # Group by agent, type and date first, take first per date, then sum per agent/type
    if 'date' in sms_df.columns:
        agent_type_date = sms_df.groupby(['agent_name', 'sms_type', sms_df['date'].dt.date])['sms_total'].first().reset_index()
        sms_pivot = agent_type_date.pivot_table(
            index='sms_type',
            columns='agent_name',
            values='sms_total',
            aggfunc='sum',
            fill_value=0
        ).reset_index()
    else:
        sms_pivot = sms_df.pivot_table(
            index='sms_type',
            columns='agent_name',
            values='sms_total',
            aggfunc='sum',
            fill_value=0
        ).reset_index()
    st.dataframe(sms_pivot, use_container_width=True, hide_index=True)


def render_content_analysis(content_df, selected_agent):
    """Render Content Analysis tab"""
    st.subheader(f"Content Analysis: {selected_agent if selected_agent != 'All Agents' else 'All Agents'}")

    if content_df.empty:
        st.warning("No content data available.")
        return

    # Summary metrics - only count Primary Text
    col1, col2, col3, col4 = st.columns(4)

    # Filter for Primary Text only for metrics
    if 'content_type' in content_df.columns:
        primary_df = content_df[content_df['content_type'] == 'Primary Text']
    else:
        primary_df = content_df

    unique_content = primary_df['primary_content'].nunique() if not primary_df.empty else 0
    total_content = len(primary_df)

    with col1:
        st.metric("Total Primary Text", f"{total_content:,}")
    with col2:
        st.metric("Unique Content", f"{unique_content:,}")
    with col3:
        freshness = (unique_content / total_content * 100) if total_content > 0 else 0
        st.metric("Freshness", f"{freshness:.1f}%")
    with col4:
        recycled = total_content - unique_content
        st.metric("Recycled", f"{recycled:,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Content Type Distribution")
        type_counts = content_df['content_type'].value_counts()
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            hole=0.4,
            color_discrete_sequence=['#667eea', '#764ba2']
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Daily Primary Text Posts")
        # Use primary_df for daily chart (Primary Text only)
        if not primary_df.empty:
            daily_content = primary_df.copy()
            daily_content['date_only'] = daily_content['date'].dt.date
            daily_agg = daily_content.groupby('date_only').size().reset_index(name='posts')
            fig = px.bar(
                daily_agg,
                x='date_only',
                y='posts',
                color='posts',
                color_continuous_scale='Blues'
            )
            fig.update_layout(height=300, xaxis_tickformat='%Y-%m-%d')
            fig.update_xaxes(type='category')  # Prevent duplicate dates
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No Primary Text data available")

    # Similarity Analysis
    st.divider()
    st.subheader("Content Similarity Analysis (Primary Text)")

    # Use primary_df for similarity analysis
    unique_contents = primary_df['primary_content'].unique().tolist() if not primary_df.empty else []

    col1, col2 = st.columns([1, 2])

    with col1:
        selected_content = st.selectbox(
            "Select content to analyze:",
            unique_contents[:20],
            format_func=lambda x: x[:50] + '...' if len(x) > 50 else x
        )
        threshold = st.slider("Similarity Threshold", 0.0, 1.0, 0.7, 0.05)

    with col2:
        if selected_content:
            from difflib import SequenceMatcher

            similar_items = []
            for content in unique_contents:
                if content != selected_content:
                    ratio = SequenceMatcher(None, selected_content.lower(), content.lower()).ratio()
                    if ratio >= threshold:
                        similar_items.append({'content': content, 'similarity': ratio})

            similar_items.sort(key=lambda x: x['similarity'], reverse=True)

            if similar_items:
                st.warning(f"Found {len(similar_items)} similar content items")
                for item in similar_items[:5]:
                    score = item['similarity']
                    color = '#e74c3c' if score >= 0.85 else '#f39c12' if score >= 0.7 else '#27ae60'
                    st.markdown(f"""
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin: 5px 0; border-left: 4px solid {color};">
                        <strong>Similarity: {score:.1%}</strong><br>
                        {item['content'][:80]}...
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("No similar content found. This content is unique!")

    # Content table
    st.subheader("Content Details")
    display_df = content_df[['date', 'agent_name', 'content_type', 'primary_content', 'status']].copy()
    display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    display_df['primary_content'] = display_df['primary_content'].str[:60] + '...'
    st.dataframe(display_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
