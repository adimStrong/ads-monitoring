"""
Updated Accounts - Account inventory
Personal FB, Company, Juanbingo, Own Created accounts
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


def count_status(df):
    if df.empty or 'Status' not in df.columns:
        return 0, 0, 0
    cats = df['Status'].apply(get_status_category)
    return len(df), (cats == 'Active').sum(), (cats == 'Disabled').sum()


def render_data_table(df, title, key_prefix):
    st.markdown(f'<div class="section-header"><h3>{title}</h3></div>', unsafe_allow_html=True)
    if df.empty:
        st.info(f"No data available")
        return
    search = st.text_input(f"Search", key=f"{key_prefix}_search",
                           placeholder="Type to search across all columns...")
    display_df = df[df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)] if search else df
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
    st.caption(f"Showing {len(display_df)} of {len(df)} rows")


def main():
    st.title("👤 Updated Accounts")

    with st.spinner("Loading data..."):
        data = load_updated_accounts_data()

    groups = {
        'personal_fb': ('Personal FB', data.get('personal_fb', pd.DataFrame())),
        'company': ('Company', data.get('company', pd.DataFrame())),
        'juanbingo': ('Juanbingo', data.get('juanbingo', pd.DataFrame())),
        'own_created': ('Own Created', data.get('own_created', pd.DataFrame())),
    }

    if all(df.empty for _, df in groups.values()):
        st.error("No account data available.")
        return

    # Sidebar
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_updated_accounts_data()
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.subheader("📋 Filter")
        options = ["All"] + [label for label, df in groups.values() if not df.empty]
        selected = st.selectbox("Group", options)

    # Filter
    show = {k: selected in ("All", label) for k, (label, _) in groups.items()}
    filtered = {k: df if show[k] else pd.DataFrame() for k, (_, df) in groups.items()}

    # KPI Cards
    st.markdown('<div class="section-header"><h3>📊 ACCOUNT OVERVIEW</h3></div>', unsafe_allow_html=True)
    totals = {'total': 0, 'active': 0, 'disabled': 0}
    group_stats = []
    for key, (label, _) in groups.items():
        df = filtered[key]
        t, a, d = count_status(df)
        totals['total'] += t
        totals['active'] += a
        totals['disabled'] += d
        if t > 0:
            group_stats.append((label, t, a))

    active_pct = (totals['active'] / totals['total'] * 100) if totals['total'] > 0 else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Accounts", f"{totals['total']:,}")
    c2.metric("Active", f"{totals['active']:,}")
    c3.metric("Disabled", f"{totals['disabled']:,}")
    c4.metric("Active %", f"{active_pct:.1f}%")

    if group_stats:
        cols = st.columns(len(group_stats))
        for col, (label, total, active) in zip(cols, group_stats):
            col.metric(label, f"{total:,}", delta=f"{active} active")

    # Status Charts
    st.divider()
    st.markdown('<div class="section-header"><h3>📈 STATUS BREAKDOWN</h3></div>', unsafe_allow_html=True)
    active_groups = [(k, l, filtered[k]) for k, (l, _) in groups.items()
                     if not filtered[k].empty and 'Status' in filtered[k].columns]

    # Stacked bars (2 per row)
    for i in range(0, len(active_groups), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j >= len(active_groups):
                break
            key, label, df = active_groups[i + j]
            df = df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            emp = df.groupby(['Employee', 'Status Category']).size().reset_index(name='Count')
            fig = px.bar(emp, x='Employee', y='Count', color='Status Category',
                         barmode='stack', title=f'{label} by Employee',
                         color_discrete_map=STATUS_COLORS)
            fig.update_layout(height=400, xaxis_title="", yaxis_title="Accounts",
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3))
            with cols[j]:
                st.plotly_chart(fig, use_container_width=True)

    # Pie charts (2 per row)
    for i in range(0, len(active_groups), 2):
        cols = st.columns(min(2, len(active_groups) - i))
        for j in range(len(cols)):
            if i + j >= len(active_groups):
                break
            key, label, df = active_groups[i + j]
            df = df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            counts = df['Status Category'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=counts.index, values=counts.values, hole=0.3,
                marker_colors=[STATUS_COLORS.get(l, '#95a5a6') for l in counts.index],
            )])
            fig.update_layout(title=dict(text=f'{label} Status', x=0.5, xanchor='center'),
                              height=350, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
            with cols[j]:
                st.plotly_chart(fig, use_container_width=True)

    # Data Tables
    icons = {'personal_fb': '📱', 'company': '🏢', 'juanbingo': '🎰', 'own_created': '🆕'}
    for key, (label, _) in groups.items():
        if show[key] and not filtered[key].empty:
            st.divider()
            render_data_table(filtered[key], f"{icons[key]} {label} Accounts", key)

    st.caption("Updated Accounts | Data from UPDATED ACCOUNTS tab")


if __name__ == "__main__":
    main()
