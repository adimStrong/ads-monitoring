"""
Updated Accounts - FB Account inventory
"""
import streamlit as st
import pandas as pd
import plotly.express as px
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


def main():
    st.title("👤 Updated Accounts")

    with st.spinner("Loading data..."):
        data = load_updated_accounts_data()

    fb_df = data.get('fb_accounts', pd.DataFrame())

    if fb_df.empty:
        st.error("No FB account data available.")
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
        employees = sorted(fb_df['Employee'].unique())
        selected = st.selectbox("Employee", ["All"] + employees)

    if selected != "All":
        fb_df = fb_df[fb_df['Employee'] == selected]

    # KPI Cards
    st.markdown('<div class="section-header"><h3>📊 FB ACCOUNTS OVERVIEW</h3></div>', unsafe_allow_html=True)
    total = len(fb_df)
    unique_employees = fb_df['Employee'].nunique()

    c1, c2 = st.columns(2)
    c1.metric("Total FB Accounts", f"{total:,}")
    c2.metric("Employees", f"{unique_employees:,}")

    # Accounts per employee bar chart
    st.divider()
    st.markdown('<div class="section-header"><h3>📈 ACCOUNTS PER EMPLOYEE</h3></div>', unsafe_allow_html=True)
    emp_counts = fb_df['Employee'].value_counts().reset_index()
    emp_counts.columns = ['Employee', 'Accounts']
    fig = px.bar(emp_counts.sort_values('Accounts', ascending=True),
                 x='Accounts', y='Employee', orientation='h',
                 title='FB Accounts per Employee', text='Accounts')
    fig.update_traces(textposition='inside')
    fig.update_layout(height=400, xaxis_title="Number of Accounts", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    # Data table
    st.divider()
    st.markdown('<div class="section-header"><h3>📋 FB ACCOUNTS</h3></div>', unsafe_allow_html=True)
    search = st.text_input("Search", placeholder="Type to search across all columns...")
    display_df = fb_df[fb_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)] if search else fb_df
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)
    st.caption(f"Showing {len(display_df)} of {len(fb_df)} accounts")


if __name__ == "__main__":
    main()
