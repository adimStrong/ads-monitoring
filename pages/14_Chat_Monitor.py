"""
Chat Monitor - Telegram Group Chat Viewer
Fetches messages from Railway Chat Listener API.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SIDEBAR_HIDE_CSS

st.set_page_config(page_title="Chat Monitor", page_icon="💬", layout="wide")

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Railway API config
CHAT_API_URL = os.getenv("CHAT_API_URL", "https://humble-illumination-production-713f.up.railway.app")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "juan365chat")
PH_TZ = timezone(timedelta(hours=8))


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


@st.cache_data(ttl=30)
def load_stats():
    return api_get('/api/stats') or {}


@st.cache_data(ttl=30)
def load_messages(search_term=None, date_from=None, date_to=None, user_filter=None, limit=500):
    params = {'limit': limit}
    if search_term:
        params['search'] = search_term
    if date_from:
        params['date_from'] = str(date_from)
    if date_to:
        params['date_to'] = str(date_to)
    if user_filter and user_filter != "All":
        params['user'] = user_filter

    data = api_get('/api/messages', params)
    if data and data.get('messages'):
        return pd.DataFrame(data['messages'])
    return pd.DataFrame()


def render_message(row):
    name = row.get('first_name') or row.get('username') or 'Unknown'
    username = row.get('username', '')
    date_ph = row.get('date_ph', '')
    text = row.get('text', '')
    if not isinstance(text, str):
        text = ''
    msg_type = row.get('message_type', 'text')

    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

    type_badge = ''
    if msg_type != 'text':
        type_badge = f' <span style="background:#4a4a6a;padding:1px 6px;border-radius:8px;font-size:0.7em;">{msg_type}</span>'

    at_user = f' <span style="color:#888;font-size:0.8em;">@{username}</span>' if username else ''

    return f"""
    <div style="padding:8px 12px;margin:3px 0;border-left:3px solid #4a9eff;background:rgba(74,158,255,0.05);border-radius:0 6px 6px 0;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span><strong style="color:#4a9eff;">{name}</strong>{at_user}{type_badge}</span>
            <span style="color:#888;font-size:0.8em;">{date_ph}</span>
        </div>
        <div style="margin-top:4px;color:#e0e0e0;">{text}</div>
    </div>
    """


def main():
    st.title("💬 Chat Monitor")
    st.markdown("Telegram Group Chat Viewer & Search")

    stats = load_stats()

    if not stats or stats.get('total', 0) == 0:
        st.warning("No messages yet. The listener bot is running on Railway and collecting new messages.")
        st.info(f"API: `{CHAT_API_URL}`")
        return

    # Sidebar
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")

        st.subheader("🔍 Search")
        search_term = st.text_input("Search messages (case-insensitive)", placeholder="e.g. Cost Per FTD")

        st.markdown("---")
        st.subheader("📅 Date Range")

        first_date = stats.get('first_date')
        last_date = stats.get('last_date')

        if first_date and last_date:
            min_date = datetime.strptime(first_date[:10], '%Y-%m-%d').date()
            max_date = datetime.strptime(last_date[:10], '%Y-%m-%d').date()
            date_from = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
            date_to = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)
        else:
            date_from = date_to = None

        st.markdown("---")
        st.subheader("👤 User Filter")
        user_options = ["All"] + [u['name'] for u in stats.get('user_activity', [])]
        user_filter = st.selectbox("Filter by user", user_options)

        st.markdown("---")
        st.subheader("📊 Quick Stats")
        st.metric("Total Messages", f"{stats['total']:,}")
        st.metric("Active Users", stats['users'])
        st.metric("Today", stats['today'])

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Messages", f"{stats['total']:,}")
    with col2:
        st.metric("Active Users", stats['users'])
    with col3:
        st.metric("Messages Today", stats['today'])
    with col4:
        st.metric("Avg/Day", stats['avg_per_day'])

    st.markdown("---")

    # Load filtered messages
    messages_df = load_messages(
        search_term=search_term if search_term else None,
        date_from=date_from,
        date_to=date_to,
        user_filter=user_filter if user_filter != "All" else None,
        limit=1000,
    )

    tab1, tab2, tab3 = st.tabs(["💬 Messages", "📊 Analytics", "📋 Data Table"])

    with tab1:
        if search_term:
            st.markdown(f"### 🔍 Search results for: **{search_term}**")
            st.caption(f"Found {len(messages_df):,} message(s)")

        if messages_df.empty:
            st.info("No messages found matching your filters.")
        else:
            html_parts = []
            for _, row in messages_df.iterrows():
                html_parts.append(render_message(row))

            page_size = 50
            total_pages = max(1, (len(html_parts) + page_size - 1) // page_size)
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="msg_page")
            start = (page - 1) * page_size
            end = start + page_size

            st.markdown(
                f'<div style="max-height:600px;overflow-y:auto;">{"".join(html_parts[start:end])}</div>',
                unsafe_allow_html=True
            )
            st.caption(f"Showing {start+1}-{min(end, len(html_parts))} of {len(html_parts)} messages | Page {page}/{total_pages}")

    with tab2:
        if not messages_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                user_data = stats.get('user_activity', [])
                if user_data:
                    user_df = pd.DataFrame(user_data).head(15)
                    user_df.columns = ['User', 'Messages']
                    fig = px.bar(user_df, x='User', y='Messages',
                                title='Messages by User (Top 15)',
                                color='Messages', color_continuous_scale='Blues')
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                type_data = stats.get('type_dist', [])
                if type_data:
                    type_df = pd.DataFrame(type_data)
                    type_df.columns = ['Type', 'Count']
                    fig = px.pie(type_df, values='Count', names='Type',
                                title='Message Types',
                                color_discrete_sequence=px.colors.qualitative.Set3)
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

            if 'date_ph' in messages_df.columns:
                daily = messages_df.copy()
                daily['day'] = daily['date_ph'].str[:10]
                daily_counts = daily.groupby('day').size().reset_index(name='messages')
                daily_counts = daily_counts.sort_values('day')

                fig = px.line(daily_counts, x='day', y='messages',
                            title='Daily Message Volume', markers=True)
                fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Messages")
                st.plotly_chart(fig, use_container_width=True)

            if 'date_ph' in messages_df.columns:
                hourly = messages_df.copy()
                hourly['hour'] = hourly['date_ph'].str[11:13].astype(int)
                hourly_counts = hourly.groupby('hour').size().reset_index(name='messages')

                fig = px.bar(hourly_counts, x='hour', y='messages',
                            title='Hourly Message Distribution (PH Time)',
                            color='messages', color_continuous_scale='Viridis')
                fig.update_layout(height=350, xaxis_title="Hour (24h)", yaxis_title="Messages",
                                xaxis=dict(dtick=1))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data to analyze.")

    with tab3:
        if not messages_df.empty:
            display_df = messages_df[['date_ph', 'first_name', 'username', 'text', 'message_type']].copy()
            display_df['text'] = display_df['text'].fillna('')
            display_df.columns = ['Date (PH)', 'Name', 'Username', 'Message', 'Type']
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)

            csv = display_df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, f"chat_messages_{datetime.now():%Y%m%d}.csv")
        else:
            st.info("No messages to display.")

    st.caption(f"Chat Monitor | Last message: {stats.get('last_date', 'N/A')} | Source: Railway API")


if __name__ == "__main__":
    main()
