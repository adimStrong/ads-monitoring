"""
Channel ROI - Roll Back
Shows Facebook and Google Roll Back performance comparison
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_fb_channel_data, load_google_channel_data, refresh_channel_data
from config import CHANNEL_ROI_ENABLED

_PAGE_CSS = """
<style>
    .fb-card {
        background: linear-gradient(135deg, #1877f2 0%, #42a5f5 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .google-card {
        background: linear-gradient(135deg, #fbbc05 0%, #f9a825 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .section-header {
        background: linear-gradient(135deg, #fbbc05 0%, #f9a825 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
"""


def format_currency(value):
    if pd.isna(value) or value == 0:
        return "$0.00"
    return f"${value:,.2f}"


def format_number(value):
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"


def render_content(fb_df, google_df, show_fb, show_google, date_from, date_to, key_prefix="rb"):
    """Render Roll Back content. Can be called standalone or from a wrapper page."""
    # Summary
    st.markdown('<div class="section-header"><h3>🔄 ROLL BACK SUMMARY</h3></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if show_fb:
            fb_totals = {
                'cost': fb_df['cost'].sum(),
                'register': fb_df['register'].sum(),
                'ftd': fb_df['ftd'].sum(),
            }
            fb_totals['cpr'] = fb_totals['cost'] / fb_totals['register'] if fb_totals['register'] > 0 else 0
            fb_totals['cost_ftd'] = fb_totals['cost'] / fb_totals['ftd'] if fb_totals['ftd'] > 0 else 0
            fb_totals['conv_rate'] = (fb_totals['ftd'] / fb_totals['register'] * 100) if fb_totals['register'] > 0 else 0

            st.markdown(f"""
            <div class="fb-card">
                <h2>📘 FACEBOOK</h2>
                <hr style="border-color: rgba(255,255,255,0.3);">
                <p><strong>Cost:</strong> {format_currency(fb_totals['cost'])}</p>
                <p><strong>Register:</strong> {format_number(fb_totals['register'])}</p>
                <p><strong>FTD:</strong> {format_number(fb_totals['ftd'])}</p>
                <p><strong>CPR:</strong> {format_currency(fb_totals['cpr'])}</p>
                <p><strong>Cost/FTD:</strong> {format_currency(fb_totals['cost_ftd'])}</p>
                <p><strong>Conv Rate:</strong> {fb_totals['conv_rate']:.2f}%</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No Facebook Roll Back data")

    with col2:
        if show_google:
            g_totals = {
                'cost': google_df['cost'].sum(),
                'register': google_df['register'].sum(),
                'ftd': google_df['ftd'].sum(),
            }
            g_totals['cpr'] = g_totals['cost'] / g_totals['register'] if g_totals['register'] > 0 else 0
            g_totals['cost_ftd'] = g_totals['cost'] / g_totals['ftd'] if g_totals['ftd'] > 0 else 0
            g_totals['conv_rate'] = (g_totals['ftd'] / g_totals['register'] * 100) if g_totals['register'] > 0 else 0

            st.markdown(f"""
            <div class="google-card">
                <h2>🔍 GOOGLE</h2>
                <hr style="border-color: rgba(255,255,255,0.3);">
                <p><strong>Cost:</strong> {format_currency(g_totals['cost'])}</p>
                <p><strong>Register:</strong> {format_number(g_totals['register'])}</p>
                <p><strong>FTD:</strong> {format_number(g_totals['ftd'])}</p>
                <p><strong>CPR:</strong> {format_currency(g_totals['cpr'])}</p>
                <p><strong>Cost/FTD:</strong> {format_currency(g_totals['cost_ftd'])}</p>
                <p><strong>Conv Rate:</strong> {g_totals['conv_rate']:.2f}%</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No Google Roll Back data")

    st.markdown("---")

    # Daily trend
    st.markdown('<div class="section-header"><h3>📅 DAILY TREND</h3></div>', unsafe_allow_html=True)

    chart_data = []
    if show_fb:
        fb_daily = fb_df.groupby(fb_df['date'].dt.date).agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index()
        fb_daily['channel'] = 'Facebook'
        fb_daily.columns = ['date', 'cost', 'ftd', 'register', 'channel']
        chart_data.append(fb_daily)

    if show_google:
        g_daily = google_df.groupby(google_df['date'].dt.date).agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index()
        g_daily['channel'] = 'Google'
        g_daily.columns = ['date', 'cost', 'ftd', 'register', 'channel']
        chart_data.append(g_daily)

    if chart_data:
        combined = pd.concat(chart_data, ignore_index=True)
        combined['cpr'] = combined.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
        combined['cost_ftd'] = combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)
        combined['conv_rate'] = combined.apply(lambda x: x['ftd'] / x['register'] * 100 if x['register'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.line(combined, x='date', y='cost', color='channel', markers=True, title='Daily Cost',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.line(combined, x='date', y='register', color='channel', markers=True, title='Daily Register',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.line(combined, x='date', y='ftd', color='channel', markers=True, title='Daily FTD',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.line(combined, x='date', y='cpr', color='channel', markers=True, title='Daily CPR',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.line(combined, x='date', y='cost_ftd', color='channel', markers=True, title='Daily Cost/FTD',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.line(combined, x='date', y='conv_rate', color='channel', markers=True, title='Daily Conversion Rate (FTD/Register)',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Weekly Summary
    st.markdown('<div class="section-header"><h3>📆 WEEKLY SUMMARY</h3></div>', unsafe_allow_html=True)

    weekly_data = []
    if show_fb:
        fb_w = fb_df.copy()
        fb_w['week'] = fb_w['date'].dt.isocalendar().week
        fb_w['year'] = fb_w['date'].dt.isocalendar().year
        fb_w['week_sort'] = fb_w.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)
        fb_w['week_start'] = fb_w.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 1), axis=1)
        fb_w['week_end'] = fb_w.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 7), axis=1)
        fb_w['week_label'] = fb_w.apply(lambda x: f"{x['week_start'].strftime('%b %d')} - {x['week_end'].strftime('%b %d')}", axis=1)
        fb_weekly = fb_w.groupby(['week_sort', 'week_label']).agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index().sort_values('week_sort')
        fb_weekly['channel'] = 'Facebook'
        weekly_data.append(fb_weekly)

    if show_google:
        g_w = google_df.copy()
        g_w['week'] = g_w['date'].dt.isocalendar().week
        g_w['year'] = g_w['date'].dt.isocalendar().year
        g_w['week_sort'] = g_w.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)
        g_w['week_start'] = g_w.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 1), axis=1)
        g_w['week_end'] = g_w.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 7), axis=1)
        g_w['week_label'] = g_w.apply(lambda x: f"{x['week_start'].strftime('%b %d')} - {x['week_end'].strftime('%b %d')}", axis=1)
        g_weekly = g_w.groupby(['week_sort', 'week_label']).agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index().sort_values('week_sort')
        g_weekly['channel'] = 'Google'
        weekly_data.append(g_weekly)

    if weekly_data:
        weekly_combined = pd.concat(weekly_data, ignore_index=True).sort_values('week_sort')
        weekly_combined['cpr'] = weekly_combined.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
        weekly_combined['cost_ftd'] = weekly_combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)
        weekly_combined['conv_rate'] = weekly_combined.apply(lambda x: x['ftd'] / x['register'] * 100 if x['register'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(weekly_combined, x='week_label', y='cost', color='channel', barmode='group', title='Weekly Cost',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(weekly_combined, x='week_label', y='register', color='channel', barmode='group', title='Weekly Register',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(weekly_combined, x='week_label', y='ftd', color='channel', barmode='group', title='Weekly FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(weekly_combined, x='week_label', y='cpr', color='channel', barmode='group', title='Weekly CPR',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(weekly_combined, x='week_label', y='cost_ftd', color='channel', barmode='group', title='Weekly Cost/FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(weekly_combined, x='week_label', y='conv_rate', color='channel', barmode='group', title='Weekly Conversion Rate',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Monthly Summary
    st.markdown('<div class="section-header"><h3>📊 MONTHLY SUMMARY</h3></div>', unsafe_allow_html=True)

    monthly_data = []
    if show_fb:
        fb_m = fb_df.copy()
        fb_m['month'] = fb_m['date'].dt.to_period('M').astype(str)
        fb_monthly = fb_m.groupby('month').agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index()
        fb_monthly['channel'] = 'Facebook'
        monthly_data.append(fb_monthly)

    if show_google:
        g_m = google_df.copy()
        g_m['month'] = g_m['date'].dt.to_period('M').astype(str)
        g_monthly = g_m.groupby('month').agg({'cost': 'sum', 'ftd': 'sum', 'register': 'sum'}).reset_index()
        g_monthly['channel'] = 'Google'
        monthly_data.append(g_monthly)

    if monthly_data:
        monthly_combined = pd.concat(monthly_data, ignore_index=True).sort_values('month')
        monthly_combined['cpr'] = monthly_combined.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
        monthly_combined['cost_ftd'] = monthly_combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)
        monthly_combined['conv_rate'] = monthly_combined.apply(lambda x: x['ftd'] / x['register'] * 100 if x['register'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(monthly_combined, x='month', y='cost', color='channel', barmode='group', title='Monthly Cost',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(monthly_combined, x='month', y='register', color='channel', barmode='group', title='Monthly Register',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(monthly_combined, x='month', y='ftd', color='channel', barmode='group', title='Monthly FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(monthly_combined, x='month', y='cpr', color='channel', barmode='group', title='Monthly CPR',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(monthly_combined, x='month', y='cost_ftd', color='channel', barmode='group', title='Monthly Cost/FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(monthly_combined, x='month', y='conv_rate', color='channel', barmode='group', title='Monthly Conversion Rate',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#fbbc05'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Data tables
    st.markdown('<div class="section-header"><h3>📋 DETAILED DATA</h3></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📘 Facebook Data", "🔍 Google Data"])

    with tab1:
        if show_fb:
            display_df = fb_df[['date', 'register', 'ftd', 'ftd_recharge', 'cost', 'cpr', 'roas']].copy()
            display_df['conv_rate'] = display_df.apply(lambda x: round(x['ftd'] / x['register'] * 100, 2) if x['register'] > 0 else 0, axis=1)
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df = display_df.sort_values('date', ascending=False)
            display_df.columns = ['Date', 'Register', 'FTD', 'Recharge (PHP)', 'Cost (USD)', 'CPR', 'ROAS', 'Conv Rate %']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.download_button("📥 Download FB CSV", display_df.to_csv(index=False), f"fb_roll_back_{datetime.now():%Y%m%d}.csv", key=f"{key_prefix}_dl_fb")
        else:
            st.info("No Facebook data available")

    with tab2:
        if show_google:
            display_df = google_df[['date', 'register', 'ftd', 'ftd_recharge', 'cost', 'cpr', 'roas']].copy()
            display_df['conv_rate'] = display_df.apply(lambda x: round(x['ftd'] / x['register'] * 100, 2) if x['register'] > 0 else 0, axis=1)
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df = display_df.sort_values('date', ascending=False)
            display_df.columns = ['Date', 'Register', 'FTD', 'Recharge (PHP)', 'Cost (USD)', 'CPR', 'ROAS', 'Conv Rate %']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.download_button("📥 Download Google CSV", display_df.to_csv(index=False), f"google_roll_back_{datetime.now():%Y%m%d}.csv", key=f"{key_prefix}_dl_g")
        else:
            st.info("No Google data available")

    st.caption(f"Roll Back Dashboard | {date_from} to {date_to}")


def main():
    st.set_page_config(page_title="Roll Back", page_icon="🔄", layout="wide")
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.title("🔄 Roll Back Dashboard")
    st.markdown("Facebook vs Google - Roll Back Performance Comparison")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    with st.spinner("Loading data..."):
        fb_data = load_fb_channel_data()
        google_data = load_google_channel_data()
        fb_df = fb_data.get('roll_back', pd.DataFrame())
        google_df = google_data.get('roll_back', pd.DataFrame())

    has_fb = not fb_df.empty
    has_google = not google_df.empty

    if not has_fb and not has_google:
        st.error("No Roll Back data available.")
        return

    all_dates = []
    if has_fb:
        fb_df['date'] = pd.to_datetime(fb_df['date'])
        all_dates.extend(fb_df['date'].tolist())
    if has_google:
        google_df['date'] = pd.to_datetime(google_df['date'])
        all_dates.extend(google_df['date'].tolist())

    data_min_date = min(all_dates).date()
    data_max_date = max(all_dates).date()
    yesterday = datetime.now().date() - timedelta(days=1)
    max_selectable_date = min(data_max_date, yesterday)

    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            refresh_channel_data()
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.subheader("📅 Date Range")
        default_start = max(data_min_date, max_selectable_date - timedelta(days=30))
        date_from = st.date_input("From", value=default_start, min_value=data_min_date, max_value=max_selectable_date)
        date_to = st.date_input("To", value=max_selectable_date, min_value=data_min_date, max_value=max_selectable_date)
        st.markdown("---")
        st.subheader("Channel Filter")
        channel_filter = st.selectbox("Select Channel", ["All", "Facebook", "Google"])

    if has_fb:
        fb_df = fb_df[(fb_df['date'].dt.date >= date_from) & (fb_df['date'].dt.date <= date_to)]
    if has_google:
        google_df = google_df[(google_df['date'].dt.date >= date_from) & (google_df['date'].dt.date <= date_to)]

    show_fb = channel_filter in ["All", "Facebook"] and has_fb and not fb_df.empty
    show_google = channel_filter in ["All", "Google"] and has_google and not google_df.empty

    if not show_fb and not show_google:
        st.warning("No data in selected date range or channel.")
        return

    render_content(fb_df, google_df, show_fb, show_google, date_from, date_to)


# Run when accessed as a Streamlit page (not when imported)
if not hasattr(st, '_is_recharge_import'):
    main()
