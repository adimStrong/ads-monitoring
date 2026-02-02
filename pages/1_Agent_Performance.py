"""
Agent Performance Page - Individual agent detailed view with all 3 sections
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
from config import AGENTS, SMS_TYPES
from data_loader import load_agent_performance_data, load_agent_content_data, get_date_range, load_facebook_ads_data

st.set_page_config(page_title="Agent Performance", page_icon="👤", layout="wide")

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

# Sidebar filters
st.sidebar.header("Filters")

# Agent selector
selected_agent = st.sidebar.selectbox(
    "Select Agent",
    [a['name'] for a in AGENTS],
    index=0
)

# Get agent config
agent_config = next((a for a in AGENTS if a['name'] == selected_agent), None)

# Data source toggle
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True, key="agent_perf_data_source")

# Load data FIRST to determine date range
running_ads_df = None
creative_df = None
sms_df = None
fb_ads_df = None

if use_real_data and agent_config:
    with st.spinner(f"Loading data for {selected_agent}..."):
        # Load legacy performance data (for creative and SMS)
        running_ads_df, creative_df, sms_df = get_agent_data(
            selected_agent,
            agent_config['sheet_performance']
        )

        # Load Facebook Ads data for this agent
        all_fb_ads = load_facebook_ads_data()
        if all_fb_ads is not None and not all_fb_ads.empty:
            fb_ads_df = all_fb_ads[all_fb_ads['person_name'] == selected_agent].copy()
            if not fb_ads_df.empty:
                st.sidebar.success(f"Loaded {len(fb_ads_df)} Facebook Ads records")

    if (running_ads_df is None or running_ads_df.empty) and (fb_ads_df is None or fb_ads_df.empty):
        st.warning(f"Could not load data for {selected_agent}. Using sample data.")
        use_real_data = False

# Date range - constrained to available data (prefer Facebook Ads data)
if fb_ads_df is not None and not fb_ads_df.empty:
    min_date, max_date = get_date_range(fb_ads_df)
elif running_ads_df is not None and not running_ads_df.empty:
    min_date, max_date = get_date_range(running_ads_df)
else:
    min_date, max_date = None, None

# Convert to date objects
if hasattr(min_date, 'date'):
    min_date = min_date.date()
if hasattr(max_date, 'date'):
    max_date = max_date.date()

has_data = min_date is not None and max_date is not None and (
    (fb_ads_df is not None and not fb_ads_df.empty) or
    (running_ads_df is not None and not running_ads_df.empty)
)

if has_data:
    col1, col2 = st.sidebar.columns(2)
    with col1:
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
    st.sidebar.caption(f"Data: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("To", datetime.now())

if not use_real_data or running_ads_df is None or running_ads_df.empty:
    # Fall back to sample data
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
else:
    st.sidebar.success(f"Loaded {len(running_ads_df)} records")

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

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "💰 Facebook Ads", "🎨 Creative Work", "📱 SMS"])

# ============================================================
# TAB 1: OVERVIEW
# ============================================================

with tab1:
    # Quick summary of all sections
    st.subheader("Quick Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); padding: 1.5rem; border-radius: 12px; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">FACEBOOK ADS</h4>
        </div>
        """, unsafe_allow_html=True)
        if fb_ads_df is not None and not fb_ads_df.empty:
            total_spend = fb_ads_df['spend'].sum()
            total_reg = int(fb_ads_df['register'].sum())
            total_ftd = int(fb_ads_df['result_ftd'].sum())
            st.metric("Total Spend", f"${total_spend:,.2f}")
            st.metric("Register", f"{total_reg:,}")
            st.metric("FTD", f"{total_ftd:,}")
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
        # Group by date first to avoid double-counting (sms_total is daily total)
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

    # Combined daily trend
    st.subheader("📈 Daily Activity Trend")

    # Aggregate daily data from Facebook Ads
    if fb_ads_df is not None and not fb_ads_df.empty:
        fb_ads_df['date_only'] = pd.to_datetime(fb_ads_df['date']).dt.date
        daily_spend = fb_ads_df.groupby('date_only')['spend'].sum().reset_index()
        daily_spend.columns = ['date', 'spend']
    else:
        daily_spend = pd.DataFrame({'date': [], 'spend': []})

    daily_creative = creative_df.groupby('date').size().reset_index(name='creative_count') if not creative_df.empty else pd.DataFrame({'date': [], 'creative_count': []})
    # Take first per date to avoid double-counting (sms_total is daily total)
    daily_sms = sms_df.groupby('date')['sms_total'].first().reset_index() if not sms_df.empty and 'sms_total' in sms_df.columns else pd.DataFrame({'date': [], 'sms_total': []})

    fig = go.Figure()

    if not daily_spend.empty:
        fig.add_trace(go.Scatter(
            x=daily_spend['date'],
            y=daily_spend['spend'],
            name='Ad Spend ($)',
            line=dict(color='#3498db', width=3),
            mode='lines+markers'
        ))

    fig.add_trace(go.Scatter(
        x=daily_creative['date'],
        y=daily_creative['creative_count'],
        name='Creatives',
        line=dict(color='#9b59b6', width=3),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=daily_sms['date'],
        y=daily_sms['sms_total'] / 50,  # Scale down for visibility
        name='SMS (÷50)',
        line=dict(color='#27ae60', width=3),
        mode='lines+markers'
    ))

    fig.update_layout(
        height=350,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 2: RUNNING ADS
# ============================================================

with tab2:
    st.subheader("📢 Facebook Ads Performance")

    if fb_ads_df is not None and not fb_ads_df.empty:
        # Key metrics from Facebook Ads
        total_spend = fb_ads_df['spend'].sum()
        total_impressions = int(fb_ads_df['impressions'].sum())
        total_clicks = int(fb_ads_df['clicks'].sum())
        total_register = int(fb_ads_df['register'].sum())
        total_ftd = int(fb_ads_df['result_ftd'].sum())
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
        avg_cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("💵 Spend", f"${total_spend:,.2f}")
        with col2:
            st.metric("👁️ Impressions", f"{total_impressions:,}")
        with col3:
            st.metric("👆 Clicks", f"{total_clicks:,}")
        with col4:
            st.metric("📊 CTR", f"{avg_ctr:.2f}%")
        with col5:
            st.metric("📝 Register", f"{total_register:,}")
        with col6:
            st.metric("💰 FTD", f"{total_ftd:,}")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📈 Performance Trend")
            fb_ads_df['date_only'] = pd.to_datetime(fb_ads_df['date']).dt.date
            daily_fb = fb_ads_df.groupby('date_only').agg({
                'spend': 'sum',
                'impressions': 'sum',
                'clicks': 'sum'
            }).reset_index()

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=daily_fb['date_only'],
                y=daily_fb['impressions'],
                name='Impressions',
                fill='tozeroy',
                line=dict(color='#3498db', width=2)
            ))

            fig.add_trace(go.Scatter(
                x=daily_fb['date_only'],
                y=daily_fb['clicks'],
                name='Clicks',
                fill='tozeroy',
                line=dict(color='#e74c3c', width=2),
                yaxis='y2'
            ))

            fig.update_layout(
                height=350,
                yaxis=dict(title='Impressions', side='left'),
                yaxis2=dict(title='Clicks', side='right', overlaying='y'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📊 Spend vs Register/FTD")
            daily_reg = fb_ads_df.groupby('date_only').agg({
                'spend': 'sum',
                'register': 'sum',
                'result_ftd': 'sum'
            }).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily_reg['date_only'], y=daily_reg['register'], name='Register', marker_color='#3498db'))
            fig.add_trace(go.Bar(x=daily_reg['date_only'], y=daily_reg['result_ftd'], name='FTD', marker_color='#27ae60'))
            fig.update_layout(height=350, barmode='group', margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # Cost metrics
        st.subheader("💰 Cost Metrics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("CPC", f"${avg_cpc:.2f}")
        with col2:
            st.metric("CPM", f"${avg_cpm:.2f}")
        with col3:
            cpr = (total_spend / total_register) if total_register > 0 else 0
            st.metric("Cost/Register", f"${cpr:.2f}")
        with col4:
            cpftd = (total_spend / total_ftd) if total_ftd > 0 else 0
            st.metric("Cost/FTD", f"${cpftd:.2f}")

        # Data table
        st.subheader("📋 Facebook Ads Data")
        # Select columns that exist in the dataframe
        display_cols = ['date', 'spend', 'impressions', 'clicks', 'register', 'result_ftd', 'ctr', 'cpc', 'cpm']
        available_cols = [col for col in display_cols if col in fb_ads_df.columns]
        display_fb = fb_ads_df[available_cols].copy()
        display_fb['date'] = pd.to_datetime(display_fb['date']).dt.strftime('%Y-%m-%d')
        st.dataframe(display_fb, use_container_width=True, hide_index=True)
    else:
        st.info(f"No Facebook Ads data available for {selected_agent}.")

# ============================================================
# TAB 3: CREATIVE WORK
# ============================================================

with tab3:
    st.subheader("🎨 WITHOUT (Creative Work)")

    # Key metrics
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

            fig = px.pie(
                type_counts,
                values='count',
                names='type',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No creative data available")

    with col2:
        st.subheader("📂 Content by Folder")
        if not creative_df.empty and 'creative_folder' in creative_df.columns:
            folder_counts = creative_df['creative_folder'].value_counts().reset_index()
            folder_counts.columns = ['folder', 'count']

            fig = px.bar(
                folder_counts,
                x='folder',
                y='count',
                color='count',
                color_continuous_scale='Purples'
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No creative data available")

    # Daily creative output
    st.subheader("📅 Daily Creative Output")
    if not creative_df.empty and 'creative_type' in creative_df.columns:
        daily_creative = creative_df.groupby(['date', 'creative_type']).size().reset_index(name='count')

        fig = px.bar(
            daily_creative,
            x='date',
            y='count',
            color='creative_type',
            barmode='stack'
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily creative data available")

    # Data table
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

    # Key metrics - group by date first to avoid double-counting (sms_total is daily total)
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
            # Group by type and date first, take first per date, then sum per type
            if 'date' in sms_df.columns:
                type_date_df = sms_df.groupby(['sms_type', sms_df['date'].dt.date if hasattr(sms_df['date'], 'dt') else sms_df['date']])['sms_total'].first().reset_index()
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
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, showlegend=False, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No SMS data available")

    with col2:
        st.subheader("📈 Daily SMS Volume")
        if not sms_df.empty and 'sms_total' in sms_df.columns:
            # Take first per date to avoid double-counting (sms_total is daily total)
            daily_sms = sms_df.groupby('date')['sms_total'].first().reset_index()

            fig = px.area(
                daily_sms,
                x='date',
                y='sms_total',
                color_discrete_sequence=['#27ae60']
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No SMS data available")

    # Top SMS types table
    st.subheader("🏆 Top SMS Types")
    if not sms_df.empty and 'sms_type' in sms_df.columns:
        # Group by type and date first, take first per date, then aggregate per type
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

    # Data table
    st.subheader("📋 SMS Data")
    if not sms_df.empty:
        display_sms = sms_df.copy()
        display_sms['date'] = display_sms['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_sms, use_container_width=True, hide_index=True)
    else:
        st.info("No SMS data available")

# ============================================================
# DOWNLOAD SECTION
# ============================================================

st.divider()
st.subheader("📥 Export Data")

col1, col2, col3 = st.columns(3)

with col1:
    csv_ads = running_ads_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Running Ads",
        data=csv_ads,
        file_name=f"{selected_agent}_running_ads_{start_date}_{end_date}.csv",
        mime="text/csv"
    )

with col2:
    csv_creative = creative_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Creative Work",
        data=csv_creative,
        file_name=f"{selected_agent}_creative_{start_date}_{end_date}.csv",
        mime="text/csv"
    )

with col3:
    csv_sms = sms_df.to_csv(index=False)
    st.download_button(
        label="📥 Download SMS Data",
        data=csv_sms,
        file_name=f"{selected_agent}_sms_{start_date}_{end_date}.csv",
        mime="text/csv"
    )
