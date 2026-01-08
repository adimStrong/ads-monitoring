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
from data_loader import load_all_data, get_date_range

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

    # Load data
    if use_real_data:
        st.sidebar.info("Loading from Google Sheets...")
        running_ads_df, creative_df, sms_df, content_df = load_all_data()

        if running_ads_df.empty and creative_df.empty and sms_df.empty:
            st.error("Could not load data from Google Sheets. Make sure the sheet is publicly accessible.")
            st.info("Google Sheets ID: 1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ")
            st.warning("Falling back to sample data...")
            running_ads_df, creative_df, sms_df, content_df = load_sample_data()
        else:
            st.sidebar.success(f"Loaded {len(running_ads_df)} ad records")
    else:
        running_ads_df, creative_df, sms_df, content_df = load_sample_data()

    # Date filter with auto-detection from data
    min_date, max_date = get_date_range(running_ads_df)
    st.sidebar.subheader("Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", max(min_date, datetime.now() - timedelta(days=30)))
    with col2:
        end_date = st.date_input("To", max_date)

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

    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview",
        "Running Ads",
        "Creative Work",
        "SMS",
        "Content Analysis"
    ])

    with tab1:
        render_overview(running_ads_df, creative_df, sms_df, content_df)

    with tab2:
        render_running_ads(running_ads_df, selected_agent)

    with tab3:
        render_creative_work(creative_df, selected_agent)

    with tab4:
        render_sms(sms_df, selected_agent)

    with tab5:
        render_content_analysis(content_df, selected_agent)


