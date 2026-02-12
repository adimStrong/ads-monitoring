"""
Business Manager - BM inventory
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_updated_accounts_data, refresh_updated_accounts_data

st.set_page_config(page_title="Business Manager", page_icon="🏗️", layout="wide")

st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.title("🏗️ Business Manager")

    with st.spinner("Loading data..."):
        data = load_updated_accounts_data()
        bm_df = data.get('bm', pd.DataFrame())

    if bm_df.empty:
        st.warning("No BM data available.")
        return

    # Sidebar
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_updated_accounts_data()
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.subheader("👤 Employee Filter")
        employees = sorted(bm_df['Employee'].unique())
        selected = st.selectbox("Employee", ["All"] + employees)

    if selected != "All":
        bm_df = bm_df[bm_df['Employee'] == selected]

    # KPIs
    st.markdown('<div class="section-header"><h3>📊 BM OVERVIEW</h3></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total BMs", f"{len(bm_df):,}")
    c2.metric("Employees with BMs", f"{bm_df['Employee'].nunique():,}")

    # BMs per employee bar chart
    st.divider()
    st.markdown('<div class="section-header"><h3>📈 BMs PER EMPLOYEE</h3></div>', unsafe_allow_html=True)
    emp_counts = bm_df['Employee'].value_counts().reset_index()
    emp_counts.columns = ['Employee', 'BMs']
    fig = px.bar(emp_counts.sort_values('BMs', ascending=True),
                 x='BMs', y='Employee', orientation='h',
                 title='BMs per Employee', text='BMs')
    fig.update_traces(textposition='inside')
    fig.update_layout(height=400, xaxis_title="Number of BMs", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.divider()
    st.markdown('<div class="section-header"><h3>📋 ALL BMs</h3></div>', unsafe_allow_html=True)
    search = st.text_input("Search", placeholder="Type to search...")
    display_df = bm_df[bm_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)] if search else bm_df
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)
    st.caption(f"Showing {len(display_df)} of {len(bm_df)} BMs")


if __name__ == "__main__":
    main()
