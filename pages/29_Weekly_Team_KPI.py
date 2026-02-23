"""
Weekly Team KPI Dashboard — Per-team weekly metrics with Week-over-Week comparison.
Aggregates Team Channel daily data into Tue-Mon weeks.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from channel_data_loader import load_team_channel_data, refresh_team_channel_data
from config import CHANNEL_ROI_ENABLED, SIDEBAR_HIDE_CSS

# Team mapping + colors (same as page 25)
TEAM_CHANNEL_MAP = {
    'JASON / SHILA': 'Promo - 09 - 12 - 13',
    'RON / ADRIAN': 'Promo - 07 - 10 - 11',
    'MIKA / JOMAR': 'Promo - 06 - 08',
}

TEAM_COLORS = {
    'JASON / SHILA': '#3b82f6',
    'RON / ADRIAN': '#22c55e',
    'MIKA / JOMAR': '#a855f7',
}


# ── Tue-Mon week helpers ─────────────────────────────────────────────
def get_tue_mon_week(date):
    adjusted = date - timedelta(days=(date.weekday() - 1) % 7)
    return adjusted.isocalendar()[0], adjusted.isocalendar()[1]


def build_weekly_team_df(daily_df, channel_team_map=None):
    """Aggregate Team Channel daily data into Tue-Mon weekly rows per team.
    Uses channel_team_map to assign teams since daily rows lack team names."""
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])

    # Map channels to teams using the overall section mapping
    if channel_team_map:
        df['team'] = df['channel'].map(channel_team_map)
    # Only rows with a real team
    df = df[df['team'].notna() & (df['team'] != '') & (df['team'] != 'All')]

    if df.empty:
        return pd.DataFrame()

    df['week_info'] = df['date'].apply(get_tue_mon_week)
    df['week_key'] = df['week_info'].apply(lambda x: f"{x[0]}-W{x[1]:02d}")

    agg = df.groupby(['team', 'week_key']).agg(
        cost=('cost', 'sum'),
        registrations=('registrations', 'sum'),
        first_recharge=('first_recharge', 'sum'),
        total_amount=('total_amount', 'sum'),
        date_start=('date', 'min'),
        date_end=('date', 'max'),
    ).reset_index()

    # Derived metrics
    agg['cpr'] = agg.apply(lambda r: r['cost'] / r['registrations'] if r['registrations'] > 0 else 0, axis=1)
    agg['cpfd'] = agg.apply(lambda r: r['cost'] / r['first_recharge'] if r['first_recharge'] > 0 else 0, axis=1)
    agg['arppu'] = agg.apply(lambda r: r['total_amount'] / r['first_recharge'] if r['first_recharge'] > 0 else 0, axis=1)
    agg['roas'] = agg.apply(lambda r: r['total_amount'] / r['cost'] if r['cost'] > 0 else 0, axis=1)

    # Week labels + day counts
    agg['days'] = (agg['date_end'] - agg['date_start']).dt.days + 1
    agg['week_label'] = agg.apply(
        lambda r: f"{r['date_start'].strftime('%b %d')} – {r['date_end'].strftime('%b %d')}", axis=1)

    return agg.sort_values(['team', 'week_key'])


# ── Display helpers ───────────────────────────────────────────────────
def arrow_delta(curr, prev, higher_is_better=True):
    if prev == 0 and curr == 0:
        return '<span style="color:#64748b">—</span>'
    if prev == 0:
        return '<span style="color:#22c55e">▲ new</span>'
    pct = (curr - prev) / abs(prev) * 100
    if abs(pct) < 0.1:
        return '<span style="color:#64748b">→ 0%</span>'
    is_good = (pct > 0) == higher_is_better
    color = '#22c55e' if is_good else '#ef4444'
    arrow = '▲' if pct > 0 else '▼'
    return f'<span style="color:{color}">{arrow} {abs(pct):.1f}%</span>'


# ── Main render ───────────────────────────────────────────────────────
def render_content(key_prefix="wtk"):
    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    with ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", type="primary", key=f"{key_prefix}_ref"):
            refresh_team_channel_data()
            st.rerun()

    with st.spinner("Loading Team Channel data..."):
        data = load_team_channel_data()
        daily_df = data.get('daily', pd.DataFrame())
        team_actual_df = data.get('team_actual', pd.DataFrame())

    # Build channel→team mapping from Team Actual section (correct grouping)
    channel_team_map = {}
    if team_actual_df is not None and not team_actual_df.empty:
        for _, row in team_actual_df.iterrows():
            team = row.get('team', '')
            ch_src = str(row.get('channel_source', ''))
            if not team or not ch_src:
                continue
            nums = re.findall(r'(\d+)', ch_src)
            for n in nums:
                channel_team_map[f'FB-FB-FB-DEERPROMO{int(n):02d}'] = team

    weekly = build_weekly_team_df(daily_df, channel_team_map)
    if weekly.empty:
        st.warning("No daily Team Channel data available to build weekly view.")
        st.info("The Team Channel sheet needs daily data rows with team assignments and dates.")
        return

    teams = sorted(weekly['team'].unique())
    team_names = ["All Teams"] + list(teams)
    weeks_sorted = sorted(weekly['week_key'].unique())

    # Week labels
    week_labels = {}
    for wk in weeks_sorted:
        subset = weekly[weekly['week_key'] == wk].iloc[0]
        days = int(subset['days'])
        tag = f" ⚠️ ({days}/7)" if days < 7 else ""
        week_labels[wk] = f"{subset['week_label']}{tag}"

    with ctrl1:
        selected = st.selectbox("Team", team_names, key=f"{key_prefix}_team")
    with ctrl2:
        sel_wk_idx = st.selectbox(
            "Week", range(len(weeks_sorted)),
            index=len(weeks_sorted) - 1,
            format_func=lambda i: week_labels[weeks_sorted[i]],
            key=f"{key_prefix}_week")
    sel_week = weeks_sorted[sel_wk_idx]
    prev_week = weeks_sorted[sel_wk_idx - 1] if sel_wk_idx > 0 else None

    # Team-Channel mapping table
    st.markdown("#### Team → Channel Mapping")
    mapping_html = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:15px">'
    mapping_html += '<tr style="background:#1e293b;color:#fff"><th style="padding:8px;border:1px solid #334155;text-align:left">Team</th><th style="padding:8px;border:1px solid #334155;text-align:left">Channel Source</th></tr>'
    for team, channels in TEAM_CHANNEL_MAP.items():
        color = TEAM_COLORS.get(team, '#64748b')
        mapping_html += f'<tr style="background:#0f172a;color:#e2e8f0"><td style="padding:8px;border:1px solid #334155;font-weight:bold;color:{color}">{team}</td><td style="padding:8px;border:1px solid #334155">{channels}</td></tr>'
    mapping_html += '</table>'
    st.markdown(mapping_html, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────
    if selected == "All Teams":
        st.subheader(f"All Teams — {week_labels[sel_week]}")

        wk_data = weekly[weekly['week_key'] == sel_week]
        prev_data = weekly[weekly['week_key'] == prev_week] if prev_week else pd.DataFrame()

        # Summary table
        th = 'padding:6px;text-align:center;border:1px solid #334155'
        td = 'padding:5px;text-align:center;border:1px solid #334155'
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += f'<tr style="background:#1e293b;color:#fff">'
        for c in ['Team', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'CPR ($)', 'CPFD ($)', 'ARPPU (₱)', 'ROAS']:
            html += f'<th style="{th}">{c}</th>'
        html += '</tr>'

        for _, r in wk_data.iterrows():
            team = r['team']
            color = TEAM_COLORS.get(team, '#64748b')
            # Find prev
            pr = None
            if not prev_data.empty:
                pr_rows = prev_data[prev_data['team'] == team]
                if not pr_rows.empty:
                    pr = pr_rows.iloc[0]

            html += f'<tr style="background:#0f172a;color:#e2e8f0">'
            html += f'<td style="{td};font-weight:bold;color:{color}">{team}</td>'

            for val, fmt, key, hib in [
                (r['cost'], '${:,.0f}', 'cost', False),
                (r['registrations'], '{:,.0f}', 'registrations', True),
                (r['first_recharge'], '{:,.0f}', 'first_recharge', True),
                (r['total_amount'], '₱{:,.0f}', 'total_amount', True),
                (r['cpr'], '${:.2f}', 'cpr', False),
                (r['cpfd'], '${:.2f}', 'cpfd', False),
                (r['arppu'], '₱{:,.0f}', 'arppu', True),
                (r['roas'], '{:.2f}', 'roas', True),
            ]:
                cell = fmt.format(val)
                if pr is not None and pr[key] > 0:
                    a = arrow_delta(val, pr[key], hib)
                    cell += f' <span style="font-size:11px">{a}</span>'
                html += f'<td style="{td}">{cell}</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

        # Grouped bar charts
        st.divider()
        st.subheader("Team Comparison")
        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure()
            for wk in weeks_sorted[-4:]:  # last 4 weeks
                wk_sub = weekly[weekly['week_key'] == wk]
                fig.add_trace(go.Bar(
                    name=week_labels.get(wk, wk),
                    x=wk_sub['team'], y=wk_sub['roas'],
                    text=[f"{v:.2f}" for v in wk_sub['roas']], textposition='outside',
                ))
            fig.update_layout(title='ROAS by Week', barmode='group', height=400,
                              yaxis_title='Ratio', margin=dict(t=40, b=40))
            st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_roas")

        with col2:
            fig = go.Figure()
            for wk in weeks_sorted[-4:]:
                wk_sub = weekly[weekly['week_key'] == wk]
                fig.add_trace(go.Bar(
                    name=week_labels.get(wk, wk),
                    x=wk_sub['team'], y=wk_sub['cpfd'],
                    text=[f"${v:.2f}" for v in wk_sub['cpfd']], textposition='outside',
                ))
            fig.update_layout(title='CPFD ($) by Week', barmode='group', height=400,
                              yaxis_title='USD', margin=dict(t=40, b=40))
            st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cpfd")

    # ──────────────────────────────────────────────────────────────────
    else:
        team_name = selected
        team_weeks = weekly[weekly['team'] == team_name].sort_values('week_key')
        if team_weeks.empty:
            st.warning(f"No weekly data for {team_name}")
            return

        curr = team_weeks[team_weeks['week_key'] == sel_week]
        if curr.empty:
            st.warning(f"No data for {team_name} in selected week")
            return
        curr = curr.iloc[0]

        prev_row = None
        if prev_week:
            pr = team_weeks[team_weeks['week_key'] == prev_week]
            if not pr.empty:
                prev_row = pr.iloc[0]

        color = TEAM_COLORS.get(team_name, '#64748b')
        st.subheader(f"{team_name} — {week_labels[sel_week]}")

        # Metric cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            d = f"${prev_row['cost']:,.0f} prev" if prev_row is not None else None
            st.metric("Cost ($)", f"${curr['cost']:,.0f}", d, delta_color="inverse")
        with c2:
            d = f"{((curr['roas'] - prev_row['roas'])/prev_row['roas']*100):+.1f}% WoW" if prev_row is not None and prev_row['roas'] > 0 else None
            st.metric("ROAS", f"{curr['roas']:.2f}", d)
        with c3:
            d = f"{((curr['cpfd'] - prev_row['cpfd'])/prev_row['cpfd']*100):+.1f}% WoW" if prev_row is not None and prev_row['cpfd'] > 0 else None
            st.metric("CPFD ($)", f"${curr['cpfd']:.2f}", d, delta_color="inverse")
        with c4:
            d = f"{((curr['arppu'] - prev_row['arppu'])/prev_row['arppu']*100):+.1f}% WoW" if prev_row is not None and prev_row['arppu'] > 0 else None
            st.metric("ARPPU (₱)", f"₱{curr['arppu']:,.0f}", d)

        # Weekly history table
        st.divider()
        st.subheader("Weekly History")
        th = 'padding:6px;text-align:center;border:1px solid #334155'
        td = 'padding:5px;text-align:center;border:1px solid #334155'
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += f'<tr style="background:#1e293b;color:#fff">'
        for c in ['Week', 'Days', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'CPR ($)', 'CPFD ($)', 'ARPPU (₱)', 'ROAS']:
            html += f'<th style="{th}">{c}</th>'
        html += '</tr>'

        prev_r = None
        for _, r in team_weeks.iterrows():
            incomplete = ' ⚠️' if r['days'] < 7 else ''
            html += f'<tr style="background:#0f172a;color:#e2e8f0">'
            html += f'<td style="{td};white-space:nowrap">{r["week_label"]}{incomplete}</td>'
            html += f'<td style="{td}">{int(r["days"])}</td>'

            for val, fmt, key, hib in [
                (r['cost'], '${:,.0f}', 'cost', False),
                (r['registrations'], '{:,.0f}', 'registrations', True),
                (r['first_recharge'], '{:,.0f}', 'first_recharge', True),
                (r['total_amount'], '₱{:,.0f}', 'total_amount', True),
                (r['cpr'], '${:.2f}', 'cpr', False),
                (r['cpfd'], '${:.2f}', 'cpfd', False),
                (r['arppu'], '₱{:,.0f}', 'arppu', True),
                (r['roas'], '{:.2f}', 'roas', True),
            ]:
                cell = fmt.format(val)
                if prev_r is not None and prev_r[key] > 0:
                    a = arrow_delta(val, prev_r[key], hib)
                    cell += f' <span style="font-size:11px">{a}</span>'
                html += f'<td style="{td}">{cell}</td>'
            html += '</tr>'
            prev_r = r
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

    st.caption("Weekly Team KPI | Data from Team Channel sheet (Tue-Mon weeks)")


def main():
    st.set_page_config(page_title="Weekly Team KPI", page_icon="📅", layout="wide")
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("📅 Weekly Team KPI")
    render_content(key_prefix="wtk")


if not hasattr(st, '_is_recharge_import'):
    main()
