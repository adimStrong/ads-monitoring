"""
Content Analysis Page - Content similarity and pattern detection
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AGENTS
from data_loader import load_agent_content_data, get_date_range

st.set_page_config(page_title="Content Analysis", page_icon="📝", layout="wide")

# Sidebar logo
logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.jpg")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)

st.title("📝 Content Analysis & Similarity Detection")

# ============================================================
# DATA LOADING - Load real content from Google Sheets
# ============================================================

@st.cache_data(ttl=300)
def load_all_content_data(agents):
    """Load content data from all agent content sheets"""
    all_content = []

    for agent in agents:
        content_df = load_agent_content_data(
            agent['name'],
            agent['sheet_content']
        )

        if content_df is not None and not content_df.empty:
            all_content.append(content_df)

    if all_content:
        combined = pd.concat(all_content, ignore_index=True)
        # Add content hash for comparison
        if 'primary_content' in combined.columns:
            combined['content_hash'] = combined['primary_content'].apply(
                lambda x: hashlib.md5(str(x).encode()).hexdigest()[:12] if pd.notna(x) else ''
            )
        return combined
    return pd.DataFrame()

# Sidebar filters
st.sidebar.header("Filters")

selected_agent = st.sidebar.selectbox(
    "Select Agent",
    ['All Agents'] + [a['name'] for a in AGENTS]
)

# Data source toggle
use_real_data = st.sidebar.checkbox("Use Google Sheets Data", value=True)

# Load data FIRST to determine date range
df = pd.DataFrame()

if use_real_data:
    with st.spinner("Loading content data from Google Sheets..."):
        df = load_all_content_data(AGENTS)

    if df.empty:
        st.warning("Could not load content data from Google Sheets. Using sample data.")
        use_real_data = False

# Date range - constrained to available data
min_date, max_date = get_date_range(df)

# Convert to date objects
if hasattr(min_date, 'date'):
    min_date = min_date.date()
if hasattr(max_date, 'date'):
    max_date = max_date.date()

has_data = min_date is not None and max_date is not None and not df.empty

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

if not use_real_data or df.empty:
    # Fall back to sample data
    import random

    content_templates = [
        "Sayang ang 8,888 Sign Up Bonus kung palalampasin mo pa! Register na!",
        "Smart choice 'to—join today!",
        "Wag papalampasin ang swerte! Lalo na kung may libreng pamuhunan! Kunin ang 36.5 signup bonus!",
        "Walang tal0 dito! Register na!",
        "Malambot at may libreng 277 Bonus at 8,888 Dp0sit Bonus!",
        "Claim your Bonus now!",
        "Ano pang hinihintay mo? Download na para makuha ang 277 + 8,888 dp0sit bonus!",
        "Download the app now!",
        "No more SANA ALL na sa panalo ng iba! Dahil ikaw na ang next! Register na at kuhain ang Libreng 277!",
        "BENTE MO, GAWIN NATING LIBO!",
    ]

    headline_templates = [
        "36.5 SIGN UP", "20 MINIMUM DEPOSIT", "277% DEPOSIT BONUS",
        "8,888 Daily Bonus", "FREE SIGNUP BONUS", "LIBRENG 277", "CASHBACK 8%",
    ]

    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    data = []

    for agent in AGENTS:
        random.seed(hash(agent['name']))
        for date in dates:
            num_posts = random.randint(3, 8)
            for i in range(num_posts):
                content_type = random.choice(['Primary Text', 'Headline'])
                content = random.choice(content_templates if content_type == 'Primary Text' else headline_templates)

                data.append({
                    'date': date,
                    'agent_name': agent['name'],
                    'content_type': content_type,
                    'primary_content': content,
                    'status': random.choice(['Active', 'Pending', 'Approved']),
                    'content_hash': hashlib.md5(content.encode()).hexdigest()[:12]
                })

    df = pd.DataFrame(data)
else:
    st.sidebar.success(f"Loaded {len(df)} content records")

# Filter by agent
if selected_agent != 'All Agents':
    df = df[df['agent_name'] == selected_agent]

# Header
st.markdown(f"""
<div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 1.5rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
    <h2 style="margin: 0;">Content Analysis: {selected_agent}</h2>
    <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')} • {len(df)} total posts</p>
