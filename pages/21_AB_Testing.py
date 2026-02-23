"""
A/B Testing - Ad copy creation and published campaign tracking
Data from Text/AbTest tab in Channel ROI sheet.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_ab_testing_data, refresh_ab_testing_data, count_ab_testing
from config import SIDEBAR_HIDE_CSS

_PAGE_CSS = """
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
"""


def render_content(key_prefix="ab"):
    """Render A/B Testing content. Can be called standalone or from Operations wrapper."""

    with st.spinner("Loading A/B Testing data..."):
        ab_data = load_ab_testing_data()

    summary_df = ab_data.get('summary', pd.DataFrame())
    detail_df = ab_data.get('detail', pd.DataFrame())
    published_df = ab_data.get('published', pd.DataFrame())

    if summary_df.empty and detail_df.empty:
        st.error("No A/B Testing data available.")
        return

    # Build date range from all available dates
    all_dates = set()
    if not detail_df.empty and 'batch_date' in detail_df.columns:
        bd = pd.to_datetime(detail_df['batch_date'], errors='coerce').dropna()
        all_dates.update(bd.dt.date)
    if not published_df.empty and 'publish_date' in published_df.columns:
        pd_dates = pd.to_datetime(published_df['publish_date'], errors='coerce').dropna()
        all_dates.update(pd_dates.dt.date)

    # Inline date filters
    fc1, fc2, fc3 = st.columns([1.5, 1.5, 1])
    date_range = None

    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
        default_start = max(min_date, max_date - timedelta(days=30))

        with fc1:
            start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date, key=f"{key_prefix}_from")
        with fc2:
            end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key=f"{key_prefix}_to")

        date_range = (pd.Timestamp(start_date), pd.Timestamp(end_date))

    # Count per agent with date filter
    ab_counts = count_ab_testing(ab_data, date_range=date_range)

    # Overall KPI cards
    st.markdown('<div class="section-header"><h3>📊 A/B TESTING OVERVIEW</h3></div>', unsafe_allow_html=True)

    total_texts = sum(v.get('primary_text', 0) for v in ab_counts.values())
    total_published = sum(v.get('published_ad', 0) for v in ab_counts.values())
    total_agents = len(ab_counts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Primary Texts", f"{total_texts:,}")
    c2.metric("Total Published Ads", f"{total_published:,}")
    c3.metric("Active Agents", f"{total_agents}")
    c4.metric("Avg Published/Agent", f"{total_published / total_agents:.1f}" if total_agents > 0 else "-")

    # Per-agent breakdown
    st.divider()
    st.markdown('<div class="section-header"><h3>📈 OUTPUT PER AGENT</h3></div>', unsafe_allow_html=True)

    if ab_counts:
        chart_rows = []
        for agent, counts in sorted(ab_counts.items()):
            chart_rows.append({'Agent': agent.title(), 'Type': 'Primary Texts', 'Count': counts.get('primary_text', 0)})
            chart_rows.append({'Agent': agent.title(), 'Type': 'Published Ads', 'Count': counts.get('published_ad', 0)})

        chart_df = pd.DataFrame(chart_rows)
        fig = px.bar(
            chart_df, x='Agent', y='Count', color='Type',
            barmode='group', title='A/B Testing Output by Agent',
            color_discrete_map={
                'Primary Texts': '#3b82f6',
                'Published Ads': '#22c55e',
            },
        )
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_agents")

        # Scoring table
        st.subheader("KPI Scoring")
        score_rows = []
        for agent, counts in sorted(ab_counts.items()):
            published = counts.get('published_ad', 0)
            if published >= 20:
                score = 4
            elif published >= 11:
                score = 3
            elif published >= 6:
                score = 2
            else:
                score = 1
            score_rows.append({
                'Agent': agent.title(),
                'Primary Texts': counts.get('primary_text', 0),
                'Published Ads': published,
                'Score': score,
            })

        score_df = pd.DataFrame(score_rows)

        # HTML table with colored scores
        html = '<table style="width:100%;border-collapse:collapse;font-size:14px">'
        html += '<tr style="background:#1e293b;color:#fff">'
        for col in ['Agent', 'Primary Texts', 'Published Ads', 'Score']:
            html += f'<th style="padding:8px;text-align:center;border:1px solid #334155">{col}</th>'
        html += '</tr>'

        for _, r in score_df.iterrows():
            score = r['Score']
            if score >= 4:
                color = '#22c55e'
            elif score >= 3:
                color = '#eab308'
            elif score >= 2:
                color = '#f97316'
            else:
                color = '#ef4444'

            html += '<tr style="border:1px solid #334155">'
            html += f'<td style="padding:6px;font-weight:bold;border:1px solid #334155">{r["Agent"]}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["Primary Texts"]}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155">{r["Published Ads"]}</td>'
            html += f'<td style="padding:6px;text-align:center;border:1px solid #334155;background:{color};color:#fff;font-weight:bold">{score}/4</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

        st.caption("Scoring: 4 (>=20 published) | 3 (11-19) | 2 (6-10) | 1 (<6)")

    # Detail log
    if not detail_df.empty:
        st.divider()
        st.markdown('<div class="section-header"><h3>📋 CAMPAIGN DETAIL LOG</h3></div>', unsafe_allow_html=True)

        # Inline filters
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            creators = sorted(detail_df['creator'].dropna().str.strip().unique())
            selected_creator = st.selectbox("Creator", ["All"] + [c for c in creators if c], key=f"{key_prefix}_creator")
        with fc2:
            advertisers = sorted(detail_df['advertiser'].dropna().str.strip().unique())
            selected_advertiser = st.selectbox("Advertiser", ["All"] + [a for a in advertisers if a], key=f"{key_prefix}_advertiser")

        filtered = detail_df.copy()

        # Apply date filter to detail log
        if date_range:
            filtered['_batch_dt'] = pd.to_datetime(filtered['batch_date'], errors='coerce')
            filtered = filtered[
                (filtered['_batch_dt'].notna()) &
                (filtered['_batch_dt'] >= date_range[0]) &
                (filtered['_batch_dt'] <= date_range[1])
            ]
            filtered = filtered.drop(columns=['_batch_dt'])

        if selected_creator != "All":
            filtered = filtered[filtered['creator'].str.strip() == selected_creator]
        if selected_advertiser != "All":
            filtered = filtered[filtered['advertiser'].str.strip() == selected_advertiser]

        # Display columns
        display_cols = ['batch_date', 'creator', 'headline', 'advertiser', 'total_published']
        available_cols = [c for c in display_cols if c in filtered.columns]
        display_df = filtered[available_cols].copy()
        rename_map = {
            'batch_date': 'Date',
            'creator': 'Creator',
            'headline': 'Headline',
            'advertiser': 'Advertiser',
            'total_published': 'Published',
        }
        display_df = display_df.rename(columns=rename_map)

        if 'Date' in display_df.columns:
            display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%m/%d/%Y')

        search = st.text_input("Search", placeholder="Type to search across all columns...", key=f"{key_prefix}_search")
        if search:
            display_df = display_df[display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

        st.dataframe(display_df, use_container_width=True, hide_index=True, height=500, key=f"{key_prefix}_tbl_detail")
        st.caption(f"Showing {len(display_df)} of {len(filtered)} records")


def main():
    st.set_page_config(page_title="A/B Testing", page_icon="🧪", layout="wide")
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

    st.title("🧪 A/B Testing")

    # Sidebar
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_ab_testing_data()
            st.rerun()

    render_content()


if not hasattr(st, '_is_recharge_import'):
    main()
