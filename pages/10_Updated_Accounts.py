"""
Updated Accounts Dashboard
Displays FB account inventory from the UPDATED ACCOUNTS tab:
  Group 1: Personal FB Accounts
  Group 2: Company Accounts
  Group 3: BM Record
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
    .kpi-card {
        background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
        color: white; padding: 20px; border-radius: 12px; text-align: center;
    }
    .kpi-card h2 { margin: 0; font-size: 2rem; }
    .kpi-card p { margin: 4px 0 0 0; opacity: 0.8; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


def render_kpi_cards(group1_df, group2_df):
    """Render KPI summary cards for Groups 1 and 2."""
    st.markdown('<div class="section-header"><h3>📊 ACCOUNT OVERVIEW</h3></div>', unsafe_allow_html=True)

    def count_status(df, status_col='Status'):
        if df.empty or status_col not in df.columns:
            return 0, 0, 0
        total = len(df)
        active = len(df[df[status_col].str.upper().isin(['ACTIVE', 'ALIVE', 'OK', 'GOOD'])])
        disabled = len(df[df[status_col].str.upper().isin(['DISABLED', 'BANNED', 'DEAD', 'LOCKED', 'RESTRICTED'])])
        return total, active, disabled

    g1_total, g1_active, g1_disabled = count_status(group1_df)
    g2_total, g2_active, g2_disabled = count_status(group2_df)

    combined_total = g1_total + g2_total
    combined_active = g1_active + g2_active
    combined_disabled = g1_disabled + g2_disabled
    active_pct = (combined_active / combined_total * 100) if combined_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Accounts", f"{combined_total:,}")
    with col2:
        st.metric("Active", f"{combined_active:,}")
    with col3:
        st.metric("Disabled", f"{combined_disabled:,}")
    with col4:
        st.metric("Active %", f"{active_pct:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Personal FB (Group 1)", f"{g1_total:,}",
                   delta=f"{g1_active} active")
    with col2:
        st.metric("Company Accounts (Group 2)", f"{g2_total:,}",
                   delta=f"{g2_active} active")


def render_status_charts(group1_df, group2_df):
    """Render per-employee stacked bar and status pie charts."""
    st.markdown('<div class="section-header"><h3>📈 STATUS BREAKDOWN</h3></div>', unsafe_allow_html=True)

    def get_status_category(status_val):
        s = str(status_val).strip().upper()
        if s in ('ACTIVE', 'ALIVE', 'OK', 'GOOD'):
            return 'Active'
        elif s in ('DISABLED', 'BANNED', 'DEAD', 'LOCKED', 'RESTRICTED'):
            return 'Disabled'
        elif s == '' or s == 'NAN':
            return 'Unknown'
        else:
            return 'Other'

    # --- Per-Employee Stacked Bar (Group 1) ---
    col1, col2 = st.columns(2)

    with col1:
        if not group1_df.empty and 'Status' in group1_df.columns:
            df = group1_df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            emp_status = df.groupby(['Employee', 'Status Category']).size().reset_index(name='Count')

            fig = px.bar(emp_status, x='Employee', y='Count', color='Status Category',
                         barmode='stack', title='Personal FB Accounts by Employee',
                         color_discrete_map={'Active': '#2ecc71', 'Disabled': '#e74c3c',
                                             'Other': '#f39c12', 'Unknown': '#95a5a6'})
            fig.update_layout(height=400, xaxis_title="", yaxis_title="Accounts",
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No Group 1 status data")

    with col2:
        if not group2_df.empty and 'Status' in group2_df.columns:
            df = group2_df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            emp_status = df.groupby(['Employee', 'Status Category']).size().reset_index(name='Count')

            fig = px.bar(emp_status, x='Employee', y='Count', color='Status Category',
                         barmode='stack', title='Company Accounts by Employee',
                         color_discrete_map={'Active': '#2ecc71', 'Disabled': '#e74c3c',
                                             'Other': '#f39c12', 'Unknown': '#95a5a6'})
            fig.update_layout(height=400, xaxis_title="", yaxis_title="Accounts",
                              legend=dict(orientation="h", yanchor="bottom", y=-0.3))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No Group 2 status data")

    # --- Status Distribution Pie Charts ---
    col1, col2 = st.columns(2)

    with col1:
        if not group1_df.empty and 'Status' in group1_df.columns:
            df = group1_df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            counts = df['Status Category'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=counts.index, values=counts.values, hole=0.3,
                marker_colors=['#2ecc71' if l == 'Active' else '#e74c3c' if l == 'Disabled'
                               else '#f39c12' if l == 'Other' else '#95a5a6' for l in counts.index],
            )])
            fig.update_layout(title=dict(text='Personal FB Status Distribution', x=0.5, xanchor='center'),
                              height=350, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not group2_df.empty and 'Status' in group2_df.columns:
            df = group2_df.copy()
            df['Status Category'] = df['Status'].apply(get_status_category)
            counts = df['Status Category'].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=counts.index, values=counts.values, hole=0.3,
                marker_colors=['#2ecc71' if l == 'Active' else '#e74c3c' if l == 'Disabled'
                               else '#f39c12' if l == 'Other' else '#95a5a6' for l in counts.index],
            )])
            fig.update_layout(title=dict(text='Company Acct Status Distribution', x=0.5, xanchor='center'),
                              height=350, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
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

    # Load data
    with st.spinner("Loading Updated Accounts data..."):
        data = load_updated_accounts_data()
        group1_df = data.get('group1', pd.DataFrame())
        group2_df = data.get('group2', pd.DataFrame())
        group3_df = data.get('group3', pd.DataFrame())

    if group1_df.empty and group2_df.empty and group3_df.empty:
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

        # Group filter
        st.subheader("📋 Group Filter")
        group_options = [
            "All",
            "Group 1: Personal FB",
            "Group 2: Company",
            "Group 3: BM Record",
        ]
        selected_group = st.selectbox("Group", group_options)

    show_g1 = selected_group in ("All", "Group 1: Personal FB")
    show_g2 = selected_group in ("All", "Group 2: Company")
    show_g3 = selected_group in ("All", "Group 3: BM Record")

    # Apply group filter to dataframes passed to all sections
    filtered_g1 = group1_df if show_g1 else pd.DataFrame()
    filtered_g2 = group2_df if show_g2 else pd.DataFrame()

    # --- Render Sections ---
    render_kpi_cards(filtered_g1, filtered_g2)

    st.divider()
    render_status_charts(filtered_g1, filtered_g2)

    if show_g1:
        st.divider()
        render_data_table(group1_df, "📱 Group 1: Personal FB Accounts", "g1")

    if show_g2:
        st.divider()
        render_data_table(group2_df, "🏢 Group 2: Company Accounts", "g2")

    if show_g3:
        st.divider()
        render_data_table(group3_df, "🔗 Group 3: BM Record", "g3")

    st.caption("Updated Accounts | Data from UPDATED ACCOUNTS tab")


if __name__ == "__main__":
    main()
