"""
Recharge Statistics - Combined view of Daily ROI, Roll Back, and Violet
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
            if 'register' in fb_df.columns:
                reg += fb_df['register'].sum()
            ftd += fb_df['ftd'].sum()
            if 'ftd_recharge' in fb_df.columns:
                rech += fb_df['ftd_recharge'].sum()
        if show_g and not g_df.empty:
            cost += g_df['cost'].sum()
            if 'register' in g_df.columns:
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

        type_labels = {'daily_roi': 'Daily ROI', 'roll_back': 'Roll Back', 'violet': 'Violet'}
        type_colors = {'daily_roi': '#3b82f6', 'roll_back': '#f59e0b', 'violet': '#9333ea'}

        # Get Roll Back register for Violet's metrics
        rb = filtered['roll_back']
        rb_reg = 0
        if rb['show_fb'] and not rb['fb'].empty:
            rb_reg += rb['fb']['register'].sum()
        if rb['show_g'] and not rb['google'].empty:
            rb_reg += rb['google']['register'].sum()

        # Compute per-type totals (Violet uses Roll Back register)
        type_totals = {}
        for key in type_labels:
            d = filtered[key]
            t = calc_totals(d['fb'], d['google'], d['show_fb'], d['show_g'])
            if key == 'violet':
                t['register'] = int(rb_reg)
                t['conv_rate'] = (t['ftd'] / rb_reg * 100) if rb_reg > 0 else 0
                t['cpr'] = t['cost'] / rb_reg if rb_reg > 0 else 0
            type_totals[key] = t

        # Executive Header
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 1.5rem 2rem; border-radius: 15px; color: white; margin-bottom: 1.5rem;">
            <h2 style="margin: 0;">Combined Recharge Overview</h2>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">{date_from.strftime('%b %d')} – {date_to.strftime('%b %d, %Y')} &bull; {channel_filter} Channel(s)</p>
        </div>
        """, unsafe_allow_html=True)

        # ---- Shared Cost ----
        shared_cost = type_totals['daily_roi']['cost']
        shared_reg = type_totals['daily_roi']['register']

        # ---- Horizontal KPI Table: views as rows, metrics as columns ----
        metric_cols = [
            ('Cost', lambda t: fmt_c(shared_cost)),
            ('Register', lambda t: fmt_n(t['register'])),
            ('FTD', lambda t: fmt_n(t['ftd'])),
            ('Recharge', lambda t: f"₱{t['ftd_recharge']:,.0f}"),
            ('Conv %', lambda t: f"{t['conv_rate']:.2f}%"),
            ('CPR', lambda t: fmt_c(t['cpr'])),
            ('Cost/FTD', lambda t: fmt_c(t['cost_ftd'])),
            ('ROAS', lambda t: f"{t['roas']:.2f}x"),
            ('ARPPU', lambda t: f"₱{t['arppu']:,.2f}"),
        ]
        header_cells = ''.join(f'<th style="padding:8px 12px;text-align:right;font-size:0.8rem;color:#94a3b8;font-weight:600;">{m[0]}</th>' for m in metric_cols)
        body_rows = ''
        for key, label in type_labels.items():
            t = type_totals[key]
            color = type_colors[key]
            note = ' <span style="font-size:0.65rem;opacity:0.7;">(Reg=RB)</span>' if key == 'violet' else ''
            val_cells = ''.join(
                f'<td style="padding:8px 12px;text-align:right;font-size:1rem;font-weight:700;color:white;">{m[1](t)}</td>'
                for m in metric_cols
            )
            body_rows += f'''<tr>
                <td style="padding:8px 12px;white-space:nowrap;">
                    <span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{color};margin-right:8px;vertical-align:middle;"></span>
                    <span style="font-weight:700;font-size:0.95rem;color:white;">{label}</span>{note}
                </td>
                {val_cells}
            </tr>'''

        st.markdown(f"""
        <div style="overflow-x:auto;margin-bottom:1rem;">
        <table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;">
            <thead><tr>
                <th style="padding:8px 12px;text-align:left;font-size:0.8rem;color:#94a3b8;font-weight:600;">View</th>
                {header_cells}
            </tr></thead>
            <tbody>{body_rows}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ---- Helper: build daily df for one view ----
        def _build_daily(key, use_rb_register=False):
            """Build daily aggregated df for a single view. Returns df with date/cost/register/ftd/ftd_recharge."""
            d = filtered[key]
            parts = []
            for sdf, show in [(d['fb'], d['show_fb']), (d['google'], d['show_g'])]:
                if show and not sdf.empty:
                    agg_cols = {'cost': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum'}
                    if 'register' in sdf.columns:
                        agg_cols['register'] = 'sum'
                    tmp = sdf.groupby(sdf['date'].dt.date).agg(agg_cols).reset_index()
                    if 'register' not in tmp.columns:
                        tmp['register'] = 0
                    parts.append(tmp)
            if not parts:
                return pd.DataFrame()
            df = pd.concat(parts, ignore_index=True).groupby('date').sum().reset_index()
            # For Violet, replace register with Roll Back's daily register
            if use_rb_register:
                rb_daily = _build_daily('roll_back')
                if not rb_daily.empty:
                    rb_reg_map = rb_daily.set_index('date')['register']
                    df['register'] = df['date'].map(rb_reg_map).fillna(0).astype(int)
                else:
                    df['register'] = 0
            return df

        def _add_derived_cols(agg_df):
            """Add CPR, Cost/FTD, Conv%, ROAS, ARPPU to an aggregated df."""
            agg_df['cpr'] = agg_df.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
            agg_df['cost_ftd'] = agg_df.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            agg_df['conv_rate'] = agg_df.apply(lambda r: (r['ftd'] / r['register'] * 100) if r['register'] > 0 else 0, axis=1)
            agg_df['roas'] = agg_df.apply(lambda r: r['ftd_recharge'] / r['cost'] if r['cost'] > 0 else 0, axis=1)
            agg_df['arppu'] = agg_df.apply(lambda r: r['ftd_recharge'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
            return agg_df

        def _weekly_agg(daily_df):
            """Aggregate daily df into weekly rows."""
            if daily_df.empty:
                return pd.DataFrame()
            wd = daily_df.copy()
            wd['date'] = pd.to_datetime(wd['date'])
            wd['week'] = wd['date'].dt.isocalendar().week
            wd['year'] = wd['date'].dt.isocalendar().year
            wd['week_sort'] = wd.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)
            wd['week_start'] = wd.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 1), axis=1)
            wd['week_end'] = wd.apply(lambda x: datetime.fromisocalendar(int(x['year']), int(x['week']), 7), axis=1)
            wd['week_label'] = wd.apply(lambda x: f"{x['week_start'].strftime('%b %d')} - {x['week_end'].strftime('%b %d')}", axis=1)
            wagg = wd.groupby(['week_sort', 'week_label']).agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum',
            }).reset_index().sort_values('week_sort')
            wagg = _add_derived_cols(wagg)
            return wagg

        def _monthly_agg(daily_df):
            """Aggregate daily df into monthly rows."""
            if daily_df.empty:
                return pd.DataFrame()
            md = daily_df.copy()
            md['date'] = pd.to_datetime(md['date'])
            md['month'] = md['date'].dt.to_period('M').astype(str)
            magg = md.groupby('month').agg({
                'cost': 'sum', 'register': 'sum', 'ftd': 'sum', 'ftd_recharge': 'sum',
            }).reset_index().sort_values('month')
            magg = _add_derived_cols(magg)
            return magg

        # Build daily data per view
        view_daily = {
            'daily_roi': _build_daily('daily_roi'),
            'roll_back': _build_daily('roll_back'),
            'violet': _build_daily('violet', use_rb_register=True),
        }

        # Ensure daily data has derived columns too
        for key in view_daily:
            if not view_daily[key].empty:
                view_daily[key] = _add_derived_cols(view_daily[key])

        # Metric definitions for chart selector
        METRIC_DEFS = {
            'FTD': {'col': 'ftd', 'label': 'FTD'},
            'Register': {'col': 'register', 'label': 'Register'},
            'Cost': {'col': 'cost', 'label': 'Cost ($)'},
            'FTD Recharge': {'col': 'ftd_recharge', 'label': 'FTD Recharge (₱)'},
            'Conv Rate': {'col': 'conv_rate', 'label': 'Conv Rate (%)'},
            'CPR': {'col': 'cpr', 'label': 'CPR ($)'},
            'Cost/FTD': {'col': 'cost_ftd', 'label': 'Cost/FTD ($)'},
            'ROAS': {'col': 'roas', 'label': 'ROAS'},
            'ARPPU': {'col': 'arppu', 'label': 'ARPPU (₱)'},
        }
        LINE_COLORS = {
            'FTD': '#10b981', 'Register': '#6366f1', 'Cost': '#ef4444',
            'FTD Recharge': '#a855f7', 'Conv Rate': '#f97316',
            'CPR': '#64748b', 'Cost/FTD': '#78716c',
            'ROAS': '#14b8a6', 'ARPPU': '#ec4899',
        }

        # ---- Shared chart builder: 3 views grouped on one chart ----
        def _grouped_chart(view_data_map, x_col, title, bar_metric, line_metrics, chart_key):
            """One chart with Daily ROI / Roll Back / Violet bars side-by-side + line overlays."""
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            bar_def = METRIC_DEFS[bar_metric]
            has_data = False

            # Grouped bars: one per view
            for key, label in type_labels.items():
                df = view_data_map.get(key, pd.DataFrame())
                if df.empty:
                    continue
                has_data = True
                fig.add_trace(
                    go.Bar(x=df[x_col], y=df[bar_def['col']],
                           name=f"{label} ({bar_metric})",
                           marker_color=type_colors[key], opacity=0.85),
                    secondary_y=False,
                )

            # Line overlays: one line per view per metric
            dash_styles = ['solid', 'dash', 'dot']
            for lm in line_metrics:
                ldef = METRIC_DEFS[lm]
                for vidx, (key, label) in enumerate(type_labels.items()):
                    df = view_data_map.get(key, pd.DataFrame())
                    if df.empty:
                        continue
                    fig.add_trace(
                        go.Scatter(x=df[x_col], y=df[ldef['col']],
                                   name=f"{label} ({lm})",
                                   mode='lines+markers',
                                   line=dict(color=type_colors[key], width=2,
                                             dash=dash_styles[vidx % len(dash_styles)]),
                                   marker=dict(size=4, symbol=['circle', 'diamond', 'square'][vidx % 3])),
                        secondary_y=True,
                    )

            if not has_data:
                st.info(f"No data for {title}.")
                return

            fig.update_layout(
                title=title, height=420, barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=-0.35, font=dict(size=10)),
                margin=dict(l=50, r=50, t=50, b=80),
                hovermode='x unified',
            )
            fig.update_yaxes(title_text=bar_def['label'], secondary_y=False)
            if len(line_metrics) == 1:
                fig.update_yaxes(title_text=METRIC_DEFS[line_metrics[0]]['label'], secondary_y=True)
            elif line_metrics:
                fig.update_yaxes(title_text='Metrics', secondary_y=True)
            fig.update_xaxes(title_text='')
            st.plotly_chart(fig, use_container_width=True, key=chart_key)

        # ---- Metric selector ----
        all_metrics = list(METRIC_DEFS.keys())
        sel_c1, sel_c2 = st.columns(2)
        with sel_c1:
            bar_choice = st.selectbox("Bar Metric", all_metrics, index=0, key="co_bar_metric")
        with sel_c2:
            line_options = [m for m in all_metrics if m != bar_choice]
            line_choice = st.multiselect("Line Metrics", line_options,
                                         default=['Cost'], key="co_line_metrics")

        # ---- Daily Trend Chart ----
        st.subheader("Daily Trend")
        daily_map = {}
        for key in type_labels:
            daily = view_daily[key]
            if not daily.empty:
                dd = daily.copy()
                dd['date'] = pd.to_datetime(dd['date'])
                dd = dd.sort_values('date')
                dd['date_label'] = dd['date'].dt.strftime('%b %d')
                daily_map[key] = dd
        _grouped_chart(daily_map, 'date_label', 'Daily: Daily ROI vs Roll Back vs Violet',
                       bar_choice, line_choice, 'co_daily')

        st.divider()

        # ---- Weekly Chart ----
        st.subheader("Weekly Summary")
        weekly_map = {}
        for key in type_labels:
            wagg = _weekly_agg(view_daily[key])
            if not wagg.empty:
                weekly_map[key] = wagg
        _grouped_chart(weekly_map, 'week_label', 'Weekly: Daily ROI vs Roll Back vs Violet',
                       bar_choice, line_choice, 'co_weekly')

        st.divider()

        # ---- Monthly Chart ----
        st.subheader("Monthly Summary")
        monthly_map = {}
        for key in type_labels:
            magg = _monthly_agg(view_daily[key])
            if not magg.empty:
                monthly_map[key] = magg
        _grouped_chart(monthly_map, 'month', 'Monthly: Daily ROI vs Roll Back vs Violet',
                       bar_choice, line_choice, 'co_monthly')

        st.divider()

        # ---- CSV Export: one per view + combined ----
        st.subheader("Export")
        exp_cols = st.columns(4)
        for idx, (key, label) in enumerate(type_labels.items()):
            daily = view_daily[key]
            if not daily.empty:
                csv = daily.to_csv(index=False)
                exp_cols[idx].download_button(
                    f"Download {label} CSV", data=csv,
                    file_name=f"{key}_{date_from}_{date_to}.csv",
                    mime="text/csv", key=f"co_dl_{key}")
            else:
                exp_cols[idx].write(f"No {label} data")
        combined_parts = []
        for key, label in type_labels.items():
            daily = view_daily[key]
            if not daily.empty:
                tmp = daily.copy()
                tmp['type'] = label
                combined_parts.append(tmp)
        if combined_parts:
            combined_csv = pd.concat(combined_parts, ignore_index=True).to_csv(index=False)
            exp_cols[3].download_button(
                "Download All CSV", data=combined_csv,
                file_name=f"recharge_all_{date_from}_{date_to}.csv",
                mime="text/csv", key="co_dl_all")

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
