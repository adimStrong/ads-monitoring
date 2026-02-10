"""
Updated Accounts Dashboard
Displays FB account inventory from the UPDATED ACCOUNTS tab:
  1. Personal FB Accounts (Col B)
  2. Company Account Details (Col L, section 1)
  3. Juanbingo Accounts (Col L, section 2)
  4. Own Created FB Accounts (Col L, section 3) - with Page Name & BM Name
  5. BM Record (Col Y)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_updated_accounts_data, refresh_updated_accounts_data

st.set_page_config(page_title="Updated Accounts", page_icon="👤", layout="wide")

st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)


STATUS_COLORS = {'Active': '#2ecc71', 'Disabled': '#e74c3c', 'Other': '#f39c12', 'Unknown': '#95a5a6'}


def get_status_category(status_val):
    s = str(status_val).strip().upper()
    if s in ('ACTIVE', 'ALIVE', 'OK', 'GOOD'):
        return 'Active'
    elif s in ('DISABLED', 'BANNED', 'DEAD', 'LOCKED', 'RESTRICTED'):
        return 'Disabled'
    elif s == '' or s == 'NAN':
        return 'Unknown'
    return 'Other'


def count_status(df, status_col='Status'):
    if df.empty or status_col not in df.columns:
        return 0, 0, 0
    total = len(df)
    cats = df[status_col].apply(get_status_category)
    active = (cats == 'Active').sum()
    disabled = (cats == 'Disabled').sum()
    return total, active, disabled


def render_kpi_cards(dfs):
    """Render KPI summary cards across all account DataFrames."""
    st.markdown('<div class="section-header"><h3>📊 ACCOUNT OVERVIEW</h3></div>', unsafe_allow_html=True)

    totals = {'total': 0, 'active': 0, 'disabled': 0}
    group_stats = []

    labels = {
        'personal_fb': 'Personal FB',
        'company': 'Company',
        'juanbingo': 'Juanbingo',
        'own_created': 'Own Created',
    }

    for key in ('personal_fb', 'company', 'juanbingo', 'own_created'):
        df = dfs.get(key, pd.DataFrame())
        t, a, d = count_status(df)
        totals['total'] += t
        totals['active'] += a
        totals['disabled'] += d
        if t > 0:
            group_stats.append((labels[key], t, a))

    active_pct = (totals['active'] / totals['total'] * 100) if totals['total'] > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Accounts", f"{totals['total']:,}")
    with col2:
        st.metric("Active", f"{totals['active']:,}")
    with col3:
        st.metric("Disabled", f"{totals['disabled']:,}")
    with col4:
        st.metric("Active %", f"{active_pct:.1f}%")

    # Per-group metrics
    cols = st.columns(len(group_stats)) if group_stats else []
    for col, (label, total, active) in zip(cols, group_stats):
        with col:
            st.metric(label, f"{total:,}", delta=f"{active} active")


def render_status_charts(dfs):
    """Render stacked bar + pie charts for account groups that have Status."""
    st.markdown('<div class="section-header"><h3>📈 STATUS BREAKDOWN</h3></div>', unsafe_allow_html=True)

    chart_groups = [
        ('personal_fb', 'Personal FB'),
        ('company', 'Company'),
        ('juanbingo', 'Juanbingo'),
        ('own_created', 'Own Created'),
    ]

    # Filter to groups with data
    active_groups = [(k, l) for k, l in chart_groups
                     if not dfs.get(k, pd.DataFrame()).empty
                     and 'Status' in dfs.get(k, pd.DataFrame()).columns]

    if not active_groups:
        st.info("No status data available")
        return

    # Stacked bar charts (2 per row)
    for i in range(0, len(active_groups), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(active_groups):
                break
            key, label = active_groups[idx]
            df = dfs[key].copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            emp_status = df.groupby(['Employee', 'Status Category']).size().reset_index(name='Count')

            fig = px.bar(emp_status, x='Employee', y='Count', color='Status Category',
                         barmode='stack', title=f'{label} by Employee',
                         color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=400, xaxis_title="", yaxis_title="Accounts",
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3))
            with col:
                st.plotly_chart(fig, use_container_width=True)

    # Pie charts (2 per row)
    cols = st.columns(min(len(active_groups), 2))
    for idx, (key, label) in enumerate(active_groups[:2]):
        df = dfs[key].copy()
        df['Status Category'] = df['Status'].apply(get_status_category)
        counts = df['Status Category'].value_counts()
        fig = go.Figure(data=[go.Pie(
            labels=counts.index, values=counts.values, hole=0.3,
            marker_colors=[STATUS_COLORS.get(l, '#95a5a6') for l in counts.index],
        )])
        fig.update_layout(title=dict(text=f'{label} Status', x=0.5, xanchor='center'),
                          height=350, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
        with cols[idx]:
            st.plotly_chart(fig, use_container_width=True)

    if len(active_groups) > 2:
        cols = st.columns(min(len(active_groups) - 2, 2))
        for idx, (key, label) in enumerate(active_groups[2:4]):
            df = dfs[key].copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            counts = df['Status Category'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=counts.index, values=counts.values, hole=0.3,
                marker_colors=[STATUS_COLORS.get(l, '#95a5a6') for l in counts.index],
            )])
            fig.update_layout(title=dict(text=f'{label} Status', x=0.5, xanchor='center'),
                              height=350, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
            with cols[idx]:
                st.plotly_chart(fig, use_container_width=True)


def render_data_table(df, title, key_prefix):
    """Render a filterable data table with search."""
    st.markdown(f'<div class="section-header"><h3>{title}</h3></div>', unsafe_allow_html=True)

    if df.empty:
        st.info(f"No data available for {title}")
        return

    search = st.text_input(f"Search {title}", key=f"{key_prefix}_search",
                           placeholder="Type to search across all columns...")
    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = df[mask]
    else:
        display_df = df

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
    st.caption(f"Showing {len(display_df)} of {len(df)} rows")


def main():
    st.title("👤 Updated Accounts")

    with st.spinner("Loading Updated Accounts data..."):
        data = load_updated_accounts_data()

    all_empty = all(data.get(k, pd.DataFrame()).empty
                    for k in ('personal_fb', 'company', 'juanbingo', 'own_created', 'bm_record'))
    if all_empty:
        st.error("No Updated Accounts data available.")
        st.info("Check that the 'UPDATED ACCOUNTS' tab exists in the Facebook Ads spreadsheet.")
        return

    # --- Sidebar ---
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_updated_accounts_data()
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")

        st.subheader("📋 Group Filter")
        group_options = [
            "All",
            "Personal FB",
            "Company",
            "Juanbingo",
            "Own Created",
            "BM Record",
        ]
        selected_group = st.selectbox("Group", group_options)

    show = {
        'personal_fb': selected_group in ("All", "Personal FB"),
        'company': selected_group in ("All", "Company"),
        'juanbingo': selected_group in ("All", "Juanbingo"),
        'own_created': selected_group in ("All", "Own Created"),
        'bm_record': selected_group in ("All", "BM Record"),
    }

    # Build filtered dict for KPI/charts (only shown groups)
    filtered = {k: data.get(k, pd.DataFrame()) if show[k] else pd.DataFrame()
                for k in ('personal_fb', 'company', 'juanbingo', 'own_created')}

    # --- Render Sections ---
    render_kpi_cards(filtered)

    st.divider()
    render_status_charts(filtered)

    if show['personal_fb']:
        st.divider()
        render_data_table(data['personal_fb'], "📱 Personal FB Accounts", "personal_fb")

    if show['company']:
        st.divider()
        render_data_table(data['company'], "🏢 Company Account Details", "company")

    if show['juanbingo']:
        st.divider()
        render_data_table(data['juanbingo'], "🎰 Juanbingo Accounts", "juanbingo")

    if show['own_created']:
        st.divider()
        render_data_table(data['own_created'], "🆕 Own Created FB Accounts", "own_created")

    if show['bm_record']:
        st.divider()
        render_data_table(data['bm_record'], "🔗 BM Record", "bm_record")

    st.caption("Updated Accounts | Data from UPDATED ACCOUNTS tab")


if __name__ == "__main__":
    main()
