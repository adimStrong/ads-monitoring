"""
Recharge Statistics - Combined view of Daily ROI, Roll Back, and Violet
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_fb_channel_data, load_google_channel_data, refresh_channel_data
from config import CHANNEL_ROI_ENABLED, SIDEBAR_HIDE_CSS

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
</style>
""", unsafe_allow_html=True)

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

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

    # Helper: aggregate totals from a df pair
    def calc_totals(fb_df, g_df, show_fb, show_g):
        cost = reg = ftd = 0
        if show_fb and not fb_df.empty:
            cost += fb_df['cost'].sum()
            reg += fb_df['register'].sum()
            ftd += fb_df['ftd'].sum()
        if show_g and not g_df.empty:
            cost += g_df['cost'].sum()
            reg += g_df['register'].sum()
            ftd += g_df['ftd'].sum()
        return {
            'cost': cost, 'register': int(reg), 'ftd': int(ftd),
            'cpr': cost / reg if reg > 0 else 0,
            'cost_ftd': cost / ftd if ftd > 0 else 0,
            'conv_rate': (ftd / reg * 100) if reg > 0 else 0,
        }

    def calc_channel_totals(fb_df, g_df):
        fb_cost = fb_df['cost'].sum() if not fb_df.empty else 0
        fb_ftd = int(fb_df['ftd'].sum()) if not fb_df.empty else 0
        g_cost = g_df['cost'].sum() if not g_df.empty else 0
        g_ftd = int(g_df['ftd'].sum()) if not g_df.empty else 0
        return fb_cost, fb_ftd, g_cost, g_ftd

    # Pre-filter all datasets
    filtered = {}
    for key in ['daily_roi', 'roll_back', 'violet']:
        fb_f, g_f, s_fb, s_g = filter_data(
            data_sets[key]['fb'].copy(), data_sets[key]['google'].copy()
        )
        filtered[key] = {'fb': fb_f, 'google': g_f, 'show_fb': s_fb, 'show_g': s_g}

    # Create 4 tabs
    tab_all, tab_dr, tab_rb, tab_vi = st.tabs([
        "📋 Combined Overview", "📊 Daily ROI", "🔄 Roll Back", "💜 Violet"
    ])

    # ================================================================
    # TAB: COMBINED OVERVIEW
    # ================================================================
    with tab_all:
        fmt_c = lambda v: f"${v:,.2f}" if v else "$0.00"
        fmt_n = lambda v: f"{int(v):,}"

        # Compute per-type totals
        type_labels = {'daily_roi': 'Daily ROI', 'roll_back': 'Roll Back', 'violet': 'Violet'}
        type_colors = {'daily_roi': '#3b82f6', 'roll_back': '#f59e0b', 'violet': '#9333ea'}
        type_totals = {}
        for key, label in type_labels.items():
            d = filtered[key]
            type_totals[key] = calc_totals(d['fb'], d['google'], d['show_fb'], d['show_g'])

        # Grand totals
        grand_cost = sum(t['cost'] for t in type_totals.values())
        grand_reg = sum(t['register'] for t in type_totals.values())
        grand_ftd = sum(t['ftd'] for t in type_totals.values())
        grand_cpr = grand_cost / grand_reg if grand_reg > 0 else 0
        grand_cpf = grand_cost / grand_ftd if grand_ftd > 0 else 0
        grand_conv = (grand_ftd / grand_reg * 100) if grand_reg > 0 else 0

        # Executive Header
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 1.5rem 2rem; border-radius: 15px; color: white; margin-bottom: 1.5rem;">
            <h2 style="margin: 0;">Combined Recharge Overview</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">{date_from.strftime('%b %d')} – {date_to.strftime('%b %d, %Y')} &bull; {channel_filter} Channel(s)</p>
        </div>
        """, unsafe_allow_html=True)

        # Grand Total KPI Cards
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Cost", fmt_c(grand_cost))
        c2.metric("Total Register", fmt_n(grand_reg))
        c3.metric("Total FTD", fmt_n(grand_ftd))
        c4.metric("Avg CPR", fmt_c(grand_cpr))
        c5.metric("Avg Cost/FTD", fmt_c(grand_cpf))
        c6.metric("Conv Rate", f"{grand_conv:.2f}%")

        st.divider()

        # ---- Breakdown by Report Type ----
        st.subheader("Breakdown by Report Type")

        cols = st.columns(3)
        for idx, (key, label) in enumerate(type_labels.items()):
            t = type_totals[key]
            color = type_colors[key]
            pct_cost = (t['cost'] / grand_cost * 100) if grand_cost > 0 else 0
            with cols[idx]:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {color}cc 0%, {color}99 100%); padding: 1.2rem; border-radius: 12px; color: white;">
                    <h3 style="margin: 0;">{label}</h3>
                    <p style="margin: 4px 0 0 0; font-size: 0.8rem; opacity: 0.85;">{pct_cost:.1f}% of total cost</p>
                </div>
                """, unsafe_allow_html=True)
                st.metric("Cost", fmt_c(t['cost']), label_visibility="visible")
                st.metric("Register", fmt_n(t['register']))
                st.metric("FTD", fmt_n(t['ftd']))
                st.metric("CPR", fmt_c(t['cpr']))
                st.metric("Cost/FTD", fmt_c(t['cost_ftd']))
                st.metric("Conv Rate", f"{t['conv_rate']:.2f}%")

        st.divider()

        # ---- Charts Row 1: Cost & FTD by Type ----
        col1, col2 = st.columns(2)

        with col1:
            chart_data = pd.DataFrame([
                {'Type': type_labels[k], 'Cost': type_totals[k]['cost'], 'color': type_colors[k]}
                for k in type_labels
            ])
            fig = px.bar(chart_data, x='Type', y='Cost', color='Type',
                         color_discrete_map={type_labels[k]: type_colors[k] for k in type_labels},
                         title='Cost by Report Type', text_auto='$.4s')
            fig.update_layout(height=380, showlegend=False, yaxis_title='Cost (USD)')
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True, key="co_cost_type")

        with col2:
            chart_data = pd.DataFrame([
                {'Type': type_labels[k], 'FTD': type_totals[k]['ftd']}
                for k in type_labels
            ])
            fig = px.bar(chart_data, x='Type', y='FTD', color='Type',
                         color_discrete_map={type_labels[k]: type_colors[k] for k in type_labels},
                         title='FTD by Report Type', text_auto=',')
            fig.update_layout(height=380, showlegend=False, yaxis_title='FTD Count')
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True, key="co_ftd_type")

        # ---- Charts Row 2: Channel Split ----
        st.subheader("Channel Comparison")
        col1, col2 = st.columns(2)

        # Aggregate FB vs Google across all types
        total_fb_cost = total_fb_ftd = total_g_cost = total_g_ftd = 0
        for key in type_labels:
            d = filtered[key]
            fc, ff, gc, gf = calc_channel_totals(d['fb'], d['google'])
            if d['show_fb']:
                total_fb_cost += fc
                total_fb_ftd += ff
            if d['show_g']:
                total_g_cost += gc
                total_g_ftd += gf

        with col1:
            pie_data = pd.DataFrame([
                {'Channel': 'Facebook', 'Cost': total_fb_cost},
                {'Channel': 'Google', 'Cost': total_g_cost},
            ])
            fig = px.pie(pie_data, names='Channel', values='Cost', title='Cost Distribution by Channel',
                         color='Channel', color_discrete_map={'Facebook': '#1877f2', 'Google': '#ea4335'},
                         hole=0.4)
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True, key="co_pie_cost")

        with col2:
            bar_data = pd.DataFrame([
                {'Channel': 'Facebook', 'FTD': total_fb_ftd},
                {'Channel': 'Google', 'FTD': total_g_ftd},
            ])
            fig = px.bar(bar_data, x='Channel', y='FTD', color='Channel',
                         color_discrete_map={'Facebook': '#1877f2', 'Google': '#ea4335'},
                         title='FTD by Channel', text_auto=',')
            fig.update_layout(height=380, showlegend=False)
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True, key="co_bar_ftd_ch")

        st.divider()

        # ---- Daily Combined Trend ----
        st.subheader("Daily Cost Trend (All Types)")

        trend_rows = []
        for key, label in type_labels.items():
            d = filtered[key]
            for source, sdf, show in [('fb', d['fb'], d['show_fb']), ('google', d['google'], d['show_g'])]:
                if show and not sdf.empty:
                    daily = sdf.groupby(sdf['date'].dt.date)['cost'].sum().reset_index()
                    daily.columns = ['date', 'cost']
                    daily['type'] = label
                    trend_rows.append(daily)

        if trend_rows:
            trend_df = pd.concat(trend_rows, ignore_index=True)
            trend_agg = trend_df.groupby(['date', 'type'])['cost'].sum().reset_index()
            fig = px.line(trend_agg, x='date', y='cost', color='type',
                          color_discrete_map={type_labels[k]: type_colors[k] for k in type_labels},
                          title='Daily Cost by Report Type', markers=True)
            fig.update_layout(height=400, legend=dict(orientation='h', yanchor='bottom', y=-0.25),
                              xaxis_title='', yaxis_title='Cost (USD)')
            st.plotly_chart(fig, use_container_width=True, key="co_trend")
        else:
            st.info("No daily data available for trend.")

        st.divider()

        # ---- Summary Table ----
        st.subheader("Summary Table")
        summary_rows = []
        for key, label in type_labels.items():
            t = type_totals[key]
            d = filtered[key]
            fc, ff, gc, gf = calc_channel_totals(d['fb'], d['google'])
            summary_rows.append({
                'Report Type': label,
                'FB Cost': fc if d['show_fb'] else 0,
                'Google Cost': gc if d['show_g'] else 0,
                'Total Cost': t['cost'],
                'Register': t['register'],
                'FTD': t['ftd'],
                'CPR': t['cpr'],
                'Cost/FTD': t['cost_ftd'],
                'Conv %': t['conv_rate'],
            })
        # Grand total row
        summary_rows.append({
            'Report Type': 'TOTAL',
            'FB Cost': total_fb_cost,
            'Google Cost': total_g_cost,
            'Total Cost': grand_cost,
            'Register': grand_reg,
            'FTD': grand_ftd,
            'CPR': grand_cpr,
            'Cost/FTD': grand_cpf,
            'Conv %': grand_conv,
        })
        summary_df = pd.DataFrame(summary_rows)

        # Format for display
        disp = summary_df.copy()
        for col in ['FB Cost', 'Google Cost', 'Total Cost', 'CPR', 'Cost/FTD']:
            disp[col] = disp[col].apply(lambda x: f"${x:,.2f}")
        disp['Register'] = disp['Register'].apply(lambda x: f"{int(x):,}")
        disp['FTD'] = disp['FTD'].apply(lambda x: f"{int(x):,}")
        disp['Conv %'] = disp['Conv %'].apply(lambda x: f"{x:.2f}%")

        st.dataframe(disp, use_container_width=True, hide_index=True, key="co_summary_tbl")

        # Export
        csv = summary_df.to_csv(index=False)
        st.download_button("Download Summary CSV", data=csv,
                           file_name=f"recharge_summary_{date_from}_{date_to}.csv",
                           mime="text/csv", key="co_dl")

    # ================================================================
    # TAB: DAILY ROI
    # ================================================================
    with tab_dr:
        d = filtered['daily_roi']
        if not d['show_fb'] and not d['show_g']:
            st.warning("No Daily ROI data in selected range.")
        else:
            _daily_roi_render(d['fb'], d['google'], d['show_fb'], d['show_g'], date_from, date_to, key_prefix="rs_dr")

    # ================================================================
    # TAB: ROLL BACK
    # ================================================================
    with tab_rb:
        d = filtered['roll_back']
        if not d['show_fb'] and not d['show_g']:
            st.warning("No Roll Back data in selected range.")
        else:
            _roll_back_render(d['fb'], d['google'], d['show_fb'], d['show_g'], date_from, date_to, key_prefix="rs_rb")

    # ================================================================
    # TAB: VIOLET
    # ================================================================
    with tab_vi:
        d = filtered['violet']
        # Violet needs Roll Back data for registration counts
        fb_rb = data_sets['roll_back']['fb'].copy()
        g_rb = data_sets['roll_back']['google'].copy()
        if not fb_rb.empty:
            fb_rb = fb_rb[(fb_rb['date'].dt.date >= date_from) & (fb_rb['date'].dt.date <= date_to)]
        if not g_rb.empty:
            g_rb = g_rb[(g_rb['date'].dt.date >= date_from) & (g_rb['date'].dt.date <= date_to)]

        if not d['show_fb'] and not d['show_g']:
            st.warning("No Violet data in selected range.")
        else:
            _violet_render(d['fb'], d['google'], d['show_fb'], d['show_g'], date_from, date_to, fb_rb, g_rb, key_prefix="rs_vi")


main()
