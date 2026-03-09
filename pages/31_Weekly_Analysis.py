"""
Weekly Analysis Dashboard — Comprehensive weekly ad performance with WoW comparison,
per-agent/team breakdowns, channel comparison, and multi-week trends.
Weeks run Monday to Sunday.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import (
    load_agent_performance_data, refresh_agent_performance_data,
    load_fb_channel_data, load_google_channel_data, refresh_channel_data,
)
from config import (
    AGENT_PERFORMANCE_TABS,
    KPI_PHP_USD_RATE,
    EXCLUDED_FROM_REPORTING,
    SIDEBAR_HIDE_CSS,
)

st.set_page_config(page_title="Weekly Analysis", page_icon="W", layout="wide")
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

AGENTS_LIST = [t['agent'] for t in AGENT_PERFORMANCE_TABS if t['agent'].upper() not in EXCLUDED_FROM_REPORTING]

TEAM_MAP = {
    'Jason': 'JASON / SHILA', 'Shila': 'JASON / SHILA',
    'Ron': 'RON / ADRIAN', 'Adrian': 'RON / ADRIAN',
    'Mika': 'MIKA / JOMAR', 'Jomar': 'MIKA / JOMAR',
    'Der': 'DER',
}
TEAM_NAMES = ['JASON / SHILA', 'RON / ADRIAN', 'MIKA / JOMAR', 'DER']

CHANNEL_TEAM_MAP = {
    'DEERPROMO01': 'MIKA / JOMAR', 'DEERPROMO02': 'RON / ADRIAN',
    'DEERPROMO03': 'MIKA / JOMAR', 'DEERPROMO04': 'RON / ADRIAN',
    'DEERPROMO05': 'JASON / SHILA', 'DEERPROMO06': 'MIKA / JOMAR',
    'DEERPROMO07': 'RON / ADRIAN', 'DEERPROMO08': 'MIKA / JOMAR',
    'DEERPROMO09': 'DER', 'DEERPROMO10': 'RON / ADRIAN',
    'DEERPROMO11': 'JASON / SHILA', 'DEERPROMO12': 'JASON / SHILA',
    'DEERPROMO13': 'JASON / SHILA', 'DEERPROMO14': 'DER',
    'DEERPROMO15': 'JASON / SHILA', 'DEERPROMO16': 'JASON / SHILA',
    'DEERPROMO17': 'MIKA / JOMAR',
}


# ── Mon-Sun week helpers ──────────────────────────────────────────
def get_week_key(date):
    """Return (week_key, week_start_monday, week_end_sunday) for a date using Mon-Sun weeks."""
    dt = pd.Timestamp(date)
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    iso = monday.isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"
    return week_key, monday, sunday


def week_label(monday, sunday):
    return f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')}"


# ── Weekly aggregation ─────────────────────────────────────────────
def build_weekly_data(daily_df):
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df[df['date'] <= pd.Timestamp.now()]  # exclude future dates

    # Assign week info
    week_info = df['date'].apply(lambda d: get_week_key(d))
    df['week_key'] = week_info.apply(lambda x: x[0])
    df['week_start'] = week_info.apply(lambda x: x[1])
    df['week_end'] = week_info.apply(lambda x: x[2])

    agg = df.groupby(['agent', 'week_key']).agg(
        cost=('cost', 'sum'),
        register=('register', 'sum'),
        ftd=('ftd', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
        days=('date', 'nunique'),
        week_start=('week_start', 'first'),
        week_end=('week_end', 'first'),
    ).reset_index()

    # ARPPU: last non-zero value per agent per week
    arppu_rows = []
    for (agent, wk), grp in df.groupby(['agent', 'week_key']):
        grp_sorted = grp.sort_values('date')
        arppu_col = pd.to_numeric(grp_sorted['arppu'], errors='coerce').fillna(0)
        nonzero = arppu_col[arppu_col > 0]
        arppu_rows.append({'agent': agent, 'week_key': wk, 'arppu': nonzero.iloc[-1] if len(nonzero) > 0 else 0})
    agg = agg.merge(pd.DataFrame(arppu_rows), on=['agent', 'week_key'], how='left')
    agg['arppu'] = agg['arppu'].fillna(0)

    # Derived metrics
    agg['cpa'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agg['cpr'] = agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
    agg['conv_rate'] = agg.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agg['ctr'] = agg.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)
    agg['roas'] = agg.apply(
        lambda r: r['arppu'] / KPI_PHP_USD_RATE / (r['cost'] / r['ftd']) if r['ftd'] > 0 and r['cost'] > 0 else 0, axis=1)

    agg['team'] = agg['agent'].map(TEAM_MAP).fillna('Unknown')
    agg['week_label'] = agg.apply(lambda r: week_label(r['week_start'], r['week_end']), axis=1)

    return agg.sort_values(['agent', 'week_key'])


def build_weekly_channel_data(daily_df):
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df[df['date'] <= pd.Timestamp.now()]  # exclude future dates

    week_info = df['date'].apply(lambda d: get_week_key(d))
    df['week_key'] = week_info.apply(lambda x: x[0])

    df['channel_clean'] = df['channel'].astype(str).str.extract(r'(DEERPROMO\d+)', expand=False)
    df = df.dropna(subset=['channel_clean'])

    agg = df.groupby(['channel_clean', 'week_key']).agg(
        cost=('cost', 'sum'),
        register=('register', 'sum'),
        ftd=('ftd', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
    ).reset_index()

    agg['cpa'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agg['conv_rate'] = agg.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agg['ctr'] = agg.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)
    agg['team'] = agg['channel_clean'].map(CHANNEL_TEAM_MAP).fillna('Unknown')

    return agg


# ── Display helpers ──────────────────────────────────────────────────
def delta_html(curr, prev, higher_is_better=True):
    if prev == 0 and curr == 0:
        return '<span style="color:#64748b">--</span>'
    if prev == 0:
        return '<span style="color:#22c55e">new</span>'
    pct = (curr - prev) / abs(prev) * 100
    if abs(pct) < 0.1:
        return '<span style="color:#64748b">0%</span>'
    is_good = (pct > 0) == higher_is_better
    color = '#16a34a' if is_good else '#dc2626'
    arrow = '&#9650;' if pct > 0 else '&#9660;'
    return f'<span style="color:{color};font-weight:600">{arrow} {abs(pct):.1f}%</span>'


def fmt_cost(v): return f"${v:,.2f}" if v else "$0.00"
def fmt_num(v): return f"{int(v):,}" if v else "0"
def fmt_pct(v): return f"{v:.2f}%" if v else "0.00%"
def fmt_roas(v): return f"{v:.4f}x" if v else "0.0000x"
def md_cost(v): return f"\\${v:,.2f}" if v else "\\$0.00"
def md_num(v): return f"{int(v):,}" if v else "0"
def md_pct(v): return f"{v:.2f}%" if v else "0.00%"
def md_roas(v): return f"{v:.4f}x" if v else "0.0000x"


METRIC_CONFIG = {
    'cost': {'label': 'Cost (USD)', 'fmt': fmt_cost, 'hib': True},
    'register': {'label': 'Register', 'fmt': fmt_num, 'hib': True},
    'ftd': {'label': 'FTD', 'fmt': fmt_num, 'hib': True},
    'cpa': {'label': 'CPA', 'fmt': fmt_cost, 'hib': False},
    'cpr': {'label': 'CPR', 'fmt': fmt_cost, 'hib': False},
    'roas': {'label': 'ROAS', 'fmt': fmt_roas, 'hib': True},
    'ctr': {'label': 'CTR', 'fmt': fmt_pct, 'hib': True},
    'conv_rate': {'label': 'Conv Rate', 'fmt': fmt_pct, 'hib': True},
    'impressions': {'label': 'Impressions', 'fmt': fmt_num, 'hib': True},
    'clicks': {'label': 'Clicks', 'fmt': fmt_num, 'hib': True},
    'arppu': {'label': 'ARPPU', 'fmt': lambda v: f"PHP {v:,.2f}" if v else "PHP 0.00", 'hib': True},
}

TH = 'padding:8px 10px;text-align:center;border:1px solid #cbd5e1;font-size:13px'
TD = 'padding:6px 10px;text-align:center;border:1px solid #cbd5e1;font-size:13px'


def aggregate_rows(df, week_key):
    rows = df[df['week_key'] == week_key]
    if rows.empty:
        return {}
    return {
        'cost': rows['cost'].sum(),
        'register': rows['register'].sum(),
        'ftd': rows['ftd'].sum(),
        'impressions': rows['impressions'].sum(),
        'clicks': rows['clicks'].sum(),
        'arppu': rows['arppu'].mean(),
        'cpa': rows['cost'].sum() / rows['ftd'].sum() if rows['ftd'].sum() > 0 else 0,
        'cpr': rows['cost'].sum() / rows['register'].sum() if rows['register'].sum() > 0 else 0,
        'conv_rate': rows['ftd'].sum() / rows['register'].sum() * 100 if rows['register'].sum() > 0 else 0,
        'ctr': rows['clicks'].sum() / rows['impressions'].sum() * 100 if rows['impressions'].sum() > 0 else 0,
        'roas': (rows['arppu'].mean() / KPI_PHP_USD_RATE / (rows['cost'].sum() / rows['ftd'].sum())
                 if rows['ftd'].sum() > 0 and rows['cost'].sum() > 0 else 0),
    }


def _pct_change(curr, prev):
    if prev == 0:
        return None
    return (curr - prev) / abs(prev) * 100


def _direction_word(pct, higher_is_better):
    if pct is None:
        return "unchanged"
    magnitude = abs(pct)
    if magnitude < 1:
        return "remained stable"
    strength = "slightly " if magnitude < 10 else ("significantly " if magnitude > 30 else "")
    direction = "increased" if pct > 0 else "decreased"
    return f"{strength}{direction} by {magnitude:.1f}%"


# ══════════════════════════════════════════════════════════════════════
# Tab 1: Overview
# ══════════════════════════════════════════════════════════════════════
def render_overview(weekly, weeks, sel_week, prev_week, week_labels_map):
    curr = aggregate_rows(weekly, sel_week)
    prev = aggregate_rows(weekly, prev_week) if prev_week else {}

    if not curr:
        st.warning("No data for selected week.")
        return

    # Summary cards
    card_metrics = ['cost', 'ftd', 'cpa', 'roas', 'ctr', 'conv_rate']
    cols = st.columns(len(card_metrics))
    for i, m in enumerate(card_metrics):
        mc = METRIC_CONFIG[m]
        with cols[i]:
            val = curr.get(m, 0)
            prev_val = prev.get(m, 0)
            delta = None
            delta_color = "inverse" if not mc['hib'] else "normal"
            if prev_val and prev_val != 0:
                pct = (val - prev_val) / abs(prev_val) * 100
                delta = f"{pct:+.1f}% WoW"
            st.metric(mc['label'], mc['fmt'](val), delta, delta_color=delta_color)

    # Full WoW comparison table
    st.markdown("#### Week-over-Week Comparison")
    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Metric</th>'
    if prev_week:
        html += f'<th style="{TH}">{week_labels_map.get(prev_week, prev_week)}</th>'
    html += f'<th style="{TH}">{week_labels_map.get(sel_week, sel_week)}</th>'
    if prev_week:
        html += f'<th style="{TH}">WoW</th>'
    html += '</tr>'

    for m, mc in METRIC_CONFIG.items():
        c_val = curr.get(m, 0)
        p_val = prev.get(m, 0)
        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{mc["label"]}</td>'
        if prev_week:
            html += f'<td style="{TD}">{mc["fmt"](p_val)}</td>'
        html += f'<td style="{TD};font-weight:600">{mc["fmt"](c_val)}</td>'
        if prev_week:
            html += f'<td style="{TD}">{delta_html(c_val, p_val, mc["hib"])}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Top / bottom performers
    week_data = weekly[weekly['week_key'] == sel_week]
    if not week_data.empty and len(week_data) > 1:
        st.markdown("#### Top & Bottom Performers")
        for metric, label, hib in [('cpa', 'CPA', False), ('roas', 'ROAS', True), ('conv_rate', 'Conv Rate', True)]:
            mc = METRIC_CONFIG[metric]
            best = week_data.loc[week_data[metric].idxmax()] if hib else week_data.loc[week_data[metric].idxmin()]
            worst = week_data.loc[week_data[metric].idxmin()] if hib else week_data.loc[week_data[metric].idxmax()]
            if len(week_data) > 1:
                c1, c2 = st.columns(2)
                with c1:
                    st.success(f"Best {label}: **{best['agent']}** ({mc['fmt'](best[metric])})")
                with c2:
                    st.error(f"Worst {label}: **{worst['agent']}** ({mc['fmt'](worst[metric])})")


# ══════════════════════════════════════════════════════════════════════
# Tab 2: Agent Breakdown
# ══════════════════════════════════════════════════════════════════════
def render_agents(weekly, sel_week, prev_week, week_labels_map):
    week_data = weekly[weekly['week_key'] == sel_week].sort_values('agent')
    if week_data.empty:
        st.warning("No agent data for selected week.")
        return

    prev_data = weekly[weekly['week_key'] == prev_week] if prev_week else pd.DataFrame()

    st.markdown("#### Agent Comparison")
    display_metrics = ['cost', 'register', 'ftd', 'cpa', 'cpr', 'roas', 'ctr', 'conv_rate', 'arppu']

    html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Agent</th>'
    for m in display_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for _, r in week_data.iterrows():
        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:700">{r["agent"]}</td>'
        for m in display_metrics:
            mc = METRIC_CONFIG[m]
            val = r[m]
            cell = mc['fmt'](val)
            if not prev_data.empty:
                prev_row = prev_data[prev_data['agent'] == r['agent']]
                if not prev_row.empty:
                    p_val = prev_row.iloc[0][m]
                    cell += f' <span style="font-size:11px">{delta_html(val, p_val, mc["hib"])}</span>'
            html += f'<td style="{TD}">{cell}</td>'
        html += '</tr>'
    html += '</table></div>'
    st.markdown(html, unsafe_allow_html=True)

    # Rankings
    st.markdown("#### Rankings")
    rank_metrics = [('cpa', False), ('roas', True), ('conv_rate', True), ('ctr', True)]
    rank_cols = st.columns(len(rank_metrics))
    medal = ['#fbbf24', '#94a3b8', '#cd7f32']

    for i, (metric, ascending_is_bad) in enumerate(rank_metrics):
        mc = METRIC_CONFIG[metric]
        sorted_df = week_data.sort_values(metric, ascending=not ascending_is_bad)
        with rank_cols[i]:
            st.markdown(f"**{mc['label']}**")
            rank_html = ''
            for j, (_, row) in enumerate(sorted_df.iterrows()):
                color = medal[j] if j < 3 else '#64748b'
                rank_html += f'<div style="padding:4px 0;color:#1e293b"><span style="color:{color};font-weight:bold">#{j+1}</span> {row["agent"]} -- {mc["fmt"](row[metric])}</div>'
            st.markdown(rank_html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# Tab 3: Team Breakdown
# ══════════════════════════════════════════════════════════════════════
def render_teams(weekly, channel_weekly, sel_week, prev_week, week_labels_map):
    week_data = weekly[weekly['week_key'] == sel_week]
    if week_data.empty:
        st.warning("No data for selected week.")
        return

    prev_data = weekly[weekly['week_key'] == prev_week] if prev_week else pd.DataFrame()

    st.markdown("#### Team Summary")
    team_metrics = ['cost', 'ftd', 'cpa', 'roas', 'conv_rate', 'ctr']

    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Team</th>'
    for m in team_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for team_name in TEAM_NAMES:
        team_rows = week_data[week_data['team'] == team_name]
        if team_rows.empty:
            continue
        totals = {
            'cost': team_rows['cost'].sum(), 'ftd': team_rows['ftd'].sum(),
            'register': team_rows['register'].sum(),
            'impressions': team_rows['impressions'].sum(),
            'clicks': team_rows['clicks'].sum(), 'arppu': team_rows['arppu'].mean(),
        }
        totals['cpa'] = totals['cost'] / totals['ftd'] if totals['ftd'] > 0 else 0
        totals['conv_rate'] = totals['ftd'] / totals['register'] * 100 if totals['register'] > 0 else 0
        totals['ctr'] = totals['clicks'] / totals['impressions'] * 100 if totals['impressions'] > 0 else 0
        totals['roas'] = (totals['arppu'] / KPI_PHP_USD_RATE / (totals['cost'] / totals['ftd'])
                          if totals['ftd'] > 0 and totals['cost'] > 0 else 0)

        prev_totals = {}
        if not prev_data.empty:
            prev_team = prev_data[prev_data['team'] == team_name]
            if not prev_team.empty:
                prev_totals = {
                    'cost': prev_team['cost'].sum(), 'ftd': prev_team['ftd'].sum(),
                    'register': prev_team['register'].sum(),
                    'impressions': prev_team['impressions'].sum(),
                    'clicks': prev_team['clicks'].sum(), 'arppu': prev_team['arppu'].mean(),
                }
                prev_totals['cpa'] = prev_totals['cost'] / prev_totals['ftd'] if prev_totals['ftd'] > 0 else 0
                prev_totals['conv_rate'] = prev_totals['ftd'] / prev_totals['register'] * 100 if prev_totals['register'] > 0 else 0
                prev_totals['ctr'] = prev_totals['clicks'] / prev_totals['impressions'] * 100 if prev_totals['impressions'] > 0 else 0
                prev_totals['roas'] = (prev_totals['arppu'] / KPI_PHP_USD_RATE / (prev_totals['cost'] / prev_totals['ftd'])
                                       if prev_totals['ftd'] > 0 and prev_totals['cost'] > 0 else 0)

        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:700">{team_name}</td>'
        for m in team_metrics:
            mc = METRIC_CONFIG[m]
            val = totals.get(m, 0)
            cell = mc['fmt'](val)
            if prev_totals:
                p_val = prev_totals.get(m, 0)
                cell += f' <span style="font-size:11px">{delta_html(val, p_val, mc["hib"])}</span>'
            html += f'<td style="{TD}">{cell}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Team distribution pies
    st.markdown("#### Team Distribution")
    c1, c2 = st.columns(2)
    team_cost = [week_data[week_data['team'] == tn]['cost'].sum() for tn in TEAM_NAMES]
    team_ftd = [week_data[week_data['team'] == tn]['ftd'].sum() for tn in TEAM_NAMES]
    colors = ['#3b82f6', '#22c55e', '#f59e0b']

    with c1:
        fig = go.Figure(go.Pie(labels=TEAM_NAMES, values=team_cost, marker_colors=colors,
                               textinfo='label+percent', textposition='inside'))
        fig.update_layout(title='Cost Distribution', height=350, margin=dict(t=40, b=20), font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_team_cost_pie")
    with c2:
        fig = go.Figure(go.Pie(labels=TEAM_NAMES, values=team_ftd, marker_colors=colors,
                               textinfo='label+percent', textposition='inside'))
        fig.update_layout(title='FTD Distribution', height=350, margin=dict(t=40, b=20), font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_team_ftd_pie")

    # Channel breakdown
    if not channel_weekly.empty:
        ch_week = channel_weekly[channel_weekly['week_key'] == sel_week]
        if not ch_week.empty:
            st.markdown("#### Channel Breakdown (DEERPROMO)")
            ch_metrics = ['cost', 'ftd', 'cpa', 'conv_rate', 'ctr']
            html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:8px 0">'
            html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Channel</th><th style="{TH}">Team</th>'
            for m in ch_metrics:
                html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
            html += '</tr>'
            for _, r in ch_week.sort_values('channel_clean').iterrows():
                html += f'<tr style="background:#ffffff;color:#1e293b">'
                html += f'<td style="{TD};font-weight:600">{r["channel_clean"]}</td>'
                html += f'<td style="{TD}">{r.get("team", "")}</td>'
                for m in ch_metrics:
                    mc = METRIC_CONFIG[m]
                    html += f'<td style="{TD}">{mc["fmt"](r[m])}</td>'
                html += '</tr>'
            html += '</table></div>'
            st.markdown(html, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# Tab 4: Trends
# ══════════════════════════════════════════════════════════════════════
def render_trends(weekly, weeks, week_labels_map):
    if len(weeks) < 2:
        st.info("Need at least 2 weeks of data to show trends.")
        return

    week_totals = []
    for wk in weeks:
        totals = aggregate_rows(weekly, wk)
        if totals:
            totals['week_key'] = wk
            totals['week_label'] = week_labels_map.get(wk, wk)
            week_totals.append(totals)
    if not week_totals:
        return
    wt_df = pd.DataFrame(week_totals)

    # Cost + FTD bar chart
    st.markdown("#### Cost & FTD Trend")
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Cost (USD)', x=wt_df['week_label'], y=wt_df['cost'], marker_color='#3b82f6', yaxis='y'))
    fig.add_trace(go.Bar(name='FTD', x=wt_df['week_label'], y=wt_df['ftd'], marker_color='#22c55e', yaxis='y2'))
    fig.update_layout(
        yaxis=dict(title='Cost (USD)', titlefont_color='#3b82f6', tickfont_color='#3b82f6'),
        yaxis2=dict(title='FTD', titlefont_color='#22c55e', tickfont_color='#22c55e', overlaying='y', side='right'),
        barmode='group', height=400, margin=dict(t=30, b=40),
        legend=dict(orientation='h', y=1.1), font=dict(color='#1e293b'),
        plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff',
    )
    st.plotly_chart(fig, use_container_width=True, key="wa_trend_cost_ftd")

    # CPA + ROAS line chart
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### CPA Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=wt_df['week_label'], y=wt_df['cpa'], mode='lines+markers',
                                 name='CPA', line=dict(color='#ef4444', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='CPA (USD)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_trend_cpa")
    with c2:
        st.markdown("#### ROAS Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=wt_df['week_label'], y=wt_df['roas'], mode='lines+markers',
                                 name='ROAS', line=dict(color='#22c55e', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='ROAS'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_trend_roas")

    # CTR + Conv Rate
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### CTR Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=wt_df['week_label'], y=wt_df['ctr'], mode='lines+markers',
                                 name='CTR', line=dict(color='#8b5cf6', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='CTR (%)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_trend_ctr")
    with c2:
        st.markdown("#### Conv Rate Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=wt_df['week_label'], y=wt_df['conv_rate'], mode='lines+markers',
                                 name='Conv Rate', line=dict(color='#f59e0b', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='Conv Rate (%)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_trend_conv")

    # Agent trend selector
    st.divider()
    st.markdown("#### Agent Weekly Trends")
    sel_agent = st.selectbox("Select Agent", AGENTS_LIST, key="wa_trend_agent")
    sel_metric = st.selectbox("Select Metric", list(METRIC_CONFIG.keys()), key="wa_trend_metric",
                              format_func=lambda m: METRIC_CONFIG[m]['label'])

    agent_data = weekly[weekly['agent'] == sel_agent].sort_values('week_key')
    if not agent_data.empty:
        mc = METRIC_CONFIG[sel_metric]
        agent_data = agent_data.copy()
        agent_data['wl'] = agent_data['week_key'].map(week_labels_map)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=agent_data['wl'], y=agent_data[sel_metric],
            mode='lines+markers+text', name=sel_agent,
            text=[mc['fmt'](v) for v in agent_data[sel_metric]],
            textposition='top center',
            line=dict(color='#3b82f6', width=3), marker=dict(size=10),
        ))
        fig.update_layout(yaxis=dict(title=mc['label']), height=400, margin=dict(t=30, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="wa_agent_trend_chart")

    # Heatmap
    st.divider()
    st.markdown("#### Agent x Week Heatmap")
    hm_metric = st.selectbox("Heatmap Metric", ['cpa', 'roas', 'conv_rate', 'ctr'],
                             key="wa_hm_metric", format_func=lambda m: METRIC_CONFIG[m]['label'])

    pivot = weekly.pivot_table(index='agent', columns='week_key', values=hm_metric, aggfunc='first')
    pivot = pivot.reindex(columns=weeks)

    mc = METRIC_CONFIG[hm_metric]
    colorscale = 'RdYlGn' if mc['hib'] else 'RdYlGn_r'
    col_labels = [week_labels_map.get(wk, wk) for wk in weeks]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=col_labels, y=pivot.index.tolist(),
        text=[[mc['fmt'](v) if pd.notna(v) else '-' for v in row] for row in pivot.values],
        texttemplate='%{text}', colorscale=colorscale,
        hovertemplate='Agent: %{y}<br>Week: %{x}<br>Value: %{text}<extra></extra>',
    ))
    fig.update_layout(height=max(300, len(pivot) * 50), margin=dict(t=20, b=40),
                      plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'),
                      xaxis=dict(title='Week'), yaxis=dict(title='Agent', autorange='reversed'))
    st.plotly_chart(fig, use_container_width=True, key="wa_heatmap")


# ══════════════════════════════════════════════════════════════════════
# Tab 5: Analysis & Insights
# ══════════════════════════════════════════════════════════════════════
def render_analysis(weekly, channel_weekly, weeks, sel_week, prev_week, week_labels_map):
    curr = aggregate_rows(weekly, sel_week)
    prev = aggregate_rows(weekly, prev_week) if prev_week else {}
    week_data = weekly[weekly['week_key'] == sel_week]
    prev_data = weekly[weekly['week_key'] == prev_week] if prev_week else pd.DataFrame()

    if not curr:
        st.warning("No data for analysis.")
        return

    sel_label = week_labels_map.get(sel_week, sel_week)
    prev_label = week_labels_map.get(prev_week, prev_week) if prev_week else None

    # 1. Executive Summary
    st.markdown("### Executive Summary")
    parts = []
    parts.append(f"In the week of **{sel_label}**, the team spent **{md_cost(curr['cost'])}** "
                 f"generating **{md_num(curr['ftd'])} FTDs** from **{md_num(curr['register'])} registrations**.")

    if prev:
        cost_pct = _pct_change(curr['cost'], prev['cost'])
        ftd_pct = _pct_change(curr['ftd'], prev['ftd'])
        cpa_pct = _pct_change(curr['cpa'], prev['cpa'])
        roas_pct = _pct_change(curr['roas'], prev['roas'])

        parts.append(f"Compared to **{prev_label}**, ad spend {_direction_word(cost_pct, False)} "
                     f"while FTD volume {_direction_word(ftd_pct, True)}.")
        parts.append(f"CPA {_direction_word(cpa_pct, False)} to **{md_cost(curr['cpa'])}** "
                     f"and ROAS {_direction_word(roas_pct, True)} to **{md_roas(curr['roas'])}**.")

        conv_pct = _pct_change(curr['conv_rate'], prev['conv_rate'])
        ctr_pct = _pct_change(curr['ctr'], prev['ctr'])
        parts.append(f"Conversion rate {_direction_word(conv_pct, True)} at **{md_pct(curr['conv_rate'])}** "
                     f"and CTR {_direction_word(ctr_pct, True)} at **{md_pct(curr['ctr'])}**.")

    st.markdown(" ".join(parts))

    # 2. Cost Efficiency
    st.markdown("---")
    st.markdown("### Cost Efficiency Analysis")

    if prev:
        cost_change = _pct_change(curr['cost'], prev['cost'])
        ftd_change = _pct_change(curr['ftd'], prev['ftd'])

        if cost_change is not None and ftd_change is not None:
            if ftd_change > cost_change:
                st.success(f"Spend efficiency **improved** -- FTD growth ({ftd_change:+.1f}%) outpaced cost growth ({cost_change:+.1f}%).")
            elif cost_change > 0 and ftd_change <= 0:
                st.error(f"Spend efficiency **declined** -- costs rose ({cost_change:+.1f}%) while FTDs dropped ({ftd_change:+.1f}%).")
            elif cost_change < 0 and ftd_change > 0:
                st.success(f"Excellent -- reduced spend ({cost_change:+.1f}%) while FTDs grew ({ftd_change:+.1f}%).")
            else:
                st.info(f"Spend changed by {cost_change:+.1f}% and FTDs by {ftd_change:+.1f}%. Roughly proportional.")

    cpa_val = curr['cpa']
    if cpa_val > 0:
        if cpa_val < 10:
            st.success(f"CPA at **{md_cost(cpa_val)}** is **excellent** (< \\$10).")
        elif cpa_val < 14:
            st.info(f"CPA at **{md_cost(cpa_val)}** is **good** (\\$10-\\$14). Room for optimization.")
        elif cpa_val <= 15:
            st.warning(f"CPA at **{md_cost(cpa_val)}** is **fair** (\\$14-\\$15). Review underperformers.")
        else:
            st.error(f"CPA at **{md_cost(cpa_val)}** **above target** (> \\$15). Action needed.")

    # 3. Agent Performance
    st.markdown("---")
    st.markdown("### Agent Performance Insights")

    if not week_data.empty and len(week_data) > 1:
        best_cpa = week_data.loc[week_data['cpa'].idxmin()]
        worst_cpa = week_data.loc[week_data['cpa'].idxmax()]
        best_roas = week_data.loc[week_data['roas'].idxmax()]
        worst_roas = week_data.loc[week_data['roas'].idxmin()]
        best_cvr = week_data.loc[week_data['conv_rate'].idxmax()]

        st.markdown(f"- **Top CPA**: {best_cpa['agent']} at {md_cost(best_cpa['cpa'])} vs "
                    f"{worst_cpa['agent']} at {md_cost(worst_cpa['cpa'])}")
        st.markdown(f"- **Best ROAS**: {best_roas['agent']} at {md_roas(best_roas['roas'])}. "
                    f"**Lowest**: {worst_roas['agent']} at {md_roas(worst_roas['roas'])}")
        st.markdown(f"- **Highest conv rate**: {best_cvr['agent']} at {md_pct(best_cvr['conv_rate'])}")

        if not prev_data.empty:
            st.markdown("#### WoW Agent Changes")
            improved = []
            declined = []
            for _, row in week_data.iterrows():
                agent = row['agent']
                prev_row = prev_data[prev_data['agent'] == agent]
                if prev_row.empty:
                    continue
                pr = prev_row.iloc[0]
                cpa_chg = _pct_change(row['cpa'], pr['cpa'])
                roas_chg = _pct_change(row['roas'], pr['roas'])

                if cpa_chg is not None and cpa_chg < -5:
                    improved.append(f"**{agent}**: CPA improved {abs(cpa_chg):.1f}% ({md_cost(pr['cpa'])} -> {md_cost(row['cpa'])})")
                elif cpa_chg is not None and cpa_chg > 10:
                    declined.append(f"**{agent}**: CPA worsened {cpa_chg:.1f}% ({md_cost(pr['cpa'])} -> {md_cost(row['cpa'])})")

                if roas_chg is not None and roas_chg > 10:
                    improved.append(f"**{agent}**: ROAS improved {roas_chg:.1f}% ({md_roas(pr['roas'])} -> {md_roas(row['roas'])})")
                elif roas_chg is not None and roas_chg < -10:
                    declined.append(f"**{agent}**: ROAS declined {abs(roas_chg):.1f}% ({md_roas(pr['roas'])} -> {md_roas(row['roas'])})")

            if improved:
                st.success("**Improvements:**\n" + "\n".join(f"- {x}" for x in improved))
            if declined:
                st.error("**Needs Attention:**\n" + "\n".join(f"- {x}" for x in declined))
            if not improved and not declined:
                st.info("All agents showed relatively stable performance week-over-week.")

    # 4. Team Analysis
    st.markdown("---")
    st.markdown("### Team Analysis")

    for team_name in TEAM_NAMES:
        team_rows = week_data[week_data['team'] == team_name]
        if team_rows.empty:
            continue
        t_cost = team_rows['cost'].sum()
        t_ftd = team_rows['ftd'].sum()
        t_reg = team_rows['register'].sum()
        t_cpa = t_cost / t_ftd if t_ftd > 0 else 0
        t_cvr = t_ftd / t_reg * 100 if t_reg > 0 else 0
        members = ", ".join(team_rows['agent'].tolist())

        team_text = (f"**{team_name}** ({members}): Spent {md_cost(t_cost)}, "
                     f"generated {md_num(t_ftd)} FTDs at {md_cost(t_cpa)} CPA "
                     f"with {md_pct(t_cvr)} conversion rate.")

        if not prev_data.empty:
            pt = prev_data[prev_data['team'] == team_name]
            if not pt.empty:
                pt_cost = pt['cost'].sum()
                pt_ftd = pt['ftd'].sum()
                cost_chg = _pct_change(t_cost, pt_cost)
                ftd_chg = _pct_change(t_ftd, pt_ftd)
                if cost_chg is not None:
                    team_text += f" Cost {_direction_word(cost_chg, False)}, FTD {_direction_word(ftd_chg, True)}."

        st.markdown(f"- {team_text}")

    # 5. Recommendations
    st.markdown("---")
    st.markdown("### Recommendations")
    recs = []

    if prev:
        if curr['cpa'] > prev.get('cpa', 0) and prev.get('cpa', 0) > 0:
            pct = _pct_change(curr['cpa'], prev['cpa'])
            if pct and pct > 10:
                recs.append(f"CPA rose {pct:.1f}% WoW. Review campaign targeting and pause underperforming ad sets.")
        if curr['roas'] < prev.get('roas', 0):
            recs.append("ROAS declined. Focus on improving post-registration deposit rates and ARPPU.")

    if curr['cpa'] > 15:
        recs.append(f"CPA at {md_cost(curr['cpa'])} exceeds \\$15 target. Tighten audiences and test new creatives.")
    if curr['conv_rate'] < 3:
        recs.append(f"Conv rate at {md_pct(curr['conv_rate'])} is low. Review registration-to-FTD funnel.")

    if not week_data.empty:
        max_cpa_agent = week_data.loc[week_data['cpa'].idxmax()]
        min_cpa_agent = week_data.loc[week_data['cpa'].idxmin()]
        if max_cpa_agent['cpa'] > min_cpa_agent['cpa'] * 2 and len(week_data) > 1:
            recs.append(f"Large CPA gap: {max_cpa_agent['agent']} ({md_cost(max_cpa_agent['cpa'])}) vs "
                        f"{min_cpa_agent['agent']} ({md_cost(min_cpa_agent['cpa'])}). "
                        f"Share best practices from top performer.")

    if not recs:
        st.success("Performance looks healthy this week. Continue current strategies.")
    else:
        for i, rec in enumerate(recs, 1):
            st.markdown(f"{i}. {rec}")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    st.title("Weekly Analysis")
    st.caption("Comprehensive weekly ad performance with WoW comparison (Mon-Sun weeks)")

    with st.sidebar:
        st.header("Controls")
        if st.button("Refresh", type="primary", use_container_width=True, key="wa_refresh"):
            refresh_agent_performance_data()
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Loading data..."):
        ptab = load_agent_performance_data()
        daily_df = ptab.get('daily', pd.DataFrame()) if ptab else pd.DataFrame()

    if daily_df is None or daily_df.empty:
        st.error("No P-tab data available.")
        st.stop()

    weekly = build_weekly_data(daily_df)
    channel_weekly = build_weekly_channel_data(daily_df)

    if weekly.empty:
        st.error("No weekly data could be computed.")
        st.stop()

    # Build week selector
    weeks = sorted(weekly['week_key'].unique())
    week_labels_map = {}
    for wk in weeks:
        row = weekly[weekly['week_key'] == wk].iloc[0]
        week_labels_map[wk] = row['week_label']

    weeks_display = list(reversed(weeks))  # newest first
    week_options = [f"{week_labels_map[wk]} ({wk})" for wk in weeks_display]

    with st.sidebar:
        st.markdown("---")
        sel_idx = st.selectbox("Select Week", range(len(week_options)),
                               format_func=lambda i: week_options[i], key="wa_week_sel")
        sel_week = weeks_display[sel_idx]
        prev_week = weeks_display[sel_idx + 1] if sel_idx + 1 < len(weeks_display) else None

        num_weeks = st.selectbox("Trend weeks", [4, 6, 8, 12], index=1, key="wa_num_weeks")

    # Limit trend weeks
    sel_pos = weeks.index(sel_week)
    trend_start = max(0, sel_pos - num_weeks + 1)
    trend_weeks = weeks[trend_start:sel_pos + 1]

    sel_label = week_labels_map.get(sel_week, sel_week)
    prev_label = week_labels_map.get(prev_week, prev_week) if prev_week else None

    st.markdown(f"**Selected:** {sel_label}" + (f" | **Previous:** {prev_label}" if prev_label else ""))

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview", "Agent Breakdown", "Team Breakdown", "Trends", "Analysis & Insights"
    ])

    with tab1:
        render_overview(weekly, trend_weeks, sel_week, prev_week, week_labels_map)
    with tab2:
        render_agents(weekly, sel_week, prev_week, week_labels_map)
    with tab3:
        render_teams(weekly, channel_weekly, sel_week, prev_week, week_labels_map)
    with tab4:
        render_trends(weekly, trend_weeks, week_labels_map)
    with tab5:
        render_analysis(weekly, channel_weekly, trend_weeks, sel_week, prev_week, week_labels_map)


main()
