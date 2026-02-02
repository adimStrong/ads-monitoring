"""
BINGO365 Daily Monitoring Dashboard
Main Streamlit Application
"""
import streamlit as st
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
from data_loader import load_all_data, get_date_range, load_facebook_ads_data

# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        st.markdown('<h1 class="main-header">BINGO365 Daily Monitoring</h1>', unsafe_allow_html=True)

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

    # Send Daily Report button
    if st.sidebar.button("📤 Send Daily Report", type="secondary"):
        try:
            from daily_report import generate_daily_report
            with st.spinner("Generating and sending report to Telegram..."):
                report = generate_daily_report(send_to_telegram=True)
                st.sidebar.success("✅ Report sent to Telegram!")
                with st.sidebar.expander("Preview Report"):
                    st.code(report, language=None)
        except ValueError as e:
            st.sidebar.error(f"⚠️ Telegram not configured: {e}")
        except Exception as e:
            st.sidebar.error(f"❌ Failed to send report: {e}")

    # Load data
    if use_real_data:
        st.sidebar.info("Loading from Google Sheets...")
        running_ads_df, creative_df, sms_df, content_df = load_all_data()

        # Load Facebook Ads data
        fb_ads_df = load_facebook_ads_data()
        if fb_ads_df is not None and not fb_ads_df.empty:
            st.sidebar.success(f"Loaded {len(fb_ads_df)} FB Ads records")
        else:
            fb_ads_df = pd.DataFrame()

        if running_ads_df.empty and creative_df.empty and sms_df.empty:
            st.error("Could not load data from Google Sheets. Make sure the sheet is publicly accessible.")
            st.info("Google Sheets ID: 1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ")
            st.warning("Falling back to sample data...")
            running_ads_df, creative_df, sms_df, content_df = load_sample_data()
        else:
            st.sidebar.success(f"Loaded {len(running_ads_df)} ad records")
    else:
        running_ads_df, creative_df, sms_df, content_df = load_sample_data()
        fb_ads_df = pd.DataFrame()

    # Date filter with auto-detection from data - only allow dates with data
    min_date, max_date = get_date_range(running_ads_df)

    # Convert to date objects if they're datetime
    if hasattr(min_date, 'date'):
        min_date = min_date.date()
    if hasattr(max_date, 'date'):
        max_date = max_date.date()

    st.sidebar.subheader("Date Range")

    # Check if we have valid data range
    has_data = min_date is not None and max_date is not None and min_date <= max_date

    if has_data:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            # Default to last 7 days of available data, or min_date if less data
            default_start = max(min_date, max_date - timedelta(days=7))
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
        st.sidebar.caption(f"Data available: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")
    else:
        st.sidebar.warning("No data available for date filtering")
        start_date = datetime.now().date() - timedelta(days=7)
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

    # Main content tabs (Running Ads removed - now uses Facebook Ads data)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Facebook Ads",
        "Creative Work",
        "SMS",
        "Content Analysis"
    ])

    with tab1:
        render_overview(running_ads_df, creative_df, sms_df, content_df, fb_ads_df)

    with tab2:
        render_facebook_ads(fb_ads_df)

    with tab3:
        render_creative_work(creative_df, selected_agent)

    with tab4:
        render_sms(sms_df, selected_agent)

    with tab5:
        render_content_analysis(content_df, selected_agent)


