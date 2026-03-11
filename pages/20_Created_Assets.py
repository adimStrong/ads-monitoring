"""
Created Assets - Gmail, FB Accounts, Pages & BMs inventory
Data from Created Assets tab in Channel ROI sheet.
Excludes disabled/inactive assets by default.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import (
    load_created_assets_data, refresh_created_assets_data,
    count_created_assets, count_assets_by_condition,
)
from config import SIDEBAR_HIDE_CSS

_PAGE_CSS = """
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
"""

DISABLED_KEYS = {'DISABLED', 'RESTRICTED', 'FOR VERIFY', 'SUSPENDED', 'CHECKPOINT', 'INACTIVE'}


def _count_items(val):
    """Count non-empty, non-separator items in a cell (may have newlines)."""
    if not val:
        return 0
    return len([v for v in val.split('\n') if v.strip() and v.strip() != '----'])


def _exclude_disabled(df):
    """Remove rows where ALL asset conditions are disabled/inactive."""
    def _is_disabled(cond):
        return str(cond).strip().upper() in DISABLED_KEYS

    mask = pd.Series(True, index=df.index)
    for cond_col in ['fb_condition', 'page_condition', 'bm_condition']:
        if cond_col in df.columns:
            mask = mask  # keep row if ANY asset is not disabled
    return df


def render_content(key_prefix="ca"):
    """Render Created Assets content. Can be called standalone or from Operations wrapper."""

    with st.spinner("Loading data..."):
        assets_df = load_created_assets_data()

    if assets_df.empty:
        st.error("No Created Assets data available.")
        return

    # Parse dates for filtering
    assets_df['date_parsed'] = pd.to_datetime(assets_df['date'], errors='coerce')

    # ── Filters ──
    fc1, fc2, fc3, fc4 = st.columns([1.5, 1.5, 2, 2])

    has_dates = assets_df['date_parsed'].notna().any()
    if has_dates:
        min_date = assets_df['date_parsed'].min().date()
        max_date = max(assets_df['date_parsed'].max().date(), datetime.now().date())
        default_start = max(min_date, max_date - timedelta(days=30))

        with fc1:
            start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date, key=f"{key_prefix}_from")
        with fc2:
            end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key=f"{key_prefix}_to")
    else:
        start_date = None
        end_date = None

    with fc3:
        ca_creators = set(assets_df['creator'].str.strip().unique())
        creators = sorted(ca_creators)
        selected = st.multiselect("Creator", creators, default=creators, key=f"{key_prefix}_creator")

    ALL_ASSET_TYPES = ['Gmail/Outlook', 'FB Accounts', 'FB Pages', 'Business Managers']
    ASSET_TYPE_MAP = {'Gmail/Outlook': 'gmail', 'FB Accounts': 'fb_accounts', 'FB Pages': 'fb_pages', 'Business Managers': 'bms'}
    with fc4:
        selected_types = st.multiselect("Asset Type", ALL_ASSET_TYPES, default=ALL_ASSET_TYPES, key=f"{key_prefix}_types")
    active_type_keys = {ASSET_TYPE_MAP[t] for t in selected_types}

    filtered = assets_df.copy()

    # Apply date filter
    if has_dates and start_date and end_date:
        filtered = filtered[
            (filtered['date_parsed'].notna()) &
            (filtered['date_parsed'].dt.date >= start_date) &
            (filtered['date_parsed'].dt.date <= end_date)
        ]

    if selected:
        filtered = filtered[filtered['creator'].str.strip().isin(selected)]
    else:
        st.warning("No creators selected.")
        return

    # ── Count active assets per creator (exclude disabled/inactive) ──
    def count_active_per_creator(df):
        """Count only ACTIVE assets per creator, excluding disabled/inactive."""
        result = {}
        for _, row in df.iterrows():
            creator = str(row.get('creator', '')).strip().upper()
            if not creator:
                continue
            if creator not in result:
                result[creator] = {'gmail': 0, 'fb_accounts': 0, 'fb_pages': 0, 'bms': 0, 'total': 0}

            fb_cond = str(row.get('fb_condition', '')).strip().upper()
            page_cond = str(row.get('page_condition', '')).strip().upper()
            bm_cond = str(row.get('bm_condition', '')).strip().upper()

            # Gmail — count if FB account condition is not disabled (gmail shares row with FB)
            gmail_val = str(row.get('gmail', '')).strip()
            if gmail_val and gmail_val != '----' and fb_cond not in DISABLED_KEYS:
                n = _count_items(gmail_val)
                result[creator]['gmail'] += n
                result[creator]['total'] += n

            # FB Accounts
            fb_val = str(row.get('fb_username', '')).strip()
            if fb_val and fb_val != '----' and fb_cond not in DISABLED_KEYS:
                n = _count_items(fb_val)
                result[creator]['fb_accounts'] += n
                result[creator]['total'] += n

            # FB Pages
            page_val = str(row.get('fb_page', '')).strip()
            if page_val and page_val != '----' and page_cond not in DISABLED_KEYS:
                n = _count_items(page_val)
                result[creator]['fb_pages'] += n
                result[creator]['total'] += n

            # BMs
            bm_val = str(row.get('bm_name', '')).strip()
            if bm_val and bm_val != '----' and bm_cond not in DISABLED_KEYS:
                n = _count_items(bm_val)
                result[creator]['bms'] += n
                result[creator]['total'] += n

        return result

    def count_all_per_creator(df):
        """Count ALL assets per creator (including disabled) for comparison."""
        result = {}
        for _, row in df.iterrows():
            creator = str(row.get('creator', '')).strip().upper()
            if not creator:
                continue
            if creator not in result:
                result[creator] = {'gmail': 0, 'fb_accounts': 0, 'fb_pages': 0, 'bms': 0, 'total': 0}

            gmail_val = str(row.get('gmail', '')).strip()
            if gmail_val and gmail_val != '----':
                n = _count_items(gmail_val)
                result[creator]['gmail'] += n
                result[creator]['total'] += n

            fb_val = str(row.get('fb_username', '')).strip()
            if fb_val and fb_val != '----':
                n = _count_items(fb_val)
                result[creator]['fb_accounts'] += n
                result[creator]['total'] += n

            page_val = str(row.get('fb_page', '')).strip()
            if page_val and page_val != '----':
                n = _count_items(page_val)
                result[creator]['fb_pages'] += n
                result[creator]['total'] += n

            bm_val = str(row.get('bm_name', '')).strip()
            if bm_val and bm_val != '----':
                n = _count_items(bm_val)
                result[creator]['bms'] += n
                result[creator]['total'] += n

        return result

    active_counts = count_active_per_creator(filtered)
    all_counts = count_all_per_creator(filtered)

    # ── KPI Cards (active only) ──
    period_label = ""
    if has_dates and start_date and end_date:
        period_label = f" ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"

    st.markdown(f'<div class="section-header"><h3>ACTIVE ASSETS{period_label}</h3><p style="margin:0;font-size:13px;opacity:0.8">Excluding disabled/inactive/restricted accounts</p></div>', unsafe_allow_html=True)

    total_gmail = sum(v['gmail'] for v in active_counts.values()) if 'gmail' in active_type_keys else 0
    total_fb = sum(v['fb_accounts'] for v in active_counts.values()) if 'fb_accounts' in active_type_keys else 0
    total_pages = sum(v['fb_pages'] for v in active_counts.values()) if 'fb_pages' in active_type_keys else 0
    total_bms = sum(v['bms'] for v in active_counts.values()) if 'bms' in active_type_keys else 0
    total_active = total_gmail + total_fb + total_pages + total_bms

    # All counts for comparison
    all_gmail = sum(v['gmail'] for v in all_counts.values()) if 'gmail' in active_type_keys else 0
    all_fb = sum(v['fb_accounts'] for v in all_counts.values()) if 'fb_accounts' in active_type_keys else 0
    all_pages = sum(v['fb_pages'] for v in all_counts.values()) if 'fb_pages' in active_type_keys else 0
    all_bms = sum(v['bms'] for v in all_counts.values()) if 'bms' in active_type_keys else 0
    total_all = all_gmail + all_fb + all_pages + all_bms
    total_disabled = total_all - total_active

    kpi_items = [
        ("Active Assets", f"{total_active:,}", f"of {total_all:,} total"),
        ("Disabled/Inactive", f"{total_disabled:,}", f"{total_disabled / total_all * 100:.0f}%" if total_all > 0 else "0%"),
    ]
    if 'gmail' in active_type_keys:
        kpi_items.append(("Gmail/Outlook", f"{total_gmail:,}", f"of {all_gmail:,}"))
    if 'fb_accounts' in active_type_keys:
        kpi_items.append(("FB Accounts", f"{total_fb:,}", f"of {all_fb:,}"))
    if 'fb_pages' in active_type_keys:
        kpi_items.append(("FB Pages", f"{total_pages:,}", f"of {all_pages:,}"))
    if 'bms' in active_type_keys:
        kpi_items.append(("Business Managers", f"{total_bms:,}", f"of {all_bms:,}"))

    cols = st.columns(len(kpi_items))
    for i, (label, val, delta) in enumerate(kpi_items):
        cols[i].metric(label, val, delta)

    # ── Per Creator Summary Table ──
    st.divider()
    st.markdown(f'<div class="section-header"><h3>PER CREATOR BREAKDOWN{period_label}</h3></div>', unsafe_allow_html=True)

    summary_rows = []
    type_labels = {'gmail': 'Gmail', 'fb_accounts': 'FB Accounts', 'fb_pages': 'FB Pages', 'bms': 'BMs'}
    for creator in sorted(active_counts.keys()):
        ac = active_counts[creator]
        al = all_counts.get(creator, {})
        row = {'Creator': creator}
        grand_active = 0
        grand_all = 0
        for at_key in ['gmail', 'fb_accounts', 'fb_pages', 'bms']:
            if at_key not in active_type_keys:
                continue
            active_n = ac.get(at_key, 0)
            all_n = al.get(at_key, 0)
            disabled_n = all_n - active_n
            row[type_labels[at_key]] = active_n
            if disabled_n > 0:
                row[f'{type_labels[at_key]} (Disabled)'] = disabled_n
            grand_active += active_n
            grand_all += all_n
        row['Total Active'] = grand_active
        row['Total Created'] = grand_all
        row['Active %'] = f"{grand_active / grand_all * 100:.0f}%" if grand_all > 0 else "0%"
        summary_rows.append(row)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True, key=f"{key_prefix}_tbl_summary")

    # ── Stacked Bar Chart ──
    if active_counts:
        chart_rows = []
        for creator in sorted(active_counts.keys()):
            ac = active_counts[creator]
            for at_key in ['gmail', 'fb_accounts', 'fb_pages', 'bms']:
                if at_key not in active_type_keys:
                    continue
                chart_rows.append({
                    'Creator': creator,
                    'Type': type_labels[at_key],
                    'Count': ac.get(at_key, 0),
                })

        chart_df = pd.DataFrame(chart_rows)
        fig = px.bar(
            chart_df, x='Creator', y='Count', color='Type',
            barmode='stack', title='Active Assets per Creator',
            color_discrete_map={
                'Gmail': '#3b82f6', 'FB Accounts': '#22c55e',
                'FB Pages': '#f59e0b', 'BMs': '#a855f7',
            },
        )
        fig.update_layout(height=400, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_creators")

    # ── Condition Breakdown ──
    st.divider()
    st.markdown('<div class="section-header"><h3>CONDITION BREAKDOWN</h3></div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        fb_conds = filtered[filtered['fb_username'].str.strip() != '']['fb_condition'].str.strip().str.upper()
        fb_conds = fb_conds[fb_conds != '']
        if not fb_conds.empty:
            cond_counts = fb_conds.value_counts().reset_index()
            cond_counts.columns = ['Condition', 'Count']
            fig2 = px.pie(cond_counts, names='Condition', values='Count', title='FB Account Conditions')
            st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_pie_fb")

    with col_b:
        pg_conds = filtered[filtered['fb_page'].str.strip() != '']['page_condition'].str.strip().str.upper()
        pg_conds = pg_conds[pg_conds != '']
        if not pg_conds.empty:
            cond_counts = pg_conds.value_counts().reset_index()
            cond_counts.columns = ['Condition', 'Count']
            fig3 = px.pie(cond_counts, names='Condition', values='Count', title='Page Conditions')
            st.plotly_chart(fig3, use_container_width=True, key=f"{key_prefix}_pie_pages")

    bm_conds = filtered[filtered['bm_name'].str.strip() != '']['bm_condition'].str.strip().str.upper()
    bm_conds = bm_conds[bm_conds != '']
    if not bm_conds.empty:
        cond_counts = bm_conds.value_counts().reset_index()
        cond_counts.columns = ['Condition', 'Count']
        fig4 = px.pie(cond_counts, names='Condition', values='Count', title='BM Conditions')
        st.plotly_chart(fig4, use_container_width=True, key=f"{key_prefix}_pie_bm")

    # ── Raw Data ──
    st.divider()
    st.markdown('<div class="section-header"><h3>ALL RECORDS</h3></div>', unsafe_allow_html=True)

    display_cols = ['date', 'creator', 'gmail', 'fb_username', 'fb_condition', 'fb_page', 'page_condition', 'bm_name', 'bm_condition']
    display_df = filtered[display_cols].copy()
    display_df.columns = ['Date', 'Creator', 'Gmail/Outlook', 'FB Username', 'FB Condition', 'FB Page', 'Page Condition', 'BM Name', 'BM Condition']
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

    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_created_assets_data()
            st.rerun()

    render_content()


if not hasattr(st, '_is_recharge_import'):
    main()
