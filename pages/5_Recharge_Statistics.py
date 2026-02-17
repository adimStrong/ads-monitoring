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
        cost = reg = ftd = rech = 0
        if show_fb and not fb_df.empty:
            cost += fb_df['cost'].sum()
            reg += fb_df['register'].sum()
            ftd += fb_df['ftd'].sum()
            if 'ftd_recharge' in fb_df.columns:
                rech += fb_df['ftd_recharge'].sum()
        if show_g and not g_df.empty:
            cost += g_df['cost'].sum()
            reg += g_df['register'].sum()
            ftd += g_df['ftd'].sum()
            if 'ftd_recharge' in g_df.columns:
                rech += g_df['ftd_recharge'].sum()
        return {
            'cost': cost, 'register': int(reg), 'ftd': int(ftd),
            'ftd_recharge': rech,
            'cpr': cost / reg if reg > 0 else 0,
            'cost_ftd': cost / ftd if ftd > 0 else 0,
            'conv_rate': (ftd / reg * 100) if reg > 0 else 0,
            'roas': rech / cost if cost > 0 else 0,
            'arppu': rech / ftd if ftd > 0 else 0,
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
        grand_rech = sum(t['ftd_recharge'] for t in type_totals.values())
        grand_cpr = grand_cost / grand_reg if grand_reg > 0 else 0
        grand_cpf = grand_cost / grand_ftd if grand_ftd > 0 else 0
        grand_conv = (grand_ftd / grand_reg * 100) if grand_reg > 0 else 0
        grand_roas = grand_rech / grand_cost if grand_cost > 0 else 0
        grand_arppu = grand_rech / grand_ftd if grand_ftd > 0 else 0

        # Executive Header
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 1.5rem 2rem; border-radius: 15px; color: white; margin-bottom: 1.5rem;">
            <h2 style="margin: 0;">Combined Recharge Overview</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">{date_from.strftime('%b %d')} – {date_to.strftime('%b %d, %Y')} &bull; {channel_filter} Channel(s)</p>
        </div>
        """, unsafe_allow_html=True)

        # Grand Total KPI Cards - Row 1
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Cost", fmt_c(grand_cost))
        c2.metric("Total Register", fmt_n(grand_reg))
        c3.metric("Total FTD", fmt_n(grand_ftd))
        c4.metric("FTD Recharge", f"₱{grand_rech:,.2f}")
        # Row 2
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg CPR", fmt_c(grand_cpr))
        c2.metric("Avg Cost/FTD", fmt_c(grand_cpf))
        c3.metric("Conv Rate", f"{grand_conv:.2f}%")
        c4.metric("ROAS", f"{grand_roas:.2f}x")
        c5.metric("ARPPU", f"₱{grand_arppu:,.2f}")

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
                st.metric("ROAS", f"{t['roas']:.2f}x")
                st.metric("ARPPU", f"₱{t['arppu']:,.2f}")

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

        # ---- Helper: combine all types into one daily df ----
        def _combine_all_daily():
            """Merge FB+Google across all 3 types into a single daily df with type column."""
            rows = []
            for key, label in type_labels.items():
                d = filtered[key]
                for src, sdf, show in [('fb', d['fb'], d['show_fb']), ('google', d['google'], d['show_g'])]:
                    if show and not sdf.empty:
                        tmp = sdf.groupby(sdf['date'].dt.date).agg({
                            'cost': 'sum', 'register': 'sum', 'ftd': 'sum',
                            'ftd_recharge': 'sum',
                        }).reset_index()
                        tmp['type'] = label
                        rows.append(tmp)
            if rows:
                return pd.concat(rows, ignore_index=True)
            return pd.DataFrame()

        all_daily = _combine_all_daily()

        def _agg_period(df, group_col):
            """Aggregate a df by group_col across all types, computing derived metrics."""
            agg = df.groupby(group_col).agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum',
            }).reset_index()
            agg['cpr'] = agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
            agg['cost_ftd'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            agg['conv_rate'] = agg.apply(lambda r: (r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, axis=1)
            agg['roas'] = agg.apply(lambda r: r['ftd_recharge'] / r['cost'] if r['cost'] > 0 else 0, axis=1)
            agg['arppu'] = agg.apply(lambda r: r['ftd_recharge'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            return agg

        def _format_period_table(df, period_col):
            """Format a period aggregation df for display."""
            disp = df.copy()
            disp['cost'] = disp['cost'].apply(lambda x: f"${x:,.2f}")
            disp['register'] = disp['register'].apply(lambda x: f"{int(x):,}")
            disp['ftd'] = disp['ftd'].apply(lambda x: f"{int(x):,}")
            disp['ftd_recharge'] = disp['ftd_recharge'].apply(lambda x: f"₱{x:,.2f}")
            disp['cpr'] = disp['cpr'].apply(lambda x: f"${x:,.2f}")
            disp['cost_ftd'] = disp['cost_ftd'].apply(lambda x: f"${x:,.2f}")
            disp['conv_rate'] = disp['conv_rate'].apply(lambda x: f"{x:.2f}%")
            disp['roas'] = disp['roas'].apply(lambda x: f"{x:.2f}x")
            disp['arppu'] = disp['arppu'].apply(lambda x: f"₱{x:,.2f}")
            disp = disp.rename(columns={
                period_col: period_col.title(), 'cost': 'Cost', 'register': 'Register',
                'ftd': 'FTD', 'ftd_recharge': 'Recharge', 'cpr': 'CPR',
                'cost_ftd': 'Cost/FTD', 'conv_rate': 'Conv %', 'roas': 'ROAS', 'arppu': 'ARPPU',
            })
            return disp

        # ---- Weekly Summary ----
        st.subheader("📆 Weekly Summary")

        if not all_daily.empty:
            wd = all_daily.copy()
            wd['date'] = pd.to_datetime(wd['date'])
            wd['week'] = wd['date'].dt.isocalendar().week
            wd['year'] = wd['date'].dt.isocalendar().year
            wd['week_sort'] = wd.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)
            wd['week_start'] = wd.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 1), axis=1)
            wd['week_end'] = wd.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 7), axis=1)
            wd['week_label'] = wd.apply(lambda x: f"{x['week_start'].strftime('%b %d')} - {x['week_end'].strftime('%b %d')}", axis=1)

            # Aggregate across all types per week
            weekly_agg = wd.groupby(['week_sort', 'week_label']).agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum',
            }).reset_index().sort_values('week_sort')
            weekly_agg['cpr'] = weekly_agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
            weekly_agg['cost_ftd'] = weekly_agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            weekly_agg['conv_rate'] = weekly_agg.apply(lambda r: (r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, axis=1)
            weekly_agg['roas'] = weekly_agg.apply(lambda r: r['ftd_recharge'] / r['cost'] if r['cost'] > 0 else 0, axis=1)
            weekly_agg['arppu'] = weekly_agg.apply(lambda r: r['ftd_recharge'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)

            # Chart: weekly cost by type
            weekly_by_type = wd.groupby(['week_label', 'week_sort', 'type'])['cost'].sum().reset_index().sort_values('week_sort')
            fig = px.bar(weekly_by_type, x='week_label', y='cost', color='type', barmode='group',
                         color_discrete_map={type_labels[k]: type_colors[k] for k in type_labels},
                         title='Weekly Cost by Report Type')
            fig.update_layout(height=380, xaxis_title='', yaxis_title='Cost (USD)',
                              legend=dict(orientation='h', yanchor='bottom', y=-0.25))
            st.plotly_chart(fig, use_container_width=True, key="co_weekly_chart")

            # Table
            w_disp = weekly_agg.drop(columns=['week_sort']).copy()
            w_disp['cost'] = w_disp['cost'].apply(lambda x: f"${x:,.2f}")
            w_disp['register'] = w_disp['register'].apply(lambda x: f"{int(x):,}")
            w_disp['ftd'] = w_disp['ftd'].apply(lambda x: f"{int(x):,}")
            w_disp['ftd_recharge'] = w_disp['ftd_recharge'].apply(lambda x: f"₱{x:,.2f}")
            w_disp['cpr'] = w_disp['cpr'].apply(lambda x: f"${x:,.2f}")
            w_disp['cost_ftd'] = w_disp['cost_ftd'].apply(lambda x: f"${x:,.2f}")
            w_disp['conv_rate'] = w_disp['conv_rate'].apply(lambda x: f"{x:.2f}%")
            w_disp['roas'] = w_disp['roas'].apply(lambda x: f"{x:.2f}x")
            w_disp['arppu'] = w_disp['arppu'].apply(lambda x: f"₱{x:,.2f}")
            w_disp = w_disp.rename(columns={
                'week_label': 'Week', 'cost': 'Cost', 'register': 'Register',
                'ftd': 'FTD', 'ftd_recharge': 'Recharge', 'cpr': 'CPR',
                'cost_ftd': 'Cost/FTD', 'conv_rate': 'Conv %', 'roas': 'ROAS', 'arppu': 'ARPPU',
            })
            st.dataframe(w_disp, use_container_width=True, hide_index=True, key="co_weekly_tbl")
        else:
            st.info("No data available for weekly summary.")

        st.divider()

        # ---- Monthly Summary ----
        st.subheader("📊 Monthly Summary")

        if not all_daily.empty:
            md = all_daily.copy()
            md['date'] = pd.to_datetime(md['date'])
            md['month'] = md['date'].dt.to_period('M').astype(str)

            # Aggregate across all types per month
            monthly_agg = md.groupby('month').agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum',
            }).reset_index().sort_values('month')
            monthly_agg['cpr'] = monthly_agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
            monthly_agg['cost_ftd'] = monthly_agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            monthly_agg['conv_rate'] = monthly_agg.apply(lambda r: (r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, axis=1)
            monthly_agg['roas'] = monthly_agg.apply(lambda r: r['ftd_recharge'] / r['cost'] if r['cost'] > 0 else 0, axis=1)
            monthly_agg['arppu'] = monthly_agg.apply(lambda r: r['ftd_recharge'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)

            # Chart: monthly cost by type
            monthly_by_type = md.groupby(['month', 'type'])['cost'].sum().reset_index().sort_values('month')
            fig = px.bar(monthly_by_type, x='month', y='cost', color='type', barmode='group',
                         color_discrete_map={type_labels[k]: type_colors[k] for k in type_labels},
                         title='Monthly Cost by Report Type')
            fig.update_layout(height=380, xaxis_title='', yaxis_title='Cost (USD)',
                              legend=dict(orientation='h', yanchor='bottom', y=-0.25))
            st.plotly_chart(fig, use_container_width=True, key="co_monthly_chart")

            # Table
            m_disp = monthly_agg.copy()
            m_disp['cost'] = m_disp['cost'].apply(lambda x: f"${x:,.2f}")
            m_disp['register'] = m_disp['register'].apply(lambda x: f"{int(x):,}")
            m_disp['ftd'] = m_disp['ftd'].apply(lambda x: f"{int(x):,}")
            m_disp['ftd_recharge'] = m_disp['ftd_recharge'].apply(lambda x: f"₱{x:,.2f}")
            m_disp['cpr'] = m_disp['cpr'].apply(lambda x: f"${x:,.2f}")
            m_disp['cost_ftd'] = m_disp['cost_ftd'].apply(lambda x: f"${x:,.2f}")
            m_disp['conv_rate'] = m_disp['conv_rate'].apply(lambda x: f"{x:.2f}%")
            m_disp['roas'] = m_disp['roas'].apply(lambda x: f"{x:.2f}x")
            m_disp['arppu'] = m_disp['arppu'].apply(lambda x: f"₱{x:,.2f}")
            m_disp = m_disp.rename(columns={
                'month': 'Month', 'cost': 'Cost', 'register': 'Register',
                'ftd': 'FTD', 'ftd_recharge': 'Recharge', 'cpr': 'CPR',
                'cost_ftd': 'Cost/FTD', 'conv_rate': 'Conv %', 'roas': 'ROAS', 'arppu': 'ARPPU',
            })
            st.dataframe(m_disp, use_container_width=True, hide_index=True, key="co_monthly_tbl")
        else:
            st.info("No data available for monthly summary.")

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
                'Recharge': t['ftd_recharge'],
                'CPR': t['cpr'],
                'Cost/FTD': t['cost_ftd'],
                'Conv %': t['conv_rate'],
                'ROAS': t['roas'],
                'ARPPU': t['arppu'],
            })
        # Grand total row
        summary_rows.append({
            'Report Type': 'TOTAL',
            'FB Cost': total_fb_cost,
            'Google Cost': total_g_cost,
            'Total Cost': grand_cost,
            'Register': grand_reg,
            'FTD': grand_ftd,
            'Recharge': grand_rech,
            'CPR': grand_cpr,
            'Cost/FTD': grand_cpf,
            'Conv %': grand_conv,
            'ROAS': grand_roas,
            'ARPPU': grand_arppu,
        })
        summary_df = pd.DataFrame(summary_rows)

        # Format for display
        disp = summary_df.copy()
        for col in ['FB Cost', 'Google Cost', 'Total Cost', 'CPR', 'Cost/FTD']:
            disp[col] = disp[col].apply(lambda x: f"${x:,.2f}")
        disp['Register'] = disp['Register'].apply(lambda x: f"{int(x):,}")
        disp['FTD'] = disp['FTD'].apply(lambda x: f"{int(x):,}")
        disp['Recharge'] = disp['Recharge'].apply(lambda x: f"₱{x:,.2f}")
        disp['Conv %'] = disp['Conv %'].apply(lambda x: f"{x:.2f}%")
        disp['ROAS'] = disp['ROAS'].apply(lambda x: f"{x:.2f}x")
        disp['ARPPU'] = disp['ARPPU'].apply(lambda x: f"₱{x:,.2f}")

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