</div>
""", unsafe_allow_html=True)

# Key Metrics
col1, col2, col3, col4, col5 = st.columns(5)

total_posts = len(df)
unique_posts = df['primary_content'].nunique() if not df.empty and 'primary_content' in df.columns else 0
recycled = total_posts - unique_posts
freshness = (unique_posts / total_posts * 100) if total_posts > 0 else 0

with col1:
    st.metric("📝 Total Posts", f"{total_posts:,}")
with col2:
    st.metric("✨ Unique Content", f"{unique_posts:,}")
with col3:
    st.metric("♻️ Recycled", f"{recycled:,}")
with col4:
    delta_color = "normal" if freshness >= 70 else "inverse"
    st.metric("🌟 Freshness", f"{freshness:.1f}%")
with col5:
    if not df.empty and 'content_type' in df.columns:
        primary_count = len(df[df['content_type'] == 'Primary Text'])
        headline_count = len(df[df['content_type'] == 'Headline'])
    else:
        primary_count = 0
        headline_count = 0
    st.metric("📊 Primary/Headline", f"{primary_count}/{headline_count}")

st.divider()

# Tabs for different views
tab1, tab2, tab3 = st.tabs(["📅 Daily vs Monthly", "🔍 Similarity Analysis", "📊 Theme Detection"])

with tab1:
    st.subheader("📅 Daily vs Monthly Content Comparison")

    if df.empty or 'date' not in df.columns or 'primary_content' not in df.columns:
        st.info("No content data available for analysis. Check if content sheets have data.")
    else:
        # Select specific date for comparison
        available_dates = sorted(df['date'].unique(), reverse=True)
        if not available_dates:
            st.warning("No dates available in the data")
        else:
            selected_date = st.selectbox(
                "Select Date to Analyze",
                available_dates[:14],  # Last 14 days
                format_func=lambda x: x.strftime('%Y-%m-%d (%A)') if hasattr(x, 'strftime') else str(x)
            )

            # Get today's content and month's content
            today_df = df[df['date'] == selected_date]
            month_df = df[df['date'] < selected_date]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### 📅 Selected Day Content")
                date_str = selected_date.strftime('%Y-%m-%d') if hasattr(selected_date, 'strftime') else str(selected_date)
                st.info(f"**{date_str}** - {len(today_df)} posts")

                if today_df.empty:
                    st.warning("No content for this date")
                else:
                    for _, row in today_df.iterrows():
                        # Check if this content exists in previous days
                        content = str(row.get('primary_content', ''))
                        is_recycled = content in month_df['primary_content'].values if not month_df.empty else False
                        status_icon = "🔴" if is_recycled else "🟢"
                        status_text = "Recycled" if is_recycled else "New"
                        content_type = row.get('content_type', 'Unknown')
                        agent_name = row.get('agent_name', 'Unknown')

                        st.markdown(f"""
                        <div style="background: {'#fff3cd' if is_recycled else '#d4edda'}; padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid {'#ffc107' if is_recycled else '#28a745'};">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span><strong>{status_icon} {status_text}</strong> | {content_type}</span>
                                <span style="font-size: 0.8em; color: #666;">{agent_name}</span>
                            </div>
                            <p style="margin: 8px 0 0 0; font-size: 0.95em;">{content[:120]}{'...' if len(content) > 120 else ''}</p>
                        </div>
                        """, unsafe_allow_html=True)

            with col2:
                st.markdown("### 📊 Day vs Month Stats")

                # Calculate stats
                today_unique = today_df['primary_content'].nunique() if not today_df.empty else 0
                today_total = len(today_df)
                today_recycled = today_total - today_unique

                month_unique = month_df['primary_content'].nunique() if not month_df.empty else 0
                month_total = len(month_df)

                # Metrics
                mcol1, mcol2 = st.columns(2)
                with mcol1:
                    st.metric("Today's Posts", today_total)
                    st.metric("New Content", today_unique)
                with mcol2:
                    st.metric("Month Total", month_total)
                    st.metric("Recycled Today", today_recycled)

                # Freshness gauge
                today_freshness = (today_unique / today_total * 100) if today_total > 0 else 0

                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=today_freshness,
                    title={'text': "Today's Freshness Score"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#28a745" if today_freshness >= 70 else "#ffc107" if today_freshness >= 50 else "#dc3545"},
                        'steps': [
                            {'range': [0, 50], 'color': '#ffebee'},
                            {'range': [50, 70], 'color': '#fff8e1'},
                            {'range': [70, 100], 'color': '#e8f5e9'}
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': 70
                        }
                    }
                ))
                fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)

            # Daily freshness trend
            st.subheader("📈 Daily Freshness Trend")
            daily_stats = []
            for date in available_dates[:14]:
                day_df = df[df['date'] == date]
                prev_df = df[df['date'] < date]
                unique = len([c for c in day_df['primary_content'].unique() if c not in prev_df['primary_content'].values]) if not day_df.empty else 0
                total = len(day_df)
                daily_stats.append({
                    'date': date,
                    'total': total,
                    'new': unique,
                    'recycled': total - unique,
                    'freshness': (unique / total * 100) if total > 0 else 0
                })

            trend_df = pd.DataFrame(daily_stats)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=trend_df['date'], y=trend_df['new'], name='New Content', marker_color='#28a745'))
            fig.add_trace(go.Bar(x=trend_df['date'], y=trend_df['recycled'], name='Recycled', marker_color='#ffc107'))
            fig.add_trace(go.Scatter(x=trend_df['date'], y=trend_df['freshness'], name='Freshness %', yaxis='y2', line=dict(color='#007bff', width=3)))

            fig.update_layout(
                barmode='stack',
                height=350,
                yaxis=dict(title='Content Count'),
                yaxis2=dict(title='Freshness %', overlaying='y', side='right', range=[0, 100]),
                legend=dict(orientation='h', yanchor='bottom', y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("🔍 Content Similarity Analysis")

    if df.empty or 'primary_content' not in df.columns:
        st.info("No content data available for similarity analysis")
    else:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("### Select Content")
            unique_contents = df['primary_content'].dropna().unique().tolist()

            if not unique_contents:
                st.warning("No content available")
            else:
                selected_content = st.selectbox(
                    "Choose content to analyze:",
                    unique_contents[:30],
                    format_func=lambda x: str(x)[:50] + '...' if len(str(x)) > 50 else str(x)
                )

                threshold = st.slider("Similarity Threshold", 0.3, 1.0, 0.6, 0.05)

                st.markdown("### Selected Content")
                st.info(selected_content)

        with col2:
            st.markdown("### Similar Content Found")

            if unique_contents:
                # Simple word-based similarity
                from difflib import SequenceMatcher

                similar_items = []
                for content in unique_contents:
                    if content != selected_content:
                        ratio = SequenceMatcher(None, str(selected_content).lower(), str(content).lower()).ratio()
                        if ratio >= threshold:
                            # Find when this content was used
                            uses = df[df['primary_content'] == content]
                            agents_list = uses['agent_name'].unique().tolist() if 'agent_name' in uses.columns else []
                            similar_items.append({
                                'content': content,
                                'similarity': ratio,
                                'times_used': len(uses),
                                'agents': agents_list,
                                'last_used': uses['date'].max() if 'date' in uses.columns else None
                            })

                similar_items.sort(key=lambda x: x['similarity'], reverse=True)

                if similar_items:
                    for item in similar_items[:10]:
                        score = item['similarity']
                        if score >= 0.85:
                            color = '#dc3545'
                            badge = '🔴 Duplicate'
                        elif score >= 0.7:
                            color = '#ffc107'
                            badge = '🟡 Very Similar'
                        else:
                            color = '#28a745'
                            badge = '🟢 Similar'

                        agents_str = ', '.join(item['agents'][:2]) if item['agents'] else 'Unknown'
                        content_preview = str(item['content'])[:100]

                        st.markdown(f"""
                        <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid {color};">
                            <div style="display: flex; justify-content: space-between;">
                                <span><strong>{badge}</strong> - {score:.1%} match</span>
                                <span style="font-size: 0.8em;">Used {item['times_used']}x by {agents_str}</span>
                            </div>
                            <p style="margin: 8px 0 0 0;">{content_preview}...</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("✅ No similar content found! This content is unique.")