def render_overview(running_ads_df, creative_df, sms_df, content_df):
    """Render overview tab with all 3 sections"""
    st.subheader("Team Overview")

    # ============================================================
    # SECTION 1: WITH RUNNING ADS Summary
    # ============================================================
    st.markdown('<div class="section-header"><h3>WITH RUNNING ADS</h3></div>', unsafe_allow_html=True)

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
        st.metric("Active Ads", f"{running_ads_df['active_count'].sum():,}")

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
        st.metric("Total SMS Sent", f"{sms_df['sms_total'].sum():,}")
    with col2:
        unique_sms = sms_df['sms_type'].nunique()
        st.metric("SMS Types Used", f"{unique_sms:,}")
    with col3:
        avg_sms = sms_df['sms_total'].mean() if len(sms_df) > 0 else 0
        st.metric("Avg per Type", f"{avg_sms:.1f}")
    with col4:
        top_sms = sms_df.groupby('sms_type')['sms_total'].sum().idxmax() if len(sms_df) > 0 else "N/A"
        st.metric("Top SMS", top_sms[:20] + "..." if len(top_sms) > 20 else top_sms)

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Daily Performance Trend")
        daily_perf = running_ads_df.groupby('date').agg({
            'total_ad': 'sum',
            'impressions': 'sum',
            'clicks': 'sum'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_perf['date'],
            y=daily_perf['total_ad'],
            name='Total Ads',
            marker_color='#667eea'
        ))
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Agent Performance Comparison")
        agent_perf = running_ads_df.groupby('agent_name').agg({
            'total_ad': 'sum',
            'ctr_percent': 'mean',
        }).reset_index()

        fig = px.bar(
            agent_perf,
            x='agent_name',
            y='total_ad',
            color='ctr_percent',
            color_continuous_scale='Viridis',
            labels={'total_ad': 'Total Ads', 'agent_name': 'Agent', 'ctr_percent': 'CTR %'}
        )
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Agent summary table
    st.subheader("Agent Summary (All Sections)")

    # Build aggregation dict based on available columns
    agg_dict = {
        'total_ad': 'sum',
        'impressions': 'sum',
        'clicks': 'sum',
        'ctr_percent': 'mean',
        'active_count': 'sum'
    }
    if 'amount_spent' in running_ads_df.columns:
        agg_dict['amount_spent'] = 'sum'
    if 'cpr' in running_ads_df.columns:
        agg_dict['cpr'] = 'mean'

    agent_ads = running_ads_df.groupby('agent_name').agg(agg_dict).round(2)

    agent_creative = creative_df.groupby('agent_name').size().rename('creatives')
    agent_sms = sms_df.groupby('agent_name')['sms_total'].sum().rename('sms_total')
    agent_content = content_df.groupby('agent_name').size().rename('content_posts')

    summary = agent_ads.join(agent_creative).join(agent_sms).join(agent_content).reset_index()

    # Build column names based on available columns
    col_names = ['Agent', 'Total Ads', 'Impressions', 'Clicks', 'Avg CTR %', 'Active']
    if 'amount_spent' in running_ads_df.columns:
        col_names.append('Amount Spent')
    if 'cpr' in running_ads_df.columns:
        col_names.append('Avg CPR')
    col_names.extend(['Creatives', 'SMS Total', 'Content Posts'])

    summary.columns = col_names
    summary = summary.fillna(0)

    st.dataframe(summary, use_container_width=True, hide_index=True)


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
        daily_trend = running_ads_df.groupby('date').agg({
            'total_ad': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'ctr_percent': 'mean'
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily_trend['date'],
            y=daily_trend['impressions'],
            name='Impressions',
            fill='tozeroy',
            line=dict(color='#3498db', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=daily_trend['date'],
            y=daily_trend['clicks'],
            name='Clicks',
            fill='tozeroy',
            yaxis='y2',
            line=dict(color='#e74c3c', width=2)
        ))
        fig.update_layout(
            height=350,
            yaxis=dict(title='Impressions'),
            yaxis2=dict(title='Clicks', overlaying='y', side='right'),
        )
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
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Creatives", f"{len(creative_df):,}")
    with col2:
        unique = creative_df['creative_content'].nunique()
        st.metric("Unique Content", f"{unique:,}")
    with col3:
        freshness = (unique / len(creative_df) * 100) if len(creative_df) > 0 else 0
        st.metric("Freshness", f"{freshness:.1f}%")
    with col4:
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
        daily_creative = creative_df.groupby('date').size().reset_index(name='count')
        fig = px.bar(
            daily_creative,
            x='date',
            y='count',
            color='count',
            color_continuous_scale='Purples'
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Creative content table
    st.subheader("Creative Content Details")
    display_df = creative_df[['date', 'agent_name', 'creative_type', 'creative_content', 'caption']].copy()
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

    with col1:
        st.metric("Total SMS Sent", f"{sms_df['sms_total'].sum():,}")
    with col2:
        unique_types = sms_df['sms_type'].nunique()
        st.metric("SMS Types Used", f"{unique_types:,}")
    with col3:
        avg_per_type = sms_df.groupby('sms_type')['sms_total'].sum().mean()
        st.metric("Avg per Type", f"{avg_per_type:.1f}")
    with col4:
        max_total = sms_df.groupby('sms_type')['sms_total'].sum().max()
        st.metric("Max Type Total", f"{max_total:,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("SMS Type Distribution")
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
        daily_sms = sms_df.groupby('date')['sms_total'].sum().reset_index()
        fig = px.line(
            daily_sms,
            x='date',
            y='sms_total',
            markers=True,
            line_shape='spline'
        )
        fig.update_traces(line_color='#ff7f0e', line_width=3)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # SMS detail table
    st.subheader("SMS Details by Agent")
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

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    unique_content = content_df['primary_content'].nunique()
    total_content = len(content_df)

    with col1:
        st.metric("Total Posts", f"{total_content:,}")
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
        st.subheader("Daily Content Posts")
        daily_content = content_df.groupby('date').size().reset_index(name='posts')
        fig = px.bar(
            daily_content,
            x='date',
            y='posts',
            color='posts',
            color_continuous_scale='Blues'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # Similarity Analysis
    st.divider()
    st.subheader("Content Similarity Analysis")

    unique_contents = content_df['primary_content'].unique().tolist()

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
