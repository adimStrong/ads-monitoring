"""
Channel ROI - Violet
Shows Facebook and Google Violet performance comparison
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_fb_channel_data, load_google_channel_data, refresh_channel_data
from config import CHANNEL_ROI_ENABLED, SIDEBAR_HIDE_CSS

_PAGE_CSS = """
<style>
    .fb-card {
        background: linear-gradient(135deg, #1877f2 0%, #42a5f5 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .google-card {
        background: linear-gradient(135deg, #9c27b0 0%, #7b1fa2 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .section-header {
        background: linear-gradient(135deg, #9c27b0 0%, #7b1fa2 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
"""

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)


def format_currency(value):
    if pd.isna(value) or value == 0:
        return "$0.00"
    return f"${value:,.2f}"


def format_number(value):
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"


def render_content(fb_df, google_df, show_fb, show_google, date_from, date_to,
                    fb_rb_df=None, google_rb_df=None, key_prefix="vi"):
    """Render Violet content. Can be called standalone or from a wrapper page."""
    if fb_rb_df is None:
        fb_rb_df = pd.DataFrame()
    if google_rb_df is None:
        google_rb_df = pd.DataFrame()

    # Summary with 5 metrics (registration from Roll Back)
    st.markdown('<div class="section-header"><h3>💜 VIOLET SUMMARY</h3></div>', unsafe_allow_html=True)

    def calc_metrics(cost, ftd, ftd_recharge, register):
        return {
            'cost': cost,
            'ftd': ftd,
            'ftd_recharge': ftd_recharge,
            'register': register,
            'cost_reg': cost / register if register > 0 else 0,
            'cost_ftd': cost / ftd if ftd > 0 else 0,
            'arppu': ftd_recharge / ftd if ftd > 0 else 0,
            'roas': ((ftd_recharge / ftd) / 57.7 / (cost / ftd)) if ftd > 0 and cost > 0 else 0,
            'conv_rate': (ftd / register) * 100 if register > 0 else 0,
        }

    def render_card(title, emoji, css_class, m):
        return f"""
        <div class="{css_class}">
            <h2>{emoji} {title}</h2>
            <hr style="border-color: rgba(255,255,255,0.3);">
            <p><strong>Cost/Register:</strong> {format_currency(m['cost_reg'])}</p>
            <p><strong>Cost/FTD:</strong> {format_currency(m['cost_ftd'])}</p>
            <p><strong>ARPPU:</strong> ₱{m['arppu']:,.2f}</p>
            <p><strong>ROAS:</strong> {m['roas']:.2f}x</p>
            <p><strong>Conv Rate:</strong> {m['conv_rate']:.1f}%</p>
            <hr style="border-color: rgba(255,255,255,0.2);">
            <p style="font-size:0.85em; opacity:0.8;">Cost: {format_currency(m['cost'])} | FTD: {format_number(m['ftd'])} | Reg: {format_number(m['register'])}</p>
        </div>
        """

    col1, col2 = st.columns(2)

    with col1:
        if show_fb:
            fb_reg = fb_rb_df['register'].sum() if not fb_rb_df.empty and 'register' in fb_rb_df.columns else 0
            fb_m = calc_metrics(fb_df['cost'].sum(), fb_df['ftd'].sum(), fb_df['ftd_recharge'].sum(), fb_reg)
            st.markdown(render_card("FACEBOOK", "📘", "fb-card", fb_m), unsafe_allow_html=True)
        else:
            st.info("No Facebook Violet data")

    with col2:
        if show_google:
            g_reg = google_rb_df['register'].sum() if not google_rb_df.empty and 'register' in google_rb_df.columns else 0
            g_m = calc_metrics(google_df['cost'].sum(), google_df['ftd'].sum(), google_df['ftd_recharge'].sum(), g_reg)
            st.markdown(render_card("GOOGLE", "🔍", "google-card", g_m), unsafe_allow_html=True)
        else:
            st.info("No Google Violet data")

    st.markdown("---")

    # Daily trend
    st.markdown('<div class="section-header"><h3>📅 DAILY TREND</h3></div>', unsafe_allow_html=True)

    chart_data = []
    if show_fb:
        fb_daily = fb_df.groupby(fb_df['date'].dt.date).agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index()
        fb_daily['channel'] = 'Facebook'
        fb_daily.columns = ['date', 'cost', 'ftd', 'ftd_recharge', 'channel']
        chart_data.append(fb_daily)

    if show_google:
        g_daily = google_df.groupby(google_df['date'].dt.date).agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index()
        g_daily['channel'] = 'Google'
        g_daily.columns = ['date', 'cost', 'ftd', 'ftd_recharge', 'channel']
        chart_data.append(g_daily)

    if chart_data:
        combined = pd.concat(chart_data, ignore_index=True)
        combined['cost_ftd'] = combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.line(combined, x='date', y='cost', color='channel', markers=True, title='Daily Cost',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.line(combined, x='date', y='ftd', color='channel', markers=True, title='Daily First Recharge',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.line(combined, x='date', y='cost_ftd', color='channel', markers=True, title='Daily Cost/FTD',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
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
        fb_weekly = fb_w.groupby(['week_sort', 'week_label']).agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index().sort_values('week_sort')
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
        g_weekly = g_w.groupby(['week_sort', 'week_label']).agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index().sort_values('week_sort')
        g_weekly['channel'] = 'Google'
        weekly_data.append(g_weekly)

    if weekly_data:
        weekly_combined = pd.concat(weekly_data, ignore_index=True).sort_values('week_sort')
        weekly_combined['cost_ftd'] = weekly_combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(weekly_combined, x='week_label', y='cost', color='channel', barmode='group', title='Weekly Cost',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(weekly_combined, x='week_label', y='ftd', color='channel', barmode='group', title='Weekly First Recharge',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(weekly_combined, x='week_label', y='cost_ftd', color='channel', barmode='group', title='Weekly Cost/FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Monthly Summary
    st.markdown('<div class="section-header"><h3>📊 MONTHLY SUMMARY</h3></div>', unsafe_allow_html=True)

    monthly_data = []
    if show_fb:
        fb_m = fb_df.copy()
        fb_m['month'] = fb_m['date'].dt.to_period('M').astype(str)
        fb_monthly = fb_m.groupby('month').agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index()
        fb_monthly['channel'] = 'Facebook'
        monthly_data.append(fb_monthly)

    if show_google:
        g_m = google_df.copy()
        g_m['month'] = g_m['date'].dt.to_period('M').astype(str)
        g_monthly = g_m.groupby('month').agg({'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}).reset_index()
        g_monthly['channel'] = 'Google'
        monthly_data.append(g_monthly)

    if monthly_data:
        monthly_combined = pd.concat(monthly_data, ignore_index=True).sort_values('month')
        monthly_combined['cost_ftd'] = monthly_combined.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig = px.bar(monthly_combined, x='month', y='cost', color='channel', barmode='group', title='Monthly Cost',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(monthly_combined, x='month', y='ftd', color='channel', barmode='group', title='Monthly First Recharge',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = px.bar(monthly_combined, x='month', y='cost_ftd', color='channel', barmode='group', title='Monthly Cost/FTD',
                        color_discrete_map={'Facebook': '#1877f2', 'Google': '#9c27b0'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Data tables
    st.markdown('<div class="section-header"><h3>📋 DETAILED DATA</h3></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📘 Facebook Data", "🔍 Google Data"])

    with tab1:
        if show_fb:
            display_df = fb_df[['date', 'ftd', 'ftd_recharge', 'cost', 'cpr', 'roas']].copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df = display_df.sort_values('date', ascending=False)
            display_df.columns = ['Date', 'First Recharge', 'Recharge Amount', 'Cost (USD)', 'Cost/Recharge', 'ROAS']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.download_button("📥 Download FB CSV", display_df.to_csv(index=False), f"fb_violet_{datetime.now():%Y%m%d}.csv", key=f"{key_prefix}_dl_fb")
        else:
            st.info("No Facebook data available")

    with tab2:
        if show_google:
            display_df = google_df[['date', 'ftd', 'ftd_recharge', 'cost', 'cpr', 'roas']].copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            display_df = display_df.sort_values('date', ascending=False)
            display_df.columns = ['Date', 'First Recharge', 'Recharge Amount', 'Cost (USD)', 'Cost/Recharge', 'ROAS']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.download_button("📥 Download Google CSV", display_df.to_csv(index=False), f"google_violet_{datetime.now():%Y%m%d}.csv", key=f"{key_prefix}_dl_g")
        else:
            st.info("No Google data available")

    st.caption(f"Violet Dashboard | {date_from} to {date_to}")


def main():
    st.set_page_config(page_title="Violet", page_icon="💜", layout="wide")
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.title("💜 Violet Dashboard")
    st.markdown("Facebook vs Google - Violet Performance Comparison")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    with st.spinner("Loading data..."):
        fb_data = load_fb_channel_data()
        google_data = load_google_channel_data()
        fb_df = fb_data.get('violet', pd.DataFrame())
        google_df = google_data.get('violet', pd.DataFrame())
        fb_rb_df = fb_data.get('roll_back', pd.DataFrame())
        google_rb_df = google_data.get('roll_back', pd.DataFrame())

    has_fb = not fb_df.empty
    has_google = not google_df.empty

    if not has_fb and not has_google:
        st.error("No Violet data available.")
        return

    if not fb_rb_df.empty:
        fb_rb_df['date'] = pd.to_datetime(fb_rb_df['date'])
    if not google_rb_df.empty:
        google_rb_df['date'] = pd.to_datetime(google_rb_df['date'])

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
    if not fb_rb_df.empty:
        fb_rb_df = fb_rb_df[(fb_rb_df['date'].dt.date >= date_from) & (fb_rb_df['date'].dt.date <= date_to)]
    if not google_rb_df.empty:
        google_rb_df = google_rb_df[(google_rb_df['date'].dt.date >= date_from) & (google_rb_df['date'].dt.date <= date_to)]

    show_fb = channel_filter in ["All", "Facebook"] and has_fb and not fb_df.empty
    show_google = channel_filter in ["All", "Google"] and has_google and not google_df.empty

    if not show_fb and not show_google:
        st.warning("No data in selected date range or channel.")
        return

    render_content(fb_df, google_df, show_fb, show_google, date_from, date_to, fb_rb_df, google_rb_df)


# Run when accessed as a Streamlit page (not when imported)
if not hasattr(st, '_is_recharge_import'):
    main()
