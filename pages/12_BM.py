"""
Business Manager - BM Created + BM Record (PWA Links)
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
        bm_created_df = data.get('bm_created', pd.DataFrame())
        bm_record_df = data.get('bm_record', pd.DataFrame())

    if bm_created_df.empty and bm_record_df.empty:
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
        st.subheader("📋 Section")
        section = st.selectbox("View", ["All", "BM Created", "BM Record"])

    show_created = section in ("All", "BM Created")
    show_record = section in ("All", "BM Record")

    # KPIs
    st.markdown('<div class="section-header"><h3>📊 BM OVERVIEW</h3></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("BM Created", f"{len(bm_created_df):,}")
    c2.metric("BM Records (PWA)", f"{len(bm_record_df):,}")

    # BM Created section
    if show_created and not bm_created_df.empty:
        st.divider()
        st.markdown('<div class="section-header"><h3>🏗️ BM CREATED</h3></div>', unsafe_allow_html=True)

        # Per employee chart
        emp_counts = bm_created_df['Employee'].value_counts().reset_index()
        emp_counts.columns = ['Employee', 'BMs']
        fig = px.bar(emp_counts.sort_values('BMs', ascending=True),
                     x='BMs', y='Employee', orientation='h',
                     title='BMs per Employee', text='BMs')
        fig.update_traces(textposition='inside')
        fig.update_layout(height=350, xaxis_title="Number of BMs", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        # Table
        search = st.text_input("Search BM Created", key="bm_created_search",
                               placeholder="Type to search...")
        display = bm_created_df[bm_created_df.apply(
            lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1
        )] if search else bm_created_df
        st.dataframe(display, use_container_width=True, hide_index=True, height=400)
        st.caption(f"Showing {len(display)} of {len(bm_created_df)} rows")

    # BM Record section
    if show_record and not bm_record_df.empty:
        st.divider()
        st.markdown('<div class="section-header"><h3>🔗 BM RECORD (PWA Links)</h3></div>', unsafe_allow_html=True)

        # Table
        search2 = st.text_input("Search BM Record", key="bm_record_search",
                                placeholder="Type to search...")
        display2 = bm_record_df[bm_record_df.apply(
            lambda row: row.astype(str).str.contains(search2, case=False).any(), axis=1
        )] if search2 else bm_record_df
        st.dataframe(display2, use_container_width=True, hide_index=True, height=500)
        st.caption(f"Showing {len(display2)} of {len(bm_record_df)} rows")

    st.caption("Business Manager | Data from UPDATED ACCOUNTS tab")


if __name__ == "__main__":
    main()
