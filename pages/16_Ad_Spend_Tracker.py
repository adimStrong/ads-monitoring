"""
Ad Spend Tracker - Parse and track Google Ads & Meta Ads hourly reports from Telegram.

Extracts structured data from agent messages sent in the TG group:
- Google Ads: BrandKw, High INT, COMP, P-MAX, Auto Test (Cost + CPC)
- Meta Ads: Per-campaign Cost, Cost per FTD Before, Cost per FTD Now
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FACEBOOK_ADS_PERSONS, SIDEBAR_HIDE_CSS

st.set_page_config(page_title="Ad Spend Tracker", page_icon="💰", layout="wide")

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

CHAT_API_URL = os.getenv("CHAT_API_URL", "https://humble-illumination-production-713f.up.railway.app")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "juan365chat")
PH_TZ = timezone(timedelta(hours=8))

# Google Ads categories
GOOGLE_ADS_CATEGORIES = ["BrandKw", "HIgh INT", "COMP", "P-MAX", "Auto Test"]
# Normalize names for display
GOOGLE_ADS_DISPLAY = {
    "brandkw": "BrandKw",
    "high int": "High INT",
    "comp": "COMP",
    "p-max": "P-MAX",
    "auto test": "Auto Test",
}

# Meta Ads campaign patterns
META_CAMPAIGN_PATTERNS = [
    r"B-FB-FB-DEERPROMO\d+",
    r"PROM\d+\s*CHANNEL",
    r"PROMO\d+\s*CHANNEL",
]


def api_get(endpoint, params=None):
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


@st.cache_data(ttl=60)
def load_agent_messages(date_from=None, date_to=None):
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


def parse_google_ads(text):
    """Parse a Google Ads hourly report message into structured data.

    Expected format:
        Google Ads hourly report as of Feb 13,2026
        5AM

        BrandKw
        Cost: 624.30
        CPC: 104.05

        HIgh INT:
        Cost: 738.35
        CPC: 123.06
        ...
    """
    if not text or not isinstance(text, str):
        return None

    text_lower = text.lower()
    if 'google ads' not in text_lower or 'cost' not in text_lower:
        return None

    # Extract hour from header
    hour_match = re.search(r'(\d{1,2})\s*(am|pm)', text_lower)
    if not hour_match:
        return None

    hour_num = int(hour_match.group(1))
    ampm = hour_match.group(2)
    if ampm == 'pm' and hour_num != 12:
        hour_num += 12
    elif ampm == 'am' and hour_num == 12:
        hour_num = 0

    # Extract date from header
    date_match = re.search(r'(?:feb|mar|jan|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*(\d{1,2})\s*,?\s*(\d{4})', text_lower)
    report_date = None
    if date_match:
        try:
            month_str = text[date_match.start():date_match.start()+3]
            day = int(date_match.group(1))
            year = int(date_match.group(2))
            months = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
            month = months.get(month_str.lower(), 2)
            report_date = f"{year}-{month:02d}-{day:02d}"
        except:
            pass

    # Parse each category
    results = []
    # Split by known categories
    categories = [
        ("brandkw", "BrandKw"),
        ("high int", "High INT"),
        ("comp", "COMP"),
        ("p-max", "P-MAX"),
        ("auto test", "Auto Test"),
    ]

    for cat_key, cat_name in categories:
        # Find the section for this category
        cat_idx = text_lower.find(cat_key)
        if cat_idx == -1:
            continue

        # Get text from this category to the next one (or end)
        next_idx = len(text)
        for other_key, _ in categories:
            if other_key == cat_key:
                continue
            other_idx = text_lower.find(other_key, cat_idx + len(cat_key))
            if other_idx != -1 and other_idx < next_idx:
                next_idx = other_idx

        section = text[cat_idx:next_idx]

        # Extract Cost
        cost_match = re.search(r'cost[:\s]*([0-9,]+\.?\d*)', section.lower())
        cost = 0.0
        if cost_match:
            cost = float(cost_match.group(1).replace(',', ''))

        # Extract CPC
        cpc_match = re.search(r'cpc[:\s]*([0-9,]+\.?\d*)', section.lower())
        cpc = 0.0
        if cpc_match:
            cpc = float(cpc_match.group(1).replace(',', ''))

        results.append({
            'category': cat_name,
            'cost': cost,
            'cpc': cpc,
        })

    if not results:
        return None

    total_cost = sum(r['cost'] for r in results)
    return {
        'type': 'google',
        'hour': hour_num,
        'date': report_date,
        'total_cost': total_cost,
        'categories': results,
    }


def parse_meta_ads(text):
    """Parse a Meta Ads report message into structured data.

    Expected formats:
        02/13 Meta Ads Report As Of 5AM
        B-FB-FB-DEERPROMO07 (ADRIAN)
        Cost: 52.17
        Cost per FTD before: 10.77
        Cost per FTD now: 8.69

    Or individual:
        As of 6PM
        PROMO10 CHANNEL
        Cost: 1057.33
        Cost per FTD Before: 15.10
        Cost per FTD Now: 15.32
    """
    if not text or not isinstance(text, str):
        return None

    text_lower = text.lower()

    # Must have cost per ftd or be a meta ads report
    is_meta_report = 'meta ads' in text_lower
    has_ftd = 'cost per ftd' in text_lower
    has_channel = bool(re.search(r'prom\w*\d+\s*channel|b-fb-fb-', text_lower))

    if not (is_meta_report or (has_ftd and has_channel)):
        return None

    # Don't match google ads reports or yesterday summary reports
    if 'google ads' in text_lower:
        return None
    if 'yesterday report' in text_lower:
        return None

    # Extract hour - if not found in text, return None (caller will use msg timestamp)
    hour_match = re.search(r'(\d{1,2})\s*(am|pm)', text_lower)
    hour_num = None
    if hour_match:
        hour_num = int(hour_match.group(1))
        ampm = hour_match.group(2)
        if ampm == 'pm' and hour_num != 12:
            hour_num += 12
        elif ampm == 'am' and hour_num == 12:
            hour_num = 0

    # Extract date
    date_match = re.search(r'(\d{2})/(\d{2})', text)
    report_date = None
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        report_date = f"2026-{month:02d}-{day:02d}"

    # Parse campaigns - split by campaign name patterns
    campaigns = []

    # Find all campaign sections
    campaign_pattern = re.compile(
        r'(B-FB-FB-\w+|PROM\w*\d+\s*CHANNEL|PROMO\d+\s*CHANNEL)',
        re.IGNORECASE
    )

    matches = list(campaign_pattern.finditer(text))

    for i, match in enumerate(matches):
        camp_name = match.group(1).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start:end]

        # Extract agent name in parentheses
        agent_match = re.search(r'\((\w+)\)', section)
        agent = agent_match.group(1).upper() if agent_match else ""

        # Extract Cost (standalone "Cost:" not "Cost per FTD")
        cost = 0.0
        # Try line-by-line first (multi-line format)
        found_cost = False
        for line in section.split('\n'):
            line_stripped = line.strip().lower()
            if line_stripped.startswith('cost:') or line_stripped.startswith('cost :'):
                cm = re.search(r'([0-9,]+\.?\d*)', line)
                if cm:
                    cost = float(cm.group(1).replace(',', ''))
                found_cost = True
                break
        # Fallback: single-line format - find "Cost:" that's NOT followed by "per"
        if not found_cost:
            for cm in re.finditer(r'cost[:\s]+([0-9,]+\.?\d*)', section.lower()):
                # Check if this is "cost per ftd"
                after_cost = section.lower()[cm.start():cm.start()+15]
                if 'per' not in after_cost:
                    cost = float(cm.group(1).replace(',', ''))
                    break

        # Extract Cost per FTD Before
        ftd_before_match = re.search(r'cost\s*per\s*ftd\s*before[:\s]*([0-9,]+\.?\d*)', section.lower())
        ftd_before = 0.0
        if ftd_before_match:
            ftd_before = float(ftd_before_match.group(1).replace(',', ''))

        # Extract Cost per FTD Now
        ftd_now_match = re.search(r'cost\s*per\s*ftd\s*now[:\s]*([0-9,]+\.?\d*)', section.lower())
        ftd_now = 0.0
        if ftd_now_match:
            ftd_now = float(ftd_now_match.group(1).replace(',', ''))

        campaigns.append({
            'campaign': camp_name,
            'agent': agent,
            'cost': cost,
            'ftd_before': ftd_before,
            'ftd_now': ftd_now,
        })

    if not campaigns:
        return None

    total_cost = sum(c['cost'] for c in campaigns)
    return {
        'type': 'meta',
        'hour': hour_num,
        'date': report_date,
        'total_cost': total_cost,
        'campaigns': campaigns,
    }


def extract_all_reports(agent_msgs):
    """Extract all Google Ads and Meta Ads reports from agent messages."""
    google_reports = []
    meta_reports = []

    if agent_msgs.empty:
        return google_reports, meta_reports

    for _, row in agent_msgs.iterrows():
        text = row.get('text', '')
        if not isinstance(text, str) or not text:
            continue

        agent = row.get('agent', 'Unknown')
        date_ph = row.get('date_ph', '')
        date_only = row.get('date_only', None)
        hour = row.get('hour', 0)

        # Try Google Ads parse
        google = parse_google_ads(text)
        if google:
            google['agent'] = agent
            google['sent_at'] = date_ph
            if not google['date'] and date_only:
                google['date'] = str(date_only)
            google_reports.append(google)
            continue

        # Try Meta Ads parse
        meta = parse_meta_ads(text)
        if meta:
            meta['agent'] = agent
            meta['sent_at'] = date_ph
            if meta['hour'] is None:
                meta['hour'] = hour
            if not meta['date'] and date_only:
                meta['date'] = str(date_only)
            meta_reports.append(meta)

    return google_reports, meta_reports


def main():
    st.title("💰 Ad Spend Tracker")
    st.markdown("Track Google Ads & Meta Ads hourly spend from Telegram reports")

    # Sidebar
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("📅 Date Range")

        stats = api_get('/api/stats') or {}
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
        st.subheader("📋 Info")
        st.caption("Parses hourly reports from TG group messages")
        st.caption("Google Ads: BrandKw, High INT, COMP, P-MAX, Auto Test")
        st.caption("Meta Ads: Campaign costs + Cost per FTD")

    # Load data
    str_from = str(date_from) if date_from else None
    str_to = str(date_to) if date_to else None
    agent_msgs = load_agent_messages(str_from, str_to)

    if agent_msgs.empty:
        st.warning("No agent messages found. Make sure the bot is collecting messages.")
        return

    # Extract reports
    google_reports, meta_reports = extract_all_reports(agent_msgs)

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Google Ads Reports", len(google_reports))
    with col2:
        if google_reports:
            latest = google_reports[0]
            st.metric("Latest Google Total", f"₱{latest['total_cost']:,.2f}", f"{latest['hour']}:00")
        else:
            st.metric("Latest Google Total", "N/A")
    with col3:
        st.metric("Meta Ads Reports", len(meta_reports))
    with col4:
        if meta_reports:
            latest = meta_reports[0]
            st.metric("Latest Meta Total", f"₱{latest['total_cost']:,.2f}", f"{latest['hour']}:00")
        else:
            st.metric("Latest Meta Total", "N/A")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Google Ads", "📱 Meta Ads", "📋 Raw Data"])

    # ==================== GOOGLE ADS TAB ====================
    with tab1:
        st.markdown("### Google Ads Hourly Tracker")

        if not google_reports:
            st.info("No Google Ads reports found in messages.")
        else:
            # Group by date
            dates = sorted(set(r['date'] for r in google_reports if r['date']), reverse=True)

            if dates:
                selected_date = st.selectbox("Select Date", dates, key="google_date")
                day_reports = [r for r in google_reports if r['date'] == selected_date]
                day_reports.sort(key=lambda x: x['hour'])

                # Latest totals
                if day_reports:
                    latest = day_reports[-1]
                    st.markdown(f"**Latest report: {latest['hour']}:00** (sent by {latest['agent']})")

                    cols = st.columns(len(latest['categories']))
                    for i, cat in enumerate(latest['categories']):
                        with cols[i]:
                            st.metric(cat['category'], f"₱{cat['cost']:,.2f}", f"CPC: {cat['cpc']:.2f}")

                # Hourly cost progression
                rows = []
                for r in day_reports:
                    for cat in r['categories']:
                        rows.append({
                            'Hour': f"{r['hour']}:00",
                            'hour_num': r['hour'],
                            'Category': cat['category'],
                            'Cost': cat['cost'],
                            'CPC': cat['cpc'],
                            'Agent': r['agent'],
                        })

                if rows:
                    df = pd.DataFrame(rows)

                    # Cost progression line chart
                    fig = px.line(
                        df, x='Hour', y='Cost', color='Category',
                        title=f'Google Ads - Hourly Cost Progression ({selected_date})',
                        markers=True,
                    )
                    fig.update_layout(height=450, yaxis_title="Cost (₱)", xaxis_title="Hour (PH)")
                    st.plotly_chart(fig, use_container_width=True)

                    # Total cost per hour
                    total_per_hour = df.groupby(['Hour', 'hour_num']).agg({'Cost': 'sum'}).reset_index()
                    total_per_hour = total_per_hour.sort_values('hour_num')

                    fig2 = px.bar(
                        total_per_hour, x='Hour', y='Cost',
                        title=f'Google Ads - Total Spend Per Hour ({selected_date})',
                        color='Cost', color_continuous_scale='Blues',
                    )
                    fig2.update_layout(height=400, yaxis_title="Total Cost (₱)")
                    st.plotly_chart(fig2, use_container_width=True)

                    # CPC trend
                    cpc_df = df[df['CPC'] > 0]
                    if not cpc_df.empty:
                        fig3 = px.line(
                            cpc_df, x='Hour', y='CPC', color='Category',
                            title=f'Google Ads - CPC Trend ({selected_date})',
                            markers=True,
                        )
                        fig3.update_layout(height=400, yaxis_title="CPC (₱)")
                        st.plotly_chart(fig3, use_container_width=True)

                    # Summary table
                    st.markdown("#### Hourly Data Table")
                    pivot = df.pivot_table(
                        index='Hour', columns='Category', values='Cost',
                        aggfunc='first'
                    )
                    pivot['Total'] = pivot.sum(axis=1)
                    st.dataframe(pivot, use_container_width=True)

    # ==================== META ADS TAB ====================
    with tab2:
        st.markdown("### Meta Ads Hourly Tracker")

        if not meta_reports:
            st.info("No Meta Ads reports found in messages.")
        else:
            dates = sorted(set(r['date'] for r in meta_reports if r['date']), reverse=True)

            if dates:
                selected_date = st.selectbox("Select Date", dates, key="meta_date")
                day_reports = [r for r in meta_reports if r['date'] == selected_date]
                day_reports.sort(key=lambda x: x['hour'])

                # Latest campaign data
                if day_reports:
                    latest = day_reports[-1]
                    st.markdown(f"**Latest report: {latest['hour']}:00** (sent by {latest['agent']})")

                    for camp in latest['campaigns']:
                        agent_tag = f" ({camp['agent']})" if camp['agent'] else ""
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(f"{camp['campaign']}{agent_tag}", f"₱{camp['cost']:,.2f}")
                        with col2:
                            st.metric("FTD Before", f"₱{camp['ftd_before']:.2f}" if camp['ftd_before'] else "N/A")
                        with col3:
                            delta = None
                            delta_color = "inverse"
                            if camp['ftd_before'] and camp['ftd_now']:
                                diff = camp['ftd_now'] - camp['ftd_before']
                                delta = f"₱{diff:+.2f}"
                            st.metric("FTD Now", f"₱{camp['ftd_now']:.2f}" if camp['ftd_now'] else "N/A", delta=delta, delta_color=delta_color)

                    st.markdown("---")

                # Build campaign cost progression
                rows = []
                for r in day_reports:
                    for camp in r['campaigns']:
                        agent_tag = f" ({camp['agent']})" if camp['agent'] else ""
                        rows.append({
                            'Hour': f"{r['hour']}:00",
                            'hour_num': r['hour'],
                            'Campaign': f"{camp['campaign']}{agent_tag}",
                            'Cost': camp['cost'],
                            'FTD Before': camp['ftd_before'],
                            'FTD Now': camp['ftd_now'],
                            'Agent': r['agent'],
                        })

                if rows:
                    df = pd.DataFrame(rows)

                    # Cost progression
                    fig = px.line(
                        df, x='Hour', y='Cost', color='Campaign',
                        title=f'Meta Ads - Hourly Cost Progression ({selected_date})',
                        markers=True,
                    )
                    fig.update_layout(height=450, yaxis_title="Cost (₱)")
                    st.plotly_chart(fig, use_container_width=True)

                    # FTD Now progression
                    ftd_df = df[df['FTD Now'] > 0]
                    if not ftd_df.empty:
                        fig2 = px.line(
                            ftd_df, x='Hour', y='FTD Now', color='Campaign',
                            title=f'Meta Ads - Cost per FTD Trend ({selected_date})',
                            markers=True,
                        )
                        fig2.update_layout(height=400, yaxis_title="Cost per FTD (₱)")
                        st.plotly_chart(fig2, use_container_width=True)

                    # Total cost per hour
                    total_per_hour = df.groupby(['Hour', 'hour_num']).agg({'Cost': 'sum'}).reset_index()
                    total_per_hour = total_per_hour.sort_values('hour_num')

                    fig3 = px.bar(
                        total_per_hour, x='Hour', y='Cost',
                        title=f'Meta Ads - Total Spend Per Hour ({selected_date})',
                        color='Cost', color_continuous_scale='Reds',
                    )
                    fig3.update_layout(height=400, yaxis_title="Total Cost (₱)")
                    st.plotly_chart(fig3, use_container_width=True)

                    # Summary table
                    st.markdown("#### Campaign Data Table")
                    display_df = df[['Hour', 'Campaign', 'Cost', 'FTD Before', 'FTD Now']].copy()
                    display_df = display_df.sort_values(['hour_num', 'Campaign'])
                    display_df = display_df.drop(columns=['hour_num'], errors='ignore')
                    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==================== RAW DATA TAB ====================
    with tab3:
        st.markdown("### All Parsed Reports")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Google Ads Reports")
            if google_reports:
                g_rows = []
                for r in google_reports:
                    for cat in r['categories']:
                        g_rows.append({
                            'Date': r['date'],
                            'Hour': r['hour'],
                            'Agent': r['agent'],
                            'Category': cat['category'],
                            'Cost': cat['cost'],
                            'CPC': cat['cpc'],
                            'Sent At': r['sent_at'],
                        })
                g_df = pd.DataFrame(g_rows)
                g_df = g_df.sort_values(['Date', 'Hour'], ascending=[False, False])
                st.dataframe(g_df, use_container_width=True, hide_index=True, height=400)

                csv = g_df.to_csv(index=False)
                st.download_button("📥 Download Google Ads CSV", csv,
                                  f"google_ads_{datetime.now():%Y%m%d}.csv")
            else:
                st.info("No Google Ads reports parsed.")

        with col2:
            st.markdown("#### Meta Ads Reports")
            if meta_reports:
                m_rows = []
                for r in meta_reports:
                    for camp in r['campaigns']:
                        m_rows.append({
                            'Date': r['date'],
                            'Hour': r['hour'],
                            'Agent': r['agent'],
                            'Campaign': camp['campaign'],
                            'Campaign Agent': camp['agent'],
                            'Cost': camp['cost'],
                            'FTD Before': camp['ftd_before'],
                            'FTD Now': camp['ftd_now'],
                            'Sent At': r['sent_at'],
                        })
                m_df = pd.DataFrame(m_rows)
                m_df = m_df.sort_values(['Date', 'Hour'], ascending=[False, False])
                st.dataframe(m_df, use_container_width=True, hide_index=True, height=400)

                csv = m_df.to_csv(index=False)
                st.download_button("📥 Download Meta Ads CSV", csv,
                                  f"meta_ads_{datetime.now():%Y%m%d}.csv")
            else:
                st.info("No Meta Ads reports parsed.")

    st.markdown("---")
    st.caption(f"Ad Spend Tracker | Source: Railway Chat API | {CHAT_API_URL}")


if __name__ == "__main__":
    main()