def render_overview(running_ads_df, creative_df, sms_df, content_df, fb_ads_df=None):
    """Render overview tab with all sections"""
    st.subheader("Team Overview")

    # ============================================================
    # SECTION 1: WITH RUNNING ADS Summary (from Facebook Ads by Agent)
    # ============================================================
    st.markdown('<div class="section-header"><h3>WITH RUNNING ADS</h3></div>', unsafe_allow_html=True)

    if fb_ads_df is not None and not fb_ads_df.empty and 'person_name' in fb_ads_df.columns:
        # Summary metrics from Facebook Ads
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        total_spend = fb_ads_df['spend'].sum()
        total_impressions = fb_ads_df['impressions'].sum()
        total_clicks = fb_ads_df['clicks'].sum()
        total_register = fb_ads_df['register'].sum()
        total_ftd = fb_ads_df['result_ftd'].sum()
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0

        with col1:
            st.metric("Total Spend", f"${total_spend:,.2f}")
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

        agent_summary = fb_ads_df.groupby('person_name').agg({
            'spend': 'sum',
            'register': 'sum',
            'result_ftd': 'sum',
        }).reset_index()

        # Calculate derived metrics
        agent_summary['CPR'] = (agent_summary['spend'] / agent_summary['register']).round(2)
        agent_summary['Cost/FTD'] = (agent_summary['spend'] / agent_summary['result_ftd']).round(2)

        # Handle inf/nan
        agent_summary = agent_summary.replace([float('inf'), float('-inf')], 0).fillna(0)

        # Sort by FTD descending
        agent_summary = agent_summary.sort_values('result_ftd', ascending=False)

        # Rename columns for display
        agent_summary = agent_summary.rename(columns={
            'person_name': 'Agent',
            'spend': 'Spend',
            'register': 'Register',
            'result_ftd': 'FTD'
        })

        # Reorder columns
        display_cols = ['Agent', 'Spend', 'Register', 'FTD', 'CPR', 'Cost/FTD']
        agent_summary = agent_summary[display_cols]

        # Format for display
        st.dataframe(
            agent_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Agent": st.column_config.TextColumn(width="medium"),
                "Spend": st.column_config.NumberColumn(format="$,.2f"),
                "Register": st.column_config.NumberColumn(format=",d"),
                "FTD": st.column_config.NumberColumn(format=",d"),
                "CPR": st.column_config.NumberColumn(format="$,.2f"),
                "Cost/FTD": st.column_config.NumberColumn(format="$,.2f"),
            }
        )
    else:
        # Fallback to old running_ads_df if no Facebook Ads data
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Total Ads", f"{running_ads_df['total_ad'].sum():,}")
        with col2:
            st.metric("Impressions", f"{running_ads_df['impressions'].sum():,}")
        with col3:
            st.metric("Clicks", f"{running_ads_df['clicks'].sum():,}")
        with col4:
            st.metric("Avg CTR", f"{running_ads_df['ctr_percent'].mean():.2f}%")
        with col5:
            st.metric("Avg CPC", f"${running_ads_df['cpc'].mean():.2f}")
        with col6:
            st.metric("Active Ads", f"{running_ads_df['active_count'].sum():,}")
        st.info("No Facebook Ads data available. Showing legacy data.")

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
        st.subheader("Daily Performance Trend")
        daily_perf = running_ads_df.copy()
        daily_perf['date_only'] = daily_perf['date'].dt.date
        daily_agg = daily_perf.groupby('date_only').agg({
            'total_ad': 'sum',
            'impressions': 'sum',
            'clicks': 'sum'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_agg['date_only'],
            y=daily_agg['total_ad'],
            name='Total Ads',
            marker_color='#667eea'
        ))
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20), xaxis_tickformat='%Y-%m-%d')
        fig.update_xaxes(type='category')  # Prevent duplicate dates
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Agent Performance Comparison")
        # Combine ads and creative data for agent comparison
        agent_perf = running_ads_df.groupby('agent_name').agg({
            'total_ad': 'sum',
            'ctr_percent': 'mean',
        }).reset_index()

        # Add creative total per agent (group by date first to avoid double-counting)
        if not creative_df.empty and 'creative_total' in creative_df.columns and 'date' in creative_df.columns:
            # First get daily totals per agent (take first value per date to avoid duplicates)
            daily_creative = creative_df.groupby(['agent_name', creative_df['date'].dt.date])['creative_total'].first().reset_index()
            # Then sum across dates per agent
            agent_creative = daily_creative.groupby('agent_name')['creative_total'].sum().reset_index()
            agent_creative.columns = ['agent_name', 'creative_total']
            agent_perf = agent_perf.merge(agent_creative, on='agent_name', how='left')
            agent_perf['creative_total'] = agent_perf['creative_total'].fillna(0)
        else:
            agent_perf['creative_total'] = 0

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agent_perf['agent_name'],
            y=agent_perf['total_ad'],
            name='Total Ads',
            marker_color='#667eea'
        ))
        fig.add_trace(go.Bar(
            x=agent_perf['agent_name'],
            y=agent_perf['creative_total'],
            name='Creative Total',
            marker_color='#764ba2'
        ))
        fig.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
            barmode='group',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    # Agent summary table
    st.subheader("Agent Summary (All Sections)")

    # Use Facebook Ads data for ads metrics (if available)
    if fb_ads_df is not None and not fb_ads_df.empty and 'person_name' in fb_ads_df.columns:
        # Aggregate Facebook Ads by person (agent)
        agent_ads = fb_ads_df.groupby('person_name').agg({
            'spend': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'register': 'sum',
            'result_ftd': 'sum'
        }).round(2)
        agent_ads['ctr'] = (agent_ads['clicks'] / agent_ads['impressions'] * 100).round(2)
        agent_ads['cpc'] = (agent_ads['spend'] / agent_ads['clicks']).round(2)
        agent_ads = agent_ads.replace([float('inf'), float('-inf')], 0).fillna(0)
        agent_ads.index.name = 'agent_name'
    else:
        # Fallback to empty DataFrame
        agent_ads = pd.DataFrame(columns=['spend', 'impressions', 'clicks', 'register', 'result_ftd', 'ctr', 'cpc'])
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
    summary.columns = ['Agent', 'Spend', 'Impressions', 'Clicks', 'Register', 'FTD', 'CTR %', 'CPC', 'Creatives', 'SMS Total', 'Content Posts']
    summary = summary.fillna(0)

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Spend": st.column_config.NumberColumn(format="$,.2f"),
            "Impressions": st.column_config.NumberColumn(format=",d"),
            "Clicks": st.column_config.NumberColumn(format=",d"),
            "Register": st.column_config.NumberColumn(format=",d"),
            "FTD": st.column_config.NumberColumn(format=",d"),
            "CTR %": st.column_config.NumberColumn(format="%.2f%%"),
            "CPC": st.column_config.NumberColumn(format="$,.2f"),
            "Creatives": st.column_config.NumberColumn(format=",d"),
            "SMS Total": st.column_config.NumberColumn(format=",d"),
            "Content Posts": st.column_config.NumberColumn(format=",d"),
        }
    )


