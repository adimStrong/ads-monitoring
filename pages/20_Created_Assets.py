"""
Created Assets - Gmail, FB Accounts, Pages & BMs inventory
Data from Created Assets tab in Channel ROI sheet.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_created_assets_data, refresh_created_assets_data, count_created_assets, count_assets_by_condition
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

    # Parse dates for filtering
    assets_df['date_parsed'] = pd.to_datetime(assets_df['date'], errors='coerce')

    # Inline filters
    fc1, fc2, fc3, fc4 = st.columns([1.5, 1.5, 2, 1])

    has_dates = assets_df['date_parsed'].notna().any()
    if has_dates:
        min_date = assets_df['date_parsed'].min().date()
        max_date = assets_df['date_parsed'].max().date()
        default_start = max(min_date, max_date - timedelta(days=30))

        with fc1:
            start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date, key=f"{key_prefix}_from")
        with fc2:
            end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key=f"{key_prefix}_to")
    else:
        start_date = None
        end_date = None

    with fc3:
        creators = sorted(assets_df['creator'].str.strip().unique())
        selected = st.selectbox("Creator", ["All"] + creators, key=f"{key_prefix}_creator")

    filtered = assets_df.copy()

    # Apply date filter
    if has_dates and start_date and end_date:
        filtered = filtered[
            (filtered['date_parsed'].notna()) &
            (filtered['date_parsed'].dt.date >= start_date) &
            (filtered['date_parsed'].dt.date <= end_date)
        ]

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

    # ── Asset Status Breakdown (Active vs Disabled vs Others) ──
    st.divider()
    st.markdown('<div class="section-header"><h3>Asset Status Breakdown</h3></div>', unsafe_allow_html=True)

    cond_data = count_assets_by_condition(filtered)

    # Aggregate across all creators
    asset_types = ['gmail', 'fb_accounts', 'fb_pages', 'bms']
    asset_labels = {'gmail': 'Gmail/Outlook', 'fb_accounts': 'FB Accounts', 'fb_pages': 'FB Pages', 'bms': 'Business Managers'}
    all_conditions = set()
    type_cond_totals = {at: {} for at in asset_types}

    for creator, types in cond_data.items():
        for at in asset_types:
            for cond, cnt in types.get(at, {}).items():
                type_cond_totals[at][cond] = type_cond_totals[at].get(cond, 0) + cnt
                all_conditions.add(cond)

    # Normalize conditions - group similar ones
    active_keys = {'ACTIVE', 'AVAILABLE'}
    disabled_keys = {'DISABLED', 'RESTRICTED', 'FOR VERIFY', 'SUSPENDED', 'CHECKPOINT'}

    def classify_status(cond):
        if cond in active_keys:
            return 'Active'
        elif cond in disabled_keys:
            return 'Disabled/Restricted'
        elif cond == 'UNKNOWN' or cond == '':
            return 'Unknown'
        else:
            return 'Other'

    # Build summary: Active vs Disabled vs Other per asset type
    status_groups = ['Active', 'Disabled/Restricted', 'Other']
    status_colors = {'Active': '#16a34a', 'Disabled/Restricted': '#dc2626', 'Other': '#64748b'}

    # KPI cards for Active vs Disabled
    total_active = 0
    total_disabled = 0
    for at in asset_types:
        for cond, cnt in type_cond_totals[at].items():
            status = classify_status(cond)
            if status == 'Active':
                total_active += cnt
            elif status == 'Disabled/Restricted':
                total_disabled += cnt

    total_other = total_all - total_active - total_disabled
    active_pct = (total_active / total_all * 100) if total_all > 0 else 0

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Active", f"{total_active:,}", f"{active_pct:.0f}%")
    sc2.metric("Disabled/Restricted", f"{total_disabled:,}")
    sc3.metric("Other", f"{total_other:,}")
    sc4.metric("Total", f"{total_all:,}")

    # Status table per asset type
    status_rows = []
    for at in asset_types:
        row = {'Asset Type': asset_labels[at]}
        at_total = 0
        for sg in status_groups:
            count = 0
            for cond, cnt in type_cond_totals[at].items():
                if classify_status(cond) == sg:
                    count += cnt
            row[sg] = count
            at_total += count
        row['Total'] = at_total
        row['Active %'] = f"{row['Active'] / at_total * 100:.0f}%" if at_total > 0 else "0%"
        status_rows.append(row)

    # Total row
    total_row = {'Asset Type': 'TOTAL'}
    for sg in status_groups:
        total_row[sg] = sum(r[sg] for r in status_rows)
    total_row['Total'] = total_all
    total_row['Active %'] = f"{active_pct:.0f}%"
    status_rows.append(total_row)

    # Render HTML table
    th = 'padding:8px 12px;text-align:center;border:1px solid #cbd5e1;font-size:13px'
    td = 'padding:6px 12px;text-align:center;border:1px solid #cbd5e1;font-size:13px'
    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b">'
    html += f'<th style="{th};text-align:left">Asset Type</th>'
    html += f'<th style="{th};color:#16a34a">Active</th>'
    html += f'<th style="{th};color:#dc2626">Disabled/Restricted</th>'
    html += f'<th style="{th};color:#64748b">Other</th>'
    html += f'<th style="{th}">Total</th>'
    html += f'<th style="{th}">Active %</th></tr>'

    for r in status_rows:
        is_total = r['Asset Type'] == 'TOTAL'
        bg = '#f8fafc' if is_total else '#ffffff'
        fw = 'font-weight:700' if is_total else ''
        html += f'<tr style="background:{bg};color:#1e293b;{fw}">'
        html += f'<td style="{td};text-align:left;{fw}">{r["Asset Type"]}</td>'
        html += f'<td style="{td};color:#16a34a;{fw}">{r["Active"]:,}</td>'
        html += f'<td style="{td};color:#dc2626;{fw}">{r["Disabled/Restricted"]:,}</td>'
        html += f'<td style="{td};color:#64748b;{fw}">{r["Other"]:,}</td>'
        html += f'<td style="{td};{fw}">{r["Total"]:,}</td>'
        html += f'<td style="{td};{fw}">{r["Active %"]}</td></tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Per-creator status breakdown
    st.markdown("#### Per-Creator Status")
    creator_status_rows = []
    for creator in sorted(cond_data.keys()):
        types = cond_data[creator]
        row = {'Creator': creator}
        cr_active = 0
        cr_disabled = 0
        cr_total = 0
        for at in asset_types:
            for cond, cnt in types.get(at, {}).items():
                status = classify_status(cond)
                if status == 'Active':
                    cr_active += cnt
                elif status == 'Disabled/Restricted':
                    cr_disabled += cnt
                cr_total += cnt
        row['Active'] = cr_active
        row['Disabled'] = cr_disabled
        row['Other'] = cr_total - cr_active - cr_disabled
        row['Total'] = cr_total
        row['Active %'] = f"{cr_active / cr_total * 100:.0f}%" if cr_total > 0 else "0%"
        creator_status_rows.append(row)

    if creator_status_rows:
        cst_df = pd.DataFrame(creator_status_rows)
        st.dataframe(cst_df, use_container_width=True, hide_index=True, key=f"{key_prefix}_tbl_status")

        # Stacked bar chart: Active vs Disabled per creator
        chart_rows = []
        for r in creator_status_rows:
            chart_rows.append({'Creator': r['Creator'], 'Status': 'Active', 'Count': r['Active']})
            chart_rows.append({'Creator': r['Creator'], 'Status': 'Disabled/Restricted', 'Count': r['Disabled']})
            if r['Other'] > 0:
                chart_rows.append({'Creator': r['Creator'], 'Status': 'Other', 'Count': r['Other']})
        chart_df = pd.DataFrame(chart_rows)
        fig_status = px.bar(
            chart_df, x='Creator', y='Count', color='Status',
            barmode='stack', title='Active vs Disabled Assets by Creator',
            color_discrete_map={'Active': '#16a34a', 'Disabled/Restricted': '#dc2626', 'Other': '#94a3b8'},
        )
        fig_status.update_layout(height=400, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig_status, use_container_width=True, key=f"{key_prefix}_chart_status")

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
