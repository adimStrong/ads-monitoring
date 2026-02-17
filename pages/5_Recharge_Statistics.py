"""
Recharge Statistics - Combined view of Daily ROI, Roll Back, and Violet
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_fb_channel_data, load_google_channel_data, refresh_channel_data
from config import CHANNEL_ROI_ENABLED

st.set_page_config(page_title="Recharge Statistics", page_icon="💰", layout="wide")

st.markdown("""
<style>
    .fb-card {
        background: linear-gradient(135deg, #1877f2 0%, #42a5f5 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .google-card {
        background: linear-gradient(135deg, #ea4335 0%, #ff6b6b 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
    /* Hide individual pages from sidebar */
    [data-testid="stSidebarNav"] a[href*="Daily_ROI"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Roll_Back"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Violet"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Import render functions - set flag so page modules don't auto-run main()
st._is_recharge_import = True
import importlib.util

def _load_render(filename):
    """Load render_content from a page file without triggering main()."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(filename.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render_content

_daily_roi_render = _load_render('19_Daily_ROI.py')
_roll_back_render = _load_render('6_Roll_Back.py')
_violet_render = _load_render('7_Violet.py')
del st._is_recharge_import


def main():
    st.title("💰 Recharge Statistics")
    st.markdown("Combined view: Daily ROI, Roll Back, and Violet")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    # Load all data once (shared across tabs)
    with st.spinner("Loading data..."):
        fb_data = load_fb_channel_data()
        google_data = load_google_channel_data()

    # Collect all dates across all data types for shared date range
    all_dates = []
    data_sets = {}
    for key in ['daily_roi', 'roll_back', 'violet']:
        fb_df = fb_data.get(key, pd.DataFrame())
        g_df = google_data.get(key, pd.DataFrame())
        if not fb_df.empty:
            fb_df['date'] = pd.to_datetime(fb_df['date'])
            all_dates.extend(fb_df['date'].tolist())
        if not g_df.empty:
            g_df['date'] = pd.to_datetime(g_df['date'])
            all_dates.extend(g_df['date'].tolist())
        data_sets[key] = {'fb': fb_df, 'google': g_df}

    if not all_dates:
        st.error("No data available for any report type.")
        return

    data_min_date = min(all_dates).date()
    data_max_date = max(all_dates).date()
    yesterday = datetime.now().date() - timedelta(days=1)
    max_selectable_date = min(data_max_date, yesterday)

    # Shared sidebar controls
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_channel_data()
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("📅 Date Range")
        default_start = max(data_min_date, max_selectable_date - timedelta(days=30))
        date_from = st.date_input("From", value=default_start,
                                   min_value=data_min_date, max_value=max_selectable_date,
                                   key="rs_from")
        date_to = st.date_input("To", value=max_selectable_date,
                                 min_value=data_min_date, max_value=max_selectable_date,
                                 key="rs_to")

        st.markdown("---")
        st.subheader("Channel Filter")
        channel_filter = st.selectbox("Select Channel", ["All", "Facebook", "Google"], key="rs_ch")

    # Filter and prepare data for each tab
    def filter_data(fb_df, g_df):
        if not fb_df.empty:
            fb_df = fb_df[(fb_df['date'].dt.date >= date_from) & (fb_df['date'].dt.date <= date_to)]
        if not g_df.empty:
            g_df = g_df[(g_df['date'].dt.date >= date_from) & (g_df['date'].dt.date <= date_to)]

        has_fb = not fb_df.empty
        has_g = not g_df.empty
        show_fb = channel_filter in ["All", "Facebook"] and has_fb
        show_g = channel_filter in ["All", "Google"] and has_g
        return fb_df, g_df, show_fb, show_g

    # Create 3 tabs
    tab_dr, tab_rb, tab_vi = st.tabs(["📊 Daily ROI", "🔄 Roll Back", "💜 Violet"])

    with tab_dr:
        fb_df, g_df, show_fb, show_g = filter_data(
            data_sets['daily_roi']['fb'].copy(),
            data_sets['daily_roi']['google'].copy()
        )
        if not show_fb and not show_g:
            st.warning("No Daily ROI data in selected range.")
        else:
            _daily_roi_render(fb_df, g_df, show_fb, show_g, date_from, date_to, key_prefix="rs_dr")

    with tab_rb:
        fb_df, g_df, show_fb, show_g = filter_data(
            data_sets['roll_back']['fb'].copy(),
            data_sets['roll_back']['google'].copy()
        )
        if not show_fb and not show_g:
            st.warning("No Roll Back data in selected range.")
        else:
            _roll_back_render(fb_df, g_df, show_fb, show_g, date_from, date_to, key_prefix="rs_rb")

    with tab_vi:
        fb_df, g_df, show_fb, show_g = filter_data(
            data_sets['violet']['fb'].copy(),
            data_sets['violet']['google'].copy()
        )
        # Violet needs Roll Back data for registration counts
        fb_rb = data_sets['roll_back']['fb'].copy()
        g_rb = data_sets['roll_back']['google'].copy()
        if not fb_rb.empty:
            fb_rb = fb_rb[(fb_rb['date'].dt.date >= date_from) & (fb_rb['date'].dt.date <= date_to)]
        if not g_rb.empty:
            g_rb = g_rb[(g_rb['date'].dt.date >= date_from) & (g_rb['date'].dt.date <= date_to)]

        if not show_fb and not show_g:
            st.warning("No Violet data in selected range.")
        else:
            _violet_render(fb_df, g_df, show_fb, show_g, date_from, date_to, fb_rb, g_rb, key_prefix="rs_vi")


main()