def render_facebook_ads(fb_ads_df):
    """Render Facebook Ads tab"""
    st.subheader("💰 Facebook Ads Performance")

    if fb_ads_df is None or fb_ads_df.empty:
        st.warning("No Facebook Ads data available. Make sure the credentials.json is configured.")
        return

    # Summary metrics
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

    total_spend = fb_ads_df['spend'].sum()
    total_impressions = fb_ads_df['impressions'].sum()
    total_clicks = fb_ads_df['clicks'].sum()
    total_reach = fb_ads_df['reach'].sum()
    total_register = fb_ads_df['register'].sum()
    total_ftd = fb_ads_df['result_ftd'].sum()
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0

    with col1:
        st.metric("Total Spend", f"${total_spend:,.2f}")
    with col2:
        st.metric("Impressions", f"{total_impressions:,}")
    with col3:
        st.metric("Clicks", f"{total_clicks:,}")
    with col4:
        st.metric("Reach", f"{total_reach:,}")
    with col5:
        st.metric("CTR", f"{avg_ctr:.2f}%")
    with col6:
        st.metric("CPC", f"${avg_cpc:.2f}")
    with col7:
        st.metric("Register", f"{int(total_register):,}")
    with col8:
        st.metric("FTD", f"{int(total_ftd):,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Performance by Person")
        if 'person_name' in fb_ads_df.columns:
            person_data = fb_ads_df.groupby('person_name').agg({
                'spend': 'sum',
                'impressions': 'sum',
                'clicks': 'sum',
                'register': 'sum',
                'result_ftd': 'sum'
            }).reset_index()
            person_data = person_data[person_data['person_name'] != '']
            person_data = person_data.sort_values('spend', ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=person_data['person_name'],
                y=person_data['spend'],
                name='Spend',
                marker_color='#667eea'
            ))
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No person names available")

    with col2:
        st.subheader("FTD by Person")
        if 'person_name' in fb_ads_df.columns:
            person_ftd = fb_ads_df.groupby('person_name').agg({
                'result_ftd': 'sum'
            }).reset_index()
            person_ftd = person_ftd[person_ftd['person_name'] != '']
            person_ftd = person_ftd.sort_values('result_ftd', ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=person_ftd['person_name'],
                y=person_ftd['result_ftd'],
                name='FTD',
                marker_color='#764ba2'
            ))
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No person data available")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Daily Spend Trend")
        fb_ads_df['date_only'] = pd.to_datetime(fb_ads_df['date']).dt.date
        daily_spend = fb_ads_df.groupby('date_only')['spend'].sum().reset_index()
        daily_spend = daily_spend.sort_values('date_only')

        fig = px.line(
            daily_spend,
            x='date_only',
            y='spend',
            markers=True,
            line_shape='spline'
        )
        fig.update_traces(line_color='#667eea', line_width=3)
        fig.update_layout(height=350, xaxis_tickformat='%Y-%m-%d')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Daily Registrations & FTD")
        daily_reg = fb_ads_df.groupby('date_only').agg({
            'register': 'sum',
            'result_ftd': 'sum'
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
            y=daily_reg['result_ftd'],
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
    st.subheader("Performance by Person")

    if 'person_name' in fb_ads_df.columns:
        summary_df = fb_ads_df.groupby('person_name').agg({
            'spend': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'reach': 'sum',
            'register': 'sum',
            'result_ftd': 'sum'
        }).reset_index()

        # Calculate derived metrics
        summary_df['CTR'] = (summary_df['clicks'] / summary_df['impressions'] * 100).round(2)
        summary_df['CPR'] = (summary_df['spend'] / summary_df['register']).round(2)
        summary_df['CPFTD'] = (summary_df['spend'] / summary_df['result_ftd']).round(2)

        # Clean up
        summary_df = summary_df.fillna(0)
        summary_df = summary_df.replace([float('inf')], 0)

        # Sort by FTD descending
        summary_df = summary_df.sort_values('result_ftd', ascending=False)

        # Rename columns
        summary_df.columns = ['Person', 'Spend', 'Impressions', 'Clicks', 'Reach', 'Register', 'FTD', 'CTR%', 'CPR', 'Cost/FTD']

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Person": st.column_config.TextColumn(width="medium"),
                "Spend": st.column_config.NumberColumn(format="$,.2f"),
                "Impressions": st.column_config.NumberColumn(format=",d"),
                "Clicks": st.column_config.NumberColumn(format=",d"),
                "Reach": st.column_config.NumberColumn(format=",d"),
                "Register": st.column_config.NumberColumn(format=",d"),
                "FTD": st.column_config.NumberColumn(format=",d"),
                "CTR%": st.column_config.NumberColumn(format="%.2f%%"),
                "CPR": st.column_config.NumberColumn(format="$,.2f"),
                "Cost/FTD": st.column_config.NumberColumn(format="$,.2f"),
            }
        )
    else:
        st.dataframe(fb_ads_df, use_container_width=True, hide_index=True)


