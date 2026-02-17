"""
Reporting Accuracy - Track agent report submissions via Telegram chat
Fetches data from Railway Chat Listener API.

Rubric:
  4: < 15 minutes
  3: 15-24 minutes
  2: 25-34 minutes
  1: 35+ minutes
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    TELEGRAM_MENTIONS,
    TELEGRAM_ALT_USERNAMES,
    REPORTING_ACCURACY_SCORING,
    REPORT_KEYWORDS,
    REPORT_CAMPAIGN_INDICATORS,
    FACEBOOK_ADS_PERSONS,
    EXCLUDED_FROM_REPORTING,
    SIDEBAR_HIDE_CSS,
)

st.set_page_config(page_title="Reporting Accuracy", page_icon="📝", layout="wide")

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Railway API config
CHAT_API_URL = os.getenv("CHAT_API_URL", "https://humble-illumination-production-713f.up.railway.app")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "juan365chat")
PH_TZ = timezone(timedelta(hours=8))

# Reverse mapping: TG username -> Agent name (primary + alts)
USERNAME_TO_AGENT = {v.lower(): k.title() for k, v in TELEGRAM_MENTIONS.items()}
for agent, alts in TELEGRAM_ALT_USERNAMES.items():
    for alt in alts:
        USERNAME_TO_AGENT[alt.lower()] = agent.title()


def api_get(endpoint, params=None):
    """Fetch data from Railway Chat Listener API."""
    if params is None:
        params = {}
    params['key'] = CHAT_API_KEY
    try:
        resp = requests.get(f"{CHAT_API_URL}{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def score_minutes(minutes):
    """Score based on minutes after hour mark."""
    for score, low, high in REPORTING_ACCURACY_SCORING:
        if low <= minutes <= high:
            return score
    return 1


@st.cache_data(ttl=60)
def load_stats():
    return api_get('/api/stats') or {}


@st.cache_data(ttl=60)
def load_agent_messages(date_from=None, date_to=None):
    """Load agent messages from Railway API."""
    params = {}
    if date_from:
        params['date_from'] = str(date_from)
    if date_to:
        params['date_to'] = str(date_to)

    data = api_get('/api/agents', params)
    if data and data.get('agents'):
        df = pd.DataFrame(data['agents'])
        if not df.empty:
            df['datetime_ph'] = pd.to_datetime(df['date_ph'])
            df['date_only'] = df['datetime_ph'].dt.date
        return df
    return pd.DataFrame()


@st.cache_data(ttl=60)
def load_reporting_scores():
    """Load reporting accuracy scores from Railway API."""
    return api_get('/api/reporting') or {}


def is_report_message(text):
    """Check if a message is a proper report (has campaign/format indicator + cost data).

    Casual messages like 'Wala pang cost?' won't match.
    """
    if not text or not isinstance(text, str):
        return False
    text_lower = text.lower()
    has_cost_data = any(kw in text_lower for kw in ["cost:", "cost per ftd", "cpc:"])
    has_indicator = any(ind in text_lower for ind in REPORT_CAMPAIGN_INDICATORS)
    return has_cost_data and has_indicator


def calculate_agent_scores(agent_df):
    """Calculate reporting accuracy scores for an agent.

    For each day, looks at when the agent sent their first report-like message
    and scores based on the minute of the hour.
    """
    if agent_df.empty:
        return pd.DataFrame()

    # Filter to report messages only
    report_msgs = agent_df[agent_df['text'].apply(is_report_message)].copy()

    if report_msgs.empty:
        return pd.DataFrame()

    # Group by date and hour - find first report message per hour
    scores = []
    for (date, hour), group in report_msgs.groupby(['date_only', 'hour']):
        first_msg = group.iloc[0]
        minute = first_msg['minute']
        score = score_minutes(minute)
        scores.append({
            'date': date,
            'hour': hour,
            'minute': minute,
            'score': score,
            'agent': first_msg['agent'],
            'text_preview': (first_msg['text'] or '')[:80],
            'time': first_msg['date_ph'],
        })

    return pd.DataFrame(scores)


def main():
    st.title("📝 Reporting Accuracy")
    st.markdown("Track agent report submissions via Telegram chat data")

    stats = load_stats()

    if not stats or stats.get('total', 0) == 0:
        st.warning("No messages yet. The listener bot is running on Railway and collecting new messages.")
        st.info(f"API: `{CHAT_API_URL}`")
        return

    total = stats['total']
    first_date = stats.get('first_date')
    last_date = stats.get('last_date')

    # Sidebar
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("📅 Date Range")

        if first_date and last_date:
            min_date = datetime.strptime(first_date[:10], '%Y-%m-%d').date()
            max_date = datetime.strptime(last_date[:10], '%Y-%m-%d').date()
            date_from = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
            date_to = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)
        else:
            date_from = date_to = None

        st.markdown("---")
        st.subheader("👤 Agent Filter")
        agents = ["All"] + [p.title() for p in FACEBOOK_ADS_PERSONS if p not in EXCLUDED_FROM_REPORTING]
        agent_filter = st.selectbox("Select Agent", agents)

        st.markdown("---")
        st.subheader("📊 Scoring Rubric")
        st.markdown("""
        | Score | Minutes |
        |-------|---------|
        | **4** | < 15 min |
        | **3** | 15-24 min |
        | **2** | 25-34 min |
        | **1** | 35+ min |
        """)

        st.markdown("---")
        st.subheader("📋 Info")
        st.metric("Total Messages", f"{total:,}")
        st.caption(f"First: {first_date[:10] if first_date else 'N/A'}")
        st.caption(f"Last: {last_date[:10] if last_date else 'N/A'}")

    # Load data
    str_from = str(date_from) if date_from else None
    str_to = str(date_to) if date_to else None

    agent_msgs = load_agent_messages(str_from, str_to)

    # Overview stats
    st.markdown("### 📊 Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Messages", f"{total:,}")
    with col2:
        agent_count = len(agent_msgs['agent'].unique()) if not agent_msgs.empty else 0
        st.metric("Active Agents", agent_count)
    with col3:
        report_count = len(agent_msgs[agent_msgs['text'].apply(is_report_message)]) if not agent_msgs.empty else 0
        st.metric("Report Messages", f"{report_count:,}")
    with col4:
        if not agent_msgs.empty:
            report_msgs = agent_msgs[agent_msgs['text'].apply(is_report_message)]
            if not report_msgs.empty:
                avg_min = report_msgs['minute'].mean()
                avg_score = score_minutes(int(avg_min))
                st.metric("Avg Score", f"{avg_score}/4", f"{avg_min:.0f} min avg")
            else:
                st.metric("Avg Score", "N/A")
        else:
            st.metric("Avg Score", "N/A")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Agent Scores", "📈 Hourly Pattern", "💬 Report Messages", "📋 All Data"])

    with tab1:
        st.markdown("### Agent Reporting Scores")

        if agent_msgs.empty:
            st.info("No agent messages found. Make sure the bot is collecting messages.")
        else:
            # Calculate scores per agent
            all_scores = []
            for agent_name in sorted(agent_msgs['agent'].unique()):
                if agent_name.upper() in EXCLUDED_FROM_REPORTING:
                    continue
                if agent_filter != "All" and agent_name != agent_filter:
                    continue
                adf = agent_msgs[agent_msgs['agent'] == agent_name]
                scores_df = calculate_agent_scores(adf)
                if not scores_df.empty:
                    all_scores.append(scores_df)

            if all_scores:
                combined_scores = pd.concat(all_scores, ignore_index=True)

                # Summary table
                summary = combined_scores.groupby('agent').agg(
                    reports=('score', 'count'),
                    avg_score=('score', 'mean'),
                    avg_minute=('minute', 'mean'),
                    score_4=('score', lambda x: (x == 4).sum()),
                    score_3=('score', lambda x: (x == 3).sum()),
                    score_2=('score', lambda x: (x == 2).sum()),
                    score_1=('score', lambda x: (x == 1).sum()),
                ).reset_index()
                summary['avg_score'] = summary['avg_score'].round(2)
                summary['avg_minute'] = summary['avg_minute'].round(1)
                summary = summary.sort_values('avg_score', ascending=False)

                # Color-coded display
                st.dataframe(
                    summary.rename(columns={
                        'agent': 'Agent',
                        'reports': 'Reports',
                        'avg_score': 'Avg Score',
                        'avg_minute': 'Avg Min',
                        'score_4': 'Score 4',
                        'score_3': 'Score 3',
                        'score_2': 'Score 2',
                        'score_1': 'Score 1',
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

                # Bar chart
                fig = px.bar(summary, x='agent', y='avg_score',
                            title='Average Reporting Score by Agent',
                            color='avg_score',
                            color_continuous_scale=['#ff4444', '#ff8800', '#ffcc00', '#44cc44'],
                            range_color=[1, 4])
                fig.update_layout(height=400, yaxis_range=[0, 4.5], yaxis_title="Score (1-4)")
                fig.add_hline(y=3, line_dash="dash", line_color="gray", annotation_text="Target (3)")
                st.plotly_chart(fig, use_container_width=True)

                # Score distribution
                score_dist = combined_scores.groupby(['agent', 'score']).size().reset_index(name='count')
                fig = px.bar(score_dist, x='agent', y='count', color='score',
                            title='Score Distribution by Agent',
                            barmode='stack',
                            color_discrete_map={4: '#44cc44', 3: '#ffcc00', 2: '#ff8800', 1: '#ff4444'})
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No report-related messages found from agents. Keywords searched: " + ", ".join(REPORT_KEYWORDS[:5]))

    with tab2:
        st.markdown("### Hourly Sending Pattern")

        if not agent_msgs.empty:
            filtered = agent_msgs
            if agent_filter != "All":
                filtered = agent_msgs[agent_msgs['agent'] == agent_filter]

            if not filtered.empty:
                # Messages per hour by agent
                hourly = filtered.groupby(['agent', 'hour']).size().reset_index(name='messages')

                fig = px.bar(hourly, x='hour', y='messages', color='agent',
                            title='Messages by Hour (PH Time)',
                            barmode='group')
                fig.update_layout(height=400, xaxis=dict(dtick=1),
                                xaxis_title="Hour (24h PH)", yaxis_title="Messages")
                st.plotly_chart(fig, use_container_width=True)

                # Heatmap: Agent x Hour
                pivot = filtered.groupby(['agent', 'hour']).size().reset_index(name='count')
                if not pivot.empty:
                    heatmap_data = pivot.pivot_table(index='agent', columns='hour', values='count', fill_value=0)
                    fig = px.imshow(heatmap_data,
                                   title='Agent Activity Heatmap (Messages per Hour)',
                                   labels=dict(x="Hour (PH)", y="Agent", color="Messages"),
                                   color_continuous_scale='YlOrRd',
                                   aspect='auto')
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                # Daily messages trend per agent
                daily = filtered.groupby(['agent', 'date_only']).size().reset_index(name='messages')
                daily['date_only'] = pd.to_datetime(daily['date_only'])
                fig = px.line(daily, x='date_only', y='messages', color='agent',
                            title='Daily Message Count by Agent',
                            markers=True)
                fig.update_layout(height=400, xaxis_title="Date", yaxis_title="Messages")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No messages for selected agent.")
        else:
            st.info("No agent messages found.")

    with tab3:
        st.markdown("### Report-Related Messages")
        st.caption("Messages containing keywords: " + ", ".join(REPORT_KEYWORDS[:8]))

        if not agent_msgs.empty:
            filtered = agent_msgs
            if agent_filter != "All":
                filtered = agent_msgs[agent_msgs['agent'] == agent_filter]

            report_msgs = filtered[filtered['text'].apply(is_report_message)].copy()

            if not report_msgs.empty:
                display = report_msgs[['date_ph', 'agent', 'text', 'hour', 'minute']].copy()
                display['score'] = display['minute'].apply(score_minutes)
                display = display.sort_values('date_ph', ascending=False)
                display.columns = ['Date (PH)', 'Agent', 'Message', 'Hour', 'Minute', 'Score']
                st.dataframe(display, use_container_width=True, hide_index=True, height=500)

                csv = display.to_csv(index=False)
                st.download_button("📥 Download Report Messages CSV", csv,
                                  f"report_messages_{datetime.now():%Y%m%d}.csv")
            else:
                st.info("No report-related messages found.")
        else:
            st.info("No agent messages found.")

    with tab4:
        st.markdown("### All Agent Messages")

        if not agent_msgs.empty:
            filtered = agent_msgs
            if agent_filter != "All":
                filtered = agent_msgs[agent_msgs['agent'] == agent_filter]

            display = filtered[['date_ph', 'agent', 'username', 'text', 'type']].copy()
            display = display.sort_values('date_ph', ascending=False)
            display.columns = ['Date (PH)', 'Agent', 'Username', 'Message', 'Type']
            st.dataframe(display, use_container_width=True, hide_index=True, height=500)

            csv = display.to_csv(index=False)
            st.download_button("📥 Download All Agent Messages CSV", csv,
                              f"agent_messages_{datetime.now():%Y%m%d}.csv")
        else:
            st.info("No agent messages found.")

    st.markdown("---")
    st.caption(f"Reporting Accuracy | Source: Railway Chat API ({total:,} messages) | {CHAT_API_URL}")


if __name__ == "__main__":
    main()
