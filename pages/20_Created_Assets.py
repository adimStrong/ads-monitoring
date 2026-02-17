"""
Created Assets - Gmail, FB Accounts, Pages & BMs inventory
Data from Created Assets tab in Channel ROI sheet.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_created_assets_data, refresh_created_assets_data, count_created_assets
from config import SIDEBAR_HIDE_CSS

_PAGE_CSS = """
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
"""


def render_content(key_prefix="ca"):
    """Render Created Assets content. Can be called standalone or from Operations wrapper."""

    with st.spinner("Loading Created Assets data..."):
        assets_df = load_created_assets_data()

    if assets_df.empty:
        st.error("No Created Assets data available.")
        return

    # Inline filter (was sidebar)
    fc1, fc2 = st.columns([3, 1])
    with fc2:
        creators = sorted(assets_df['creator'].str.strip().unique())
        selected = st.selectbox("Creator", ["All"] + creators, key=f"{key_prefix}_creator")

    filtered = assets_df.copy()
    if selected != "All":
        filtered = filtered[filtered['creator'].str.strip() == selected]

    # Count assets
    asset_counts = count_created_assets(filtered)

    # Overall KPI cards
    st.markdown('<div class="section-header"><h3>📊 ASSETS OVERVIEW</h3></div>', unsafe_allow_html=True)

    total_gmail = sum(v.get('gmail', 0) for v in asset_counts.values())
    total_fb = sum(v.get('fb_accounts', 0) for v in asset_counts.values())
    total_pages = sum(v.get('fb_pages', 0) for v in asset_counts.values())
    total_bms = sum(v.get('bms', 0) for v in asset_counts.values())
    total_all = total_gmail + total_fb + total_pages + total_bms

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Assets", f"{total_all:,}")
    c2.metric("Gmail/Outlook", f"{total_gmail:,}")
    c3.metric("FB Accounts", f"{total_fb:,}")
    c4.metric("FB Pages", f"{total_pages:,}")
    c5.metric("Business Managers", f"{total_bms:,}")

    # Per-creator breakdown
    st.divider()
    st.markdown('<div class="section-header"><h3>📈 ASSETS PER CREATOR</h3></div>', unsafe_allow_html=True)

    if asset_counts:
        chart_rows = []
        for creator, counts in sorted(asset_counts.items()):
            chart_rows.append({'Creator': creator, 'Type': 'Gmail', 'Count': counts['gmail']})
            chart_rows.append({'Creator': creator, 'Type': 'FB Accounts', 'Count': counts['fb_accounts']})
            chart_rows.append({'Creator': creator, 'Type': 'FB Pages', 'Count': counts['fb_pages']})
            chart_rows.append({'Creator': creator, 'Type': 'BMs', 'Count': counts['bms']})

        chart_df = pd.DataFrame(chart_rows)
        fig = px.bar(
            chart_df, x='Creator', y='Count', color='Type',
            barmode='stack', title='Assets by Creator',
            color_discrete_map={
                'Gmail': '#3b82f6', 'FB Accounts': '#22c55e',
                'FB Pages': '#f59e0b', 'BMs': '#a855f7',
            },
        )
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_creators")

        # Summary table
        summary_rows = []
        for creator, counts in sorted(asset_counts.items()):
            summary_rows.append({
                'Creator': creator,
                'Gmail': counts['gmail'],
                'FB Accounts': counts['fb_accounts'],
                'FB Pages': counts['fb_pages'],
                'BMs': counts['bms'],
                'Total Accounts': counts['total_accounts'],
                'Total Assets': counts['total_assets'],
                'Grand Total': counts['gmail'] + counts['fb_accounts'] + counts['fb_pages'] + counts['bms'],
            })
        summary = pd.DataFrame(summary_rows)
        st.dataframe(summary, use_container_width=True, hide_index=True, key=f"{key_prefix}_tbl_summary")

    # Condition breakdown
    st.divider()
    st.markdown('<div class="section-header"><h3>📋 CONDITION BREAKDOWN</h3></div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        # FB Account conditions
        fb_conds = filtered[filtered['fb_username'].str.strip() != '']['fb_condition'].str.strip().str.upper()
        fb_conds = fb_conds[fb_conds != '']
        if not fb_conds.empty:
            cond_counts = fb_conds.value_counts().reset_index()
            cond_counts.columns = ['Condition', 'Count']
            fig2 = px.pie(cond_counts, names='Condition', values='Count', title='FB Account Conditions')
            st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_pie_fb")

    with col_b:
        # Page conditions
        pg_conds = filtered[filtered['fb_page'].str.strip() != '']['page_condition'].str.strip().str.upper()
        pg_conds = pg_conds[pg_conds != '']
        if not pg_conds.empty:
            cond_counts = pg_conds.value_counts().reset_index()
            cond_counts.columns = ['Condition', 'Count']
            fig3 = px.pie(cond_counts, names='Condition', values='Count', title='Page Conditions')
            st.plotly_chart(fig3, use_container_width=True, key=f"{key_prefix}_pie_pages")

    # BM conditions
    bm_conds = filtered[filtered['bm_name'].str.strip() != '']['bm_condition'].str.strip().str.upper()
    bm_conds = bm_conds[bm_conds != '']
    if not bm_conds.empty:
        cond_counts = bm_conds.value_counts().reset_index()
        cond_counts.columns = ['Condition', 'Count']
        fig4 = px.pie(cond_counts, names='Condition', values='Count', title='BM Conditions')
        st.plotly_chart(fig4, use_container_width=True, key=f"{key_prefix}_pie_bm")

    # Raw data table
    st.divider()
    st.markdown('<div class="section-header"><h3>📋 ALL RECORDS</h3></div>', unsafe_allow_html=True)

    # Display columns (exclude internal fields)
    display_cols = ['date', 'creator', 'gmail', 'fb_username', 'fb_condition', 'fb_page', 'page_condition', 'bm_name', 'bm_condition']
    display_df = filtered[display_cols].copy()
    display_df.columns = ['Date', 'Creator', 'Gmail/Outlook', 'FB Username', 'FB Condition', 'FB Page', 'Page Condition', 'BM Name', 'BM Condition']

    # Format dates
    display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%m/%d/%Y')

    search = st.text_input("Search", placeholder="Type to search across all columns...", key=f"{key_prefix}_search")
    if search:
        display_df = display_df[display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500, key=f"{key_prefix}_tbl_records")
    st.caption(f"Showing {len(display_df)} of {len(filtered)} records")


def main():
    st.set_page_config(page_title="Created Assets", page_icon="🏗️", layout="wide")
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

    st.title("🏗️ Created Assets")

    # Sidebar
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_created_assets_data()
            st.rerun()

    render_content()


if not hasattr(st, '_is_recharge_import'):
    main()