def render_running_ads(running_ads_df, selected_agent):
    """Render Running Ads tab"""
    st.subheader(f"WITH RUNNING ADS: {selected_agent if selected_agent != 'All Agents' else 'All Agents'}")

    # Summary metrics - Row 1
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

    with col1:
        st.metric("Total Ads", f"{running_ads_df['total_ad'].sum():,}")
    with col2:
        st.metric("Impressions", f"{running_ads_df['impressions'].sum():,}")
    with col3:
        st.metric("Clicks", f"{running_ads_df['clicks'].sum():,}")
    with col4:
        st.metric("Avg CTR", f"{running_ads_df['ctr_percent'].mean():.2f}%")
    with col5:
        st.metric("Avg CPC", f"${running_ads_df['cpc'].mean():.2f}")
    with col6:
        amount_spent = running_ads_df['amount_spent'].sum() if 'amount_spent' in running_ads_df.columns else 0
        st.metric("Amount Spent", f"${amount_spent:,.2f}")
    with col7:
        avg_cpr = running_ads_df['cpr'].mean() if 'cpr' in running_ads_df.columns else 0
        st.metric("Avg CPR", f"${avg_cpr:.2f}")
    with col8:
        st.metric("Active", f"{running_ads_df['active_count'].sum():,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Performance Trend")
        daily_trend = running_ads_df.copy()
        daily_trend['date_only'] = daily_trend['date'].dt.date
        daily_agg = daily_trend.groupby('date_only').agg({
            'total_ad': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'ctr_percent': 'mean'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily_agg['date_only'],
            y=daily_agg['impressions'],
            name='Impressions',
            fill='tozeroy',
            line=dict(color='#3498db', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=daily_agg['date_only'],
            y=daily_agg['clicks'],
            name='Clicks',
            fill='tozeroy',
            yaxis='y2',
            line=dict(color='#e74c3c', width=2)
        ))
        fig.update_layout(
            height=350,
            yaxis=dict(title='Impressions'),
            yaxis2=dict(title='Clicks', overlaying='y', side='right'),
            xaxis_tickformat='%Y-%m-%d'
        )
        fig.update_xaxes(type='category')  # Prevent duplicate dates
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Ad Status Distribution")
        status_data = running_ads_df[['active_count', 'rejected_count', 'deleted_count']].sum()
        fig = px.pie(
            values=status_data.values,
            names=['Active', 'Rejected', 'Deleted'],
            hole=0.4,
            color_discrete_sequence=['#2ecc71', '#e74c3c', '#95a5a6']
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.subheader("Detailed Data")
    # Build column list dynamically based on available columns
    base_cols = ['date', 'agent_name', 'total_ad', 'campaign', 'impressions', 'clicks', 'ctr_percent', 'cpc', 'conversion_rate']
    if 'amount_spent' in running_ads_df.columns:
        base_cols.append('amount_spent')
    if 'cpr' in running_ads_df.columns:
        base_cols.append('cpr')
    base_cols.extend(['active_count', 'rejected_count'])

    display_df = running_ads_df[[col for col in base_cols if col in running_ads_df.columns]].copy()
    display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    st.dataframe(display_df, use_container_width=True, hide_index=True)


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