with tab3:
    st.subheader("📊 Content Theme Detection")

    if df.empty or 'primary_content' not in df.columns:
        st.info("No content data available for theme detection")
    else:
        # Define themes and keywords
        themes = {
            'Sign Up Bonus': ['sign up', 'signup', 'register', 'libreng'],
            'Deposit Bonus': ['deposit', 'dp0sit', 'puhunan', 'minimum'],
            'Cashback': ['cashback', 'cash back', 'balik'],
            'Download/App': ['download', 'app', 'link'],
            'Jackpot/Winning': ['panalo', 'win', 'jackpot', 'swerte', 'libo'],
            'Promo/Bonus Amount': ['277', '8,888', '36.5', 'bonus'],
        }

        # Detect themes in content
        theme_counts = {theme: 0 for theme in themes}
        content_themes = []

        for content in df['primary_content'].dropna():
            content_lower = str(content).lower()
            detected = []
            for theme, keywords in themes.items():
                if any(kw in content_lower for kw in keywords):
                    theme_counts[theme] += 1
                    detected.append(theme)
            content_themes.append(detected)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Theme Distribution")
            fig = px.bar(
                x=list(theme_counts.values()),
                y=list(theme_counts.keys()),
                orientation='h',
                color=list(theme_counts.values()),
                color_continuous_scale='Viridis'
            )
            fig.update_layout(
                height=400,
                showlegend=False,
                xaxis_title='Content Count',
                yaxis_title='Theme'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### Theme Breakdown")
            total = sum(theme_counts.values())
            for theme, count in sorted(theme_counts.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total * 100) if total > 0 else 0
                st.markdown(f"**{theme}**")
                st.progress(pct / 100)
                st.caption(f"{count} posts ({pct:.1f}%)")

        # Theme by agent
        st.subheader("📊 Theme Distribution by Agent")

        agent_themes = []
        for agent in [a['name'] for a in AGENTS]:
            agent_df = df[df['agent_name'] == agent]
            agent_theme_counts = {theme: 0 for theme in themes}

            if not agent_df.empty and 'primary_content' in agent_df.columns:
                for content in agent_df['primary_content'].dropna():
                    content_lower = str(content).lower()
                    for theme, keywords in themes.items():
                        if any(kw in content_lower for kw in keywords):
                            agent_theme_counts[theme] += 1

            for theme, count in agent_theme_counts.items():
                agent_themes.append({
                    'agent': agent,
                    'theme': theme,
                    'count': count
                })

        theme_df = pd.DataFrame(agent_themes)
        if not theme_df.empty:
            fig = px.bar(
                theme_df,
                x='agent',
                y='count',
                color='theme',
                barmode='group',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=400, legend=dict(orientation='h', yanchor='bottom', y=1.02))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No theme data available for agents")
