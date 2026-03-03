"""
Monthly Analysis Dashboard — Comprehensive monthly ad performance with MoM comparison,
per-agent/team breakdowns, FB vs Google channel comparison, and multi-month trends.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
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

AGENTS_LIST = [t['agent'] for t in AGENT_PERFORMANCE_TABS if t['agent'].upper() not in EXCLUDED_FROM_REPORTING]

TEAM_MAP = {
    'Jason': 'JASON / SHILA', 'Shila': 'JASON / SHILA',
    'Ron': 'RON / ADRIAN', 'Adrian': 'RON / ADRIAN',
    'Mika': 'MIKA / JOMAR', 'Jomar': 'MIKA / JOMAR',
    'Der': 'DER (Solo)',
}
TEAM_NAMES = ['JASON / SHILA', 'RON / ADRIAN', 'MIKA / JOMAR']

CHANNEL_TEAM_MAP = {
    'DEERPROMO06': 'MIKA / JOMAR', 'DEERPROMO07': 'RON / ADRIAN',
    'DEERPROMO08': 'MIKA / JOMAR', 'DEERPROMO09': 'JASON / SHILA',
    'DEERPROMO10': 'RON / ADRIAN', 'DEERPROMO11': 'RON / ADRIAN',
    'DEERPROMO12': 'JASON / SHILA', 'DEERPROMO13': 'JASON / SHILA',
}


# ── Monthly aggregation ─────────────────────────────────────────────
def build_monthly_data(daily_df):
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['month_key'] = df['date'].dt.to_period('M').astype(str)

    agg = df.groupby(['agent', 'month_key']).agg(
        cost=('cost', 'sum'),
        register=('register', 'sum'),
        ftd=('ftd', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
        days=('date', 'nunique'),
    ).reset_index()

    # ARPPU: last non-zero value per agent per month
    arppu_rows = []
    for (agent, mk), grp in df.groupby(['agent', 'month_key']):
        grp_sorted = grp.sort_values('date')
        arppu_col = pd.to_numeric(grp_sorted['arppu'], errors='coerce').fillna(0)
        nonzero = arppu_col[arppu_col > 0]
        arppu_rows.append({'agent': agent, 'month_key': mk, 'arppu': nonzero.iloc[-1] if len(nonzero) > 0 else 0})
    agg = agg.merge(pd.DataFrame(arppu_rows), on=['agent', 'month_key'], how='left')
    agg['arppu'] = agg['arppu'].fillna(0)

    # Derived metrics
    agg['cpa'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agg['cpr'] = agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
    agg['conv_rate'] = agg.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agg['ctr'] = agg.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)
    agg['roas'] = agg.apply(
        lambda r: r['arppu'] / KPI_PHP_USD_RATE / (r['cost'] / r['ftd']) if r['ftd'] > 0 and r['cost'] > 0 else 0, axis=1)

    # Team assignment
    agg['team'] = agg['agent'].map(TEAM_MAP).fillna('Unknown')

    return agg.sort_values(['agent', 'month_key'])


def build_monthly_channel_data(daily_df):
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['month_key'] = df['date'].dt.to_period('M').astype(str)

    # Extract DEERPROMO channel name
    df['channel_clean'] = df['channel'].astype(str).str.extract(r'(DEERPROMO\d+)', expand=False)
    df = df.dropna(subset=['channel_clean'])

    agg = df.groupby(['channel_clean', 'month_key']).agg(
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


# ── FB vs Google monthly aggregation ──────────────────────────────────
def build_platform_monthly(fb_data, google_data):
    """Build monthly aggregation for FB and Google across all 3 attribution windows."""
    results = {}

    for section_key in ['daily_roi', 'roll_back', 'violet']:
        rows = []
        for platform_label, data_dict in [('Facebook', fb_data), ('Google', google_data)]:
            df = data_dict.get(section_key, pd.DataFrame())
            if df.empty or 'date' not in df.columns:
                continue
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])
            df['month_key'] = df['date'].dt.to_period('M').astype(str)

            for mk, grp in df.groupby('month_key'):
                cost = pd.to_numeric(grp.get('cost', 0), errors='coerce').fillna(0).sum()
                register = pd.to_numeric(grp.get('register', 0), errors='coerce').fillna(0).sum()
                ftd = pd.to_numeric(grp.get('ftd', 0), errors='coerce').fillna(0).sum()
                deposit = pd.to_numeric(grp.get('deposit_amount', grp.get('ftd_recharge', 0)), errors='coerce').fillna(0).sum()
                avg_rech = pd.to_numeric(grp.get('avg_recharge', 0), errors='coerce').fillna(0)
                avg_rech = avg_rech[avg_rech > 0]
                arppu = avg_rech.mean() if len(avg_rech) > 0 else 0

                cpa = cost / ftd if ftd > 0 else 0
                roas = arppu / KPI_PHP_USD_RATE / cpa if cpa > 0 else 0

                rows.append({
                    'platform': platform_label,
                    'month_key': mk,
                    'cost': cost,
                    'register': int(register),
                    'ftd': int(ftd),
                    'deposit': deposit,
                    'arppu': arppu,
                    'cpr': cost / register if register > 0 else 0,
                    'cpftd': cpa,
                    'conv_rate': ftd / register * 100 if register > 0 else 0,
                    'roas': roas,
                    'days': grp['date'].dt.date.nunique(),
                })

        results[section_key] = pd.DataFrame(rows) if rows else pd.DataFrame()

    return results


# ── Display helpers ──────────────────────────────────────────────────
def delta_html(curr, prev, higher_is_better=True):
    if prev == 0 and curr == 0:
        return '<span style="color:#64748b">—</span>'
    if prev == 0:
        return '<span style="color:#22c55e">▲ new</span>'
    pct = (curr - prev) / abs(prev) * 100
    if abs(pct) < 0.1:
        return '<span style="color:#64748b">→ 0%</span>'
    is_good = (pct > 0) == higher_is_better
    color = '#16a34a' if is_good else '#dc2626'
    arrow = '▲' if pct > 0 else '▼'
    return f'<span style="color:{color};font-weight:600">{arrow} {abs(pct):.1f}%</span>'


def fmt_cost(v):
    return f"${v:,.2f}" if v else "$0.00"


def fmt_num(v):
    return f"{int(v):,}" if v else "0"


def fmt_pct(v):
    return f"{v:.2f}%" if v else "0.00%"


def fmt_roas(v):
    return f"{v:.4f}x" if v else "0.0000x"


# Markdown-safe formatters (escape $ to avoid LaTeX rendering in st.markdown)
def md_cost(v):
    return f"\\${v:,.2f}" if v else "\\$0.00"


def md_num(v):
    return f"{int(v):,}" if v else "0"


def md_pct(v):
    return f"{v:.2f}%" if v else "0.00%"


def md_roas(v):
    return f"{v:.4f}x" if v else "0.0000x"


def md_deposit(v):
    return f"₱{v:,.0f}" if v else "₱0"


METRIC_CONFIG = {
    'cost': {'label': 'Cost (USD)', 'fmt': fmt_cost, 'hib': False},
    'register': {'label': 'Register', 'fmt': fmt_num, 'hib': True},
    'ftd': {'label': 'FTD', 'fmt': fmt_num, 'hib': True},
    'cpa': {'label': 'CPA', 'fmt': fmt_cost, 'hib': False},
    'cpr': {'label': 'CPR', 'fmt': fmt_cost, 'hib': False},
    'roas': {'label': 'ROAS', 'fmt': fmt_roas, 'hib': True},
    'ctr': {'label': 'CTR', 'fmt': fmt_pct, 'hib': True},
    'conv_rate': {'label': 'Conv Rate', 'fmt': fmt_pct, 'hib': True},
    'impressions': {'label': 'Impressions', 'fmt': fmt_num, 'hib': True},
    'clicks': {'label': 'Clicks', 'fmt': fmt_num, 'hib': True},
    'arppu': {'label': 'ARPPU', 'fmt': lambda v: f"₱{v:,.2f}" if v else "₱0.00", 'hib': True},
}

TH = 'padding:8px 10px;text-align:center;border:1px solid #cbd5e1;font-size:13px'
TD = 'padding:6px 10px;text-align:center;border:1px solid #cbd5e1;font-size:13px'


def aggregate_rows(df, month_key):
    rows = df[df['month_key'] == month_key]
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


# ── Tab 1: Overview ─────────────────────────────────────────────────
def render_overview(monthly, months, sel_month, prev_month):
    curr = aggregate_rows(monthly, sel_month)
    prev = aggregate_rows(monthly, prev_month) if prev_month else {}

    if not curr:
        st.warning("No data for selected month.")
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
                delta = f"{pct:+.1f}% MoM"
            st.metric(mc['label'], mc['fmt'](val), delta, delta_color=delta_color)

    # Full MoM comparison table
    st.markdown("#### Month-over-Month Comparison")
    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Metric</th>'
    if prev_month:
        html += f'<th style="{TH}">{prev_month}</th>'
    html += f'<th style="{TH}">{sel_month}</th>'
    if prev_month:
        html += f'<th style="{TH}">Δ MoM</th>'
    html += '</tr>'

    for m, mc in METRIC_CONFIG.items():
        c_val = curr.get(m, 0)
        p_val = prev.get(m, 0)
        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{mc["label"]}</td>'
        if prev_month:
            html += f'<td style="{TD}">{mc["fmt"](p_val)}</td>'
        html += f'<td style="{TD};font-weight:600">{mc["fmt"](c_val)}</td>'
        if prev_month:
            html += f'<td style="{TD}">{delta_html(c_val, p_val, mc["hib"])}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Top / bottom performers
    if not monthly[monthly['month_key'] == sel_month].empty:
        st.markdown("#### Top & Bottom Performers")
        month_data = monthly[monthly['month_key'] == sel_month]
        for metric, label, hib in [('cpa', 'CPA', False), ('roas', 'ROAS', True), ('conv_rate', 'Conv Rate', True)]:
            mc = METRIC_CONFIG[metric]
            best = month_data.loc[month_data[metric].idxmax()] if hib else month_data.loc[month_data[metric].idxmin()]
            worst = month_data.loc[month_data[metric].idxmin()] if hib else month_data.loc[month_data[metric].idxmax()]
            # Skip if best/worst are same agent
            if len(month_data) > 1:
                best_txt = f"**{best['agent']}** ({mc['fmt'](best[metric])})"
                worst_txt = f"**{worst['agent']}** ({mc['fmt'](worst[metric])})"
                c1, c2 = st.columns(2)
                with c1:
                    st.success(f"Best {label}: {best_txt}")
                with c2:
                    st.error(f"Worst {label}: {worst_txt}")


# ── Tab 2: Agent Breakdown ──────────────────────────────────────────
def render_agents(monthly, months, sel_month, prev_month):
    month_data = monthly[monthly['month_key'] == sel_month].sort_values('agent')
    if month_data.empty:
        st.warning("No agent data for selected month.")
        return

    prev_data = monthly[monthly['month_key'] == prev_month] if prev_month else pd.DataFrame()

    # Agent comparison table
    st.markdown("#### Agent Comparison")
    display_metrics = ['cost', 'register', 'ftd', 'cpa', 'cpr', 'roas', 'ctr', 'conv_rate', 'arppu']

    html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Agent</th>'
    for m in display_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for _, r in month_data.iterrows():
        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:700">{r["agent"]}</td>'
        for m in display_metrics:
            mc = METRIC_CONFIG[m]
            val = r[m]
            cell = mc['fmt'](val)
            # Add MoM delta if available
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
    medal = ['#fbbf24', '#94a3b8', '#cd7f32']  # gold, silver, bronze

    for i, (metric, ascending_is_bad) in enumerate(rank_metrics):
        mc = METRIC_CONFIG[metric]
        sorted_df = month_data.sort_values(metric, ascending=not ascending_is_bad)
        with rank_cols[i]:
            st.markdown(f"**{mc['label']}**")
            rank_html = ''
            for j, (_, row) in enumerate(sorted_df.iterrows()):
                color = medal[j] if j < 3 else '#64748b'
                rank_html += f'<div style="padding:4px 0;color:#1e293b"><span style="color:{color};font-weight:bold">#{j+1}</span> {row["agent"]} — {mc["fmt"](row[metric])}</div>'
            st.markdown(rank_html, unsafe_allow_html=True)


# ── Tab 3: Team Breakdown ───────────────────────────────────────────
def render_teams(monthly, channel_monthly, months, sel_month, prev_month):
    month_data = monthly[monthly['month_key'] == sel_month]
    if month_data.empty:
        st.warning("No data for selected month.")
        return

    prev_data = monthly[monthly['month_key'] == prev_month] if prev_month else pd.DataFrame()

    # Team summary table
    st.markdown("#### Team Summary")
    team_metrics = ['cost', 'ftd', 'cpa', 'roas', 'conv_rate', 'ctr']

    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Team</th>'
    for m in team_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for team_name in TEAM_NAMES:
        team_rows = month_data[month_data['team'] == team_name]
        if team_rows.empty:
            continue
        totals = {
            'cost': team_rows['cost'].sum(),
            'ftd': team_rows['ftd'].sum(),
            'register': team_rows['register'].sum(),
            'impressions': team_rows['impressions'].sum(),
            'clicks': team_rows['clicks'].sum(),
            'arppu': team_rows['arppu'].mean(),
        }
        totals['cpa'] = totals['cost'] / totals['ftd'] if totals['ftd'] > 0 else 0
        totals['conv_rate'] = totals['ftd'] / totals['register'] * 100 if totals['register'] > 0 else 0
        totals['ctr'] = totals['clicks'] / totals['impressions'] * 100 if totals['impressions'] > 0 else 0
        totals['roas'] = (totals['arppu'] / KPI_PHP_USD_RATE / (totals['cost'] / totals['ftd'])
                          if totals['ftd'] > 0 and totals['cost'] > 0 else 0)

        # Prev month team totals for MoM
        prev_totals = {}
        if not prev_data.empty:
            prev_team = prev_data[prev_data['team'] == team_name]
            if not prev_team.empty:
                prev_totals = {
                    'cost': prev_team['cost'].sum(),
                    'ftd': prev_team['ftd'].sum(),
                    'register': prev_team['register'].sum(),
                    'impressions': prev_team['impressions'].sum(),
                    'clicks': prev_team['clicks'].sum(),
                    'arppu': prev_team['arppu'].mean(),
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

    # Team share pie charts
    st.markdown("#### Team Distribution")
    c1, c2 = st.columns(2)

    team_cost = []
    team_ftd = []
    for tn in TEAM_NAMES:
        tr = month_data[month_data['team'] == tn]
        team_cost.append(tr['cost'].sum())
        team_ftd.append(tr['ftd'].sum())

    colors = ['#3b82f6', '#22c55e', '#f59e0b']
    with c1:
        fig = go.Figure(go.Pie(labels=TEAM_NAMES, values=team_cost, marker_colors=colors,
                               textinfo='label+percent', textposition='inside'))
        fig.update_layout(title='Cost Distribution', height=350, margin=dict(t=40, b=20),
                          font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="team_cost_pie")
    with c2:
        fig = go.Figure(go.Pie(labels=TEAM_NAMES, values=team_ftd, marker_colors=colors,
                               textinfo='label+percent', textposition='inside'))
        fig.update_layout(title='FTD Distribution', height=350, margin=dict(t=40, b=20),
                          font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="team_ftd_pie")

    # Per-channel breakdown
    if not channel_monthly.empty:
        ch_month = channel_monthly[channel_monthly['month_key'] == sel_month]
        if not ch_month.empty:
            st.markdown("#### Channel Breakdown (DEERPROMO)")
            ch_metrics = ['cost', 'ftd', 'cpa', 'conv_rate', 'ctr']
            html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:8px 0">'
            html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Channel</th><th style="{TH}">Team</th>'
            for m in ch_metrics:
                html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
            html += '</tr>'

            for _, r in ch_month.sort_values('channel_clean').iterrows():
                html += f'<tr style="background:#ffffff;color:#1e293b">'
                html += f'<td style="{TD};font-weight:600">{r["channel_clean"]}</td>'
                html += f'<td style="{TD}">{r.get("team", "")}</td>'
                for m in ch_metrics:
                    mc = METRIC_CONFIG[m]
                    html += f'<td style="{TD}">{mc["fmt"](r[m])}</td>'
                html += '</tr>'
            html += '</table></div>'
            st.markdown(html, unsafe_allow_html=True)


# ── Tab 4: Trends ───────────────────────────────────────────────────
def render_trends(monthly, months):
    if len(months) < 2:
        st.info("Need at least 2 months of data to show trends.")
        return

    # Aggregate totals per month
    month_totals = []
    for mk in months:
        totals = aggregate_rows(monthly, mk)
        if totals:
            totals['month_key'] = mk
            month_totals.append(totals)
    if not month_totals:
        return
    mt_df = pd.DataFrame(month_totals)

    # Cost + FTD bar chart
    st.markdown("#### Cost & FTD Trend")
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Cost (USD)', x=mt_df['month_key'], y=mt_df['cost'],
                         marker_color='#3b82f6', yaxis='y'))
    fig.add_trace(go.Bar(name='FTD', x=mt_df['month_key'], y=mt_df['ftd'],
                         marker_color='#22c55e', yaxis='y2'))
    fig.update_layout(
        yaxis=dict(title='Cost (USD)', titlefont_color='#3b82f6', tickfont_color='#3b82f6'),
        yaxis2=dict(title='FTD', titlefont_color='#22c55e', tickfont_color='#22c55e',
                    overlaying='y', side='right'),
        barmode='group', height=400, margin=dict(t=30, b=40),
        legend=dict(orientation='h', y=1.1), font=dict(color='#1e293b'),
        plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff',
    )
    st.plotly_chart(fig, use_container_width=True, key="trend_cost_ftd")

    # CPA + ROAS line chart
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### CPA Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mt_df['month_key'], y=mt_df['cpa'], mode='lines+markers',
                                 name='CPA', line=dict(color='#ef4444', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='CPA (USD)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="trend_cpa")
    with c2:
        st.markdown("#### ROAS Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mt_df['month_key'], y=mt_df['roas'], mode='lines+markers',
                                 name='ROAS', line=dict(color='#22c55e', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='ROAS'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="trend_roas")

    # CTR + Conv Rate
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### CTR Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mt_df['month_key'], y=mt_df['ctr'], mode='lines+markers',
                                 name='CTR', line=dict(color='#8b5cf6', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='CTR (%)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="trend_ctr")
    with c2:
        st.markdown("#### Conv Rate Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mt_df['month_key'], y=mt_df['conv_rate'], mode='lines+markers',
                                 name='Conv Rate', line=dict(color='#f59e0b', width=3), marker=dict(size=8)))
        fig.update_layout(yaxis=dict(title='Conv Rate (%)'), height=350, margin=dict(t=20, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="trend_conv")

    # Agent trend lines
    st.divider()
    st.markdown("#### Agent Monthly Trends")
    sel_agent = st.selectbox("Select Agent", AGENTS_LIST, key="trend_agent")
    sel_metric = st.selectbox("Select Metric", list(METRIC_CONFIG.keys()), key="trend_metric",
                              format_func=lambda m: METRIC_CONFIG[m]['label'])

    agent_data = monthly[monthly['agent'] == sel_agent].sort_values('month_key')
    if not agent_data.empty:
        mc = METRIC_CONFIG[sel_metric]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=agent_data['month_key'], y=agent_data[sel_metric],
            mode='lines+markers+text', name=sel_agent,
            text=[mc['fmt'](v) for v in agent_data[sel_metric]],
            textposition='top center',
            line=dict(color='#3b82f6', width=3), marker=dict(size=10),
        ))
        fig.update_layout(yaxis=dict(title=mc['label']), height=400, margin=dict(t=30, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
        st.plotly_chart(fig, use_container_width=True, key="agent_trend_chart")

    # Team trend lines
    st.divider()
    st.markdown("#### Team Monthly Trends")
    sel_team = st.selectbox("Select Team", TEAM_NAMES, key="trend_team")
    sel_team_metric = st.selectbox("Select Metric", ['cost', 'ftd', 'cpa', 'roas', 'conv_rate', 'ctr'],
                                   key="trend_team_metric",
                                   format_func=lambda m: METRIC_CONFIG[m]['label'])

    team_data = monthly[monthly['team'] == sel_team]
    if not team_data.empty:
        # Aggregate team per month
        team_monthly = []
        for mk in months:
            mk_rows = team_data[team_data['month_key'] == mk]
            if mk_rows.empty:
                continue
            t = {
                'month_key': mk,
                'cost': mk_rows['cost'].sum(),
                'ftd': mk_rows['ftd'].sum(),
                'register': mk_rows['register'].sum(),
                'impressions': mk_rows['impressions'].sum(),
                'clicks': mk_rows['clicks'].sum(),
                'arppu': mk_rows['arppu'].mean(),
            }
            t['cpa'] = t['cost'] / t['ftd'] if t['ftd'] > 0 else 0
            t['conv_rate'] = t['ftd'] / t['register'] * 100 if t['register'] > 0 else 0
            t['ctr'] = t['clicks'] / t['impressions'] * 100 if t['impressions'] > 0 else 0
            t['roas'] = (t['arppu'] / KPI_PHP_USD_RATE / (t['cost'] / t['ftd'])
                         if t['ftd'] > 0 and t['cost'] > 0 else 0)
            team_monthly.append(t)

        if team_monthly:
            tm_df = pd.DataFrame(team_monthly)
            mc = METRIC_CONFIG[sel_team_metric]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=tm_df['month_key'], y=tm_df[sel_team_metric],
                mode='lines+markers+text', name=sel_team,
                text=[mc['fmt'](v) for v in tm_df[sel_team_metric]],
                textposition='top center',
                line=dict(color='#22c55e', width=3), marker=dict(size=10),
            ))
            fig.update_layout(yaxis=dict(title=mc['label']), height=400, margin=dict(t=30, b=40),
                              plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'))
            st.plotly_chart(fig, use_container_width=True, key="team_trend_chart")

    # Heatmap: Agents x Months
    st.divider()
    st.markdown("#### Agent × Month Heatmap")
    hm_metric = st.selectbox("Heatmap Metric", ['cpa', 'roas', 'conv_rate', 'ctr'],
                             key="hm_metric", format_func=lambda m: METRIC_CONFIG[m]['label'])

    pivot = monthly.pivot_table(index='agent', columns='month_key', values=hm_metric, aggfunc='first')
    pivot = pivot.reindex(columns=months)

    mc = METRIC_CONFIG[hm_metric]
    colorscale = 'RdYlGn' if mc['hib'] else 'RdYlGn_r'
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        text=[[mc['fmt'](v) if pd.notna(v) else '-' for v in row] for row in pivot.values],
        texttemplate='%{text}',
        colorscale=colorscale,
        hovertemplate='Agent: %{y}<br>Month: %{x}<br>Value: %{text}<extra></extra>',
    ))
    fig.update_layout(height=max(300, len(pivot) * 50), margin=dict(t=20, b=40),
                      plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'),
                      xaxis=dict(title='Month'), yaxis=dict(title='Agent', autorange='reversed'))
    st.plotly_chart(fig, use_container_width=True, key="heatmap")


# ── Tab 5: Analysis & Insights ───────────────────────────────────────
def _pct_change(curr, prev):
    if prev == 0:
        return None
    return (curr - prev) / abs(prev) * 100


def _direction_word(pct, higher_is_better):
    if pct is None:
        return "unchanged"
    is_good = (pct > 0) == higher_is_better
    magnitude = abs(pct)
    if magnitude < 1:
        return "remained stable"
    strength = "slightly" if magnitude < 10 else ("significantly" if magnitude > 30 else "")
    direction = "increased" if pct > 0 else "decreased"
    good_bad = "improved" if is_good else "declined"
    return f"{strength} {good_bad} ({direction} by {magnitude:.1f}%)".strip()


def _render_platform_analysis(platform_monthly, platform_name, sel_month, prev_month):
    """Render standalone analysis for a single platform (Facebook or Google)."""
    has_data = False
    for sk in ['daily_roi', 'roll_back', 'violet']:
        pdf = platform_monthly.get(sk, pd.DataFrame())
        if not pdf.empty and not pdf[(pdf['month_key'] == sel_month) & (pdf['platform'] == platform_name)].empty:
            has_data = True
            break

    if not has_data:
        return

    # Derive prev_month from platform data if P-tab doesn't have it
    # (e.g. P-tab starts Feb but Google has Jan data)
    if not prev_month:
        for sk in ['daily_roi', 'roll_back', 'violet']:
            pdf = platform_monthly.get(sk, pd.DataFrame())
            if pdf.empty:
                continue
            plat_months = sorted(pdf[pdf['platform'] == platform_name]['month_key'].unique())
            sel_idx = plat_months.index(sel_month) if sel_month in plat_months else -1
            if sel_idx > 0:
                prev_month = plat_months[sel_idx - 1]
                break

    icon = "📘" if platform_name == 'Facebook' else "📗"
    st.markdown("---")
    st.markdown(f"### {icon} {platform_name} Ads Analysis")

    for section_key, section_label in SECTION_LABELS.items():
        pdf = platform_monthly.get(section_key, pd.DataFrame())
        if pdf.empty:
            continue

        curr_rows = pdf[(pdf['month_key'] == sel_month) & (pdf['platform'] == platform_name)]
        if curr_rows.empty:
            continue

        prev_rows = pdf[(pdf['month_key'] == prev_month) & (pdf['platform'] == platform_name)] if prev_month else pd.DataFrame()

        c = curr_rows.iloc[0]
        p = prev_rows.iloc[0] if not prev_rows.empty else None

        st.markdown(f"#### {section_label}")

        # Summary line
        parts = []
        parts.append(f"Spent **{md_cost(c['cost'])}**, generated **{md_num(c['ftd'])} FTDs** "
                     f"with **{md_num(c['register'])} registrations** and "
                     f"**{md_deposit(c['deposit'])}** in deposits.")

        # Key metrics
        parts.append(f"Cost/FTD: **{md_cost(c['cpftd'])}** · "
                     f"ARPPU: **{md_deposit(c['arppu'])}** · "
                     f"Conv Rate: **{md_pct(c['conv_rate'])}** · "
                     f"ROAS: **{c['roas']:.4f}x**")

        # MoM comparison
        if p is not None:
            cost_chg = _pct_change(c['cost'], p['cost'])
            ftd_chg = _pct_change(c['ftd'], p['ftd'])
            dep_chg = _pct_change(c['deposit'], p['deposit'])
            roas_chg = _pct_change(c['roas'], p['roas'])
            cpftd_chg = _pct_change(c['cpftd'], p['cpftd'])
            cvr_chg = _pct_change(c['conv_rate'], p['conv_rate'])

            mom_lines = []
            mom_lines.append(f"Cost {_direction_word(cost_chg, False)} ({md_cost(p['cost'])} → {md_cost(c['cost'])})")
            mom_lines.append(f"FTD {_direction_word(ftd_chg, True)} ({md_num(p['ftd'])} → {md_num(c['ftd'])})")
            mom_lines.append(f"Deposits {_direction_word(dep_chg, True)} ({md_deposit(p['deposit'])} → {md_deposit(c['deposit'])})")
            mom_lines.append(f"Cost/FTD {_direction_word(cpftd_chg, False)} ({md_cost(p['cpftd'])} → {md_cost(c['cpftd'])})")
            mom_lines.append(f"Conv Rate {_direction_word(cvr_chg, True)} ({md_pct(p['conv_rate'])} → {md_pct(c['conv_rate'])})")
            mom_lines.append(f"ROAS {_direction_word(roas_chg, True)} ({p['roas']:.4f}x → {c['roas']:.4f}x)")

            parts.append("**MoM Changes:**")
            for ml in mom_lines:
                parts.append(f"  - {ml}")

            # Efficiency assessment
            if cost_chg is not None and ftd_chg is not None:
                if ftd_chg > cost_chg:
                    parts.append("✅ Spend efficiency improved — FTD growth outpaced cost growth.")
                elif cost_chg > 0 and (ftd_chg is None or ftd_chg <= 0):
                    parts.append("⚠️ Spend efficiency declined — costs rose while FTDs dropped or stagnated.")
                elif cost_chg < 0 and ftd_chg > 0:
                    parts.append("✅ Excellent — reduced spend while FTDs still grew.")
        else:
            parts.append("*No previous month data for MoM comparison.*")

        # ROAS assessment (ARPPU/57.7/CPA scale: >0.15 good, 0.08-0.15 moderate, <0.08 low)
        roas_val = c['roas']
        if roas_val >= 0.15:
            parts.append(f"✅ ROAS at {roas_val:.4f}x — strong return. Current strategy is working well.")
        elif roas_val >= 0.08:
            parts.append(f"ROAS at {roas_val:.4f}x — moderate return. Focus on improving FTD recharge rates and ARPPU.")
        elif roas_val > 0:
            parts.append(f"⚠️ ROAS at {roas_val:.4f}x — low return. Review targeting and post-registration engagement.")

        st.markdown("\n".join(f"- {line}" if not line.startswith("  ") and not line.startswith("*") and not line.startswith("✅") and not line.startswith("⚠") else line for line in parts))

    # Platform-specific recommendations
    roi_df = platform_monthly.get('daily_roi', pd.DataFrame())
    if not roi_df.empty:
        curr_roi = roi_df[(roi_df['month_key'] == sel_month) & (roi_df['platform'] == platform_name)]
        prev_roi = roi_df[(roi_df['month_key'] == prev_month) & (roi_df['platform'] == platform_name)] if prev_month else pd.DataFrame()

        if not curr_roi.empty:
            c = curr_roi.iloc[0]
            st.markdown(f"#### {platform_name} Recommendations")
            p_recs = []

            cpftd = c['cpftd']
            if cpftd > 15:
                p_recs.append(f"Cost/FTD at {md_cost(cpftd)} exceeds \\$15 target. Tighten audience targeting and pause low-performing campaigns.")
            elif cpftd > 12:
                p_recs.append(f"Cost/FTD at {md_cost(cpftd)} is moderate. A/B test creatives to push below \\$12.")
            elif cpftd > 0:
                p_recs.append(f"Cost/FTD at {md_cost(cpftd)} is efficient. Scale budget cautiously while maintaining efficiency.")

            if c['conv_rate'] < 3:
                p_recs.append(f"Conversion rate at {md_pct(c['conv_rate'])} is low. Review registration-to-FTD funnel and onboarding experience.")

            if c['roas'] < 0.08 and c['roas'] > 0:
                p_recs.append(f"ROAS at {c['roas']:.4f}x needs improvement. Focus on retaining FTDs with better first-deposit incentives.")

            if not prev_roi.empty:
                p = prev_roi.iloc[0]
                ftd_chg = _pct_change(c['ftd'], p['ftd'])
                cost_chg = _pct_change(c['cost'], p['cost'])
                if cost_chg is not None and cost_chg > 20 and (ftd_chg is None or ftd_chg < 10):
                    p_recs.append("Budget scaling issue — spend increased significantly without proportional FTD growth. Scale more gradually.")

            if p_recs:
                for i, rec in enumerate(p_recs, 1):
                    st.markdown(f"{i}. {rec}")
            else:
                st.success(f"{platform_name} performance looks strong. Continue current strategies.")


def render_analysis(monthly, channel_monthly, months, sel_month, prev_month, platform_monthly=None):
    curr = aggregate_rows(monthly, sel_month)
    prev = aggregate_rows(monthly, prev_month) if prev_month else {}
    month_data = monthly[monthly['month_key'] == sel_month]
    prev_data = monthly[monthly['month_key'] == prev_month] if prev_month else pd.DataFrame()

    if not curr:
        st.warning("No data for analysis.")
        return

    # ── 1. Executive Summary ─────────────────────────────────────────
    st.markdown("### Executive Summary")
    summary_parts = []
    summary_parts.append(f"In **{sel_month}**, the team spent a total of **{md_cost(curr['cost'])}** "
                         f"generating **{md_num(curr['ftd'])} FTDs** from **{md_num(curr['register'])} registrations**.")

    if prev:
        cost_pct = _pct_change(curr['cost'], prev['cost'])
        ftd_pct = _pct_change(curr['ftd'], prev['ftd'])
        cpa_pct = _pct_change(curr['cpa'], prev['cpa'])
        roas_pct = _pct_change(curr['roas'], prev['roas'])

        summary_parts.append(
            f"Compared to **{prev_month}**, ad spend {_direction_word(cost_pct, False)} "
            f"while FTD volume {_direction_word(ftd_pct, True)}.")

        summary_parts.append(
            f"CPA {_direction_word(cpa_pct, False)} to **{md_cost(curr['cpa'])}** "
            f"and ROAS {_direction_word(roas_pct, True)} to **{md_roas(curr['roas'])}**.")

        conv_pct = _pct_change(curr['conv_rate'], prev['conv_rate'])
        ctr_pct = _pct_change(curr['ctr'], prev['ctr'])
        summary_parts.append(
            f"Conversion rate {_direction_word(conv_pct, True)} at **{md_pct(curr['conv_rate'])}** "
            f"and CTR {_direction_word(ctr_pct, True)} at **{md_pct(curr['ctr'])}**.")

    st.markdown(" ".join(summary_parts))

    # ── 2. Cost Efficiency Analysis ──────────────────────────────────
    st.markdown("---")
    st.markdown("### Cost Efficiency Analysis")

    if prev:
        cost_change = _pct_change(curr['cost'], prev['cost'])
        ftd_change = _pct_change(curr['ftd'], prev['ftd'])

        if cost_change is not None and ftd_change is not None:
            if ftd_change > cost_change:
                st.success(
                    f"Spend efficiency **improved** — FTD growth ({ftd_change:+.1f}%) outpaced "
                    f"cost growth ({cost_change:+.1f}%), meaning more conversions per dollar spent.")
            elif cost_change > 0 and ftd_change <= 0:
                st.error(
                    f"Spend efficiency **declined** — costs rose ({cost_change:+.1f}%) while "
                    f"FTDs dropped ({ftd_change:+.1f}%). Investigate campaign targeting and creative fatigue.")
            elif cost_change < 0 and ftd_change > 0:
                st.success(
                    f"Excellent cost optimization — reduced spend ({cost_change:+.1f}%) while "
                    f"FTDs still grew ({ftd_change:+.1f}%). Great budget discipline.")
            else:
                st.info(
                    f"Spend changed by {cost_change:+.1f}% and FTDs by {ftd_change:+.1f}%. "
                    f"The cost-to-output ratio is roughly proportional.")

    cpa_val = curr['cpa']
    if cpa_val > 0:
        if cpa_val < 10:
            st.success(f"CPA at **{md_cost(cpa_val)}** is in the **excellent** range (< \\$10). Keep current strategy.")
        elif cpa_val < 14:
            st.info(f"CPA at **{md_cost(cpa_val)}** is in the **good** range (\\$10–\\$14). Room for optimization.")
        elif cpa_val <= 15:
            st.warning(f"CPA at **{md_cost(cpa_val)}** is in the **fair** range (\\$14–\\$15). Review underperforming campaigns.")
        else:
            st.error(f"CPA at **{md_cost(cpa_val)}** is **above target** (> \\$15). Immediate action needed on high-cost campaigns.")

    # ── 3. Agent Performance Insights ────────────────────────────────
    st.markdown("---")
    st.markdown("### Agent Performance Insights")

    if not month_data.empty and len(month_data) > 1:
        best_cpa = month_data.loc[month_data['cpa'].idxmin()]
        worst_cpa = month_data.loc[month_data['cpa'].idxmax()]
        best_roas = month_data.loc[month_data['roas'].idxmax()]
        worst_roas = month_data.loc[month_data['roas'].idxmin()]
        best_cvr = month_data.loc[month_data['conv_rate'].idxmax()]

        insights = []
        insights.append(
            f"**Top performer by CPA**: {best_cpa['agent']} at {md_cost(best_cpa['cpa'])} — "
            f"{((worst_cpa['cpa'] - best_cpa['cpa']) / worst_cpa['cpa'] * 100):.0f}% more efficient than "
            f"{worst_cpa['agent']} ({md_cost(worst_cpa['cpa'])}).")

        insights.append(
            f"**Best ROAS**: {best_roas['agent']} at {md_roas(best_roas['roas'])}. "
            f"**Lowest ROAS**: {worst_roas['agent']} at {md_roas(worst_roas['roas'])}.")

        insights.append(
            f"**Highest conversion rate**: {best_cvr['agent']} at {md_pct(best_cvr['conv_rate'])}.")

        for ins in insights:
            st.markdown(f"- {ins}")

        if not prev_data.empty:
            st.markdown("#### MoM Agent Changes")
            improved = []
            declined = []
            for _, row in month_data.iterrows():
                agent = row['agent']
                prev_row = prev_data[prev_data['agent'] == agent]
                if prev_row.empty:
                    continue
                pr = prev_row.iloc[0]
                cpa_chg = _pct_change(row['cpa'], pr['cpa'])
                roas_chg = _pct_change(row['roas'], pr['roas'])

                if cpa_chg is not None and cpa_chg < -5:
                    improved.append(f"**{agent}**: CPA improved {abs(cpa_chg):.1f}% ({md_cost(pr['cpa'])} → {md_cost(row['cpa'])})")
                elif cpa_chg is not None and cpa_chg > 10:
                    declined.append(f"**{agent}**: CPA worsened {cpa_chg:.1f}% ({md_cost(pr['cpa'])} → {md_cost(row['cpa'])})")

                if roas_chg is not None and roas_chg > 10:
                    improved.append(f"**{agent}**: ROAS improved {roas_chg:.1f}% ({md_roas(pr['roas'])} → {md_roas(row['roas'])})")
                elif roas_chg is not None and roas_chg < -10:
                    declined.append(f"**{agent}**: ROAS declined {abs(roas_chg):.1f}% ({md_roas(pr['roas'])} → {md_roas(row['roas'])})")

            if improved:
                st.success("**Improvements:**\n" + "\n".join(f"- {x}" for x in improved))
            if declined:
                st.error("**Needs Attention:**\n" + "\n".join(f"- {x}" for x in declined))
            if not improved and not declined:
                st.info("All agents showed relatively stable performance compared to the previous month.")

    # ── 4. Team Analysis ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Team Analysis")

    for team_name in TEAM_NAMES:
        team_rows = month_data[month_data['team'] == team_name]
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
            prev_team = prev_data[prev_data['team'] == team_name]
            if not prev_team.empty:
                pt_cost = prev_team['cost'].sum()
                pt_ftd = prev_team['ftd'].sum()
                pt_cpa = pt_cost / pt_ftd if pt_ftd > 0 else 0
                cpa_chg = _pct_change(t_cpa, pt_cpa)
                if cpa_chg is not None:
                    team_text += f" CPA {_direction_word(cpa_chg, False)} vs last month."

        st.markdown(f"- {team_text}")

    total_cost = month_data['cost'].sum()
    if total_cost > 0:
        st.markdown("#### Budget Allocation")
        for team_name in TEAM_NAMES:
            team_cost = month_data[month_data['team'] == team_name]['cost'].sum()
            share = team_cost / total_cost * 100
            team_ftd = month_data[month_data['team'] == team_name]['ftd'].sum()
            ftd_share = team_ftd / curr['ftd'] * 100 if curr['ftd'] > 0 else 0
            if ftd_share > share + 5:
                st.success(f"**{team_name}**: {share:.1f}% of budget → {ftd_share:.1f}% of FTDs (over-delivering)")
            elif share > ftd_share + 5:
                st.warning(f"**{team_name}**: {share:.1f}% of budget → {ftd_share:.1f}% of FTDs (under-delivering)")
            else:
                st.info(f"**{team_name}**: {share:.1f}% of budget → {ftd_share:.1f}% of FTDs (proportional)")

    # ── 5. Channel Insights (DEERPROMO) ──────────────────────────────
    if not channel_monthly.empty:
        ch_month = channel_monthly[channel_monthly['month_key'] == sel_month]
        if not ch_month.empty and len(ch_month) > 1:
            st.markdown("---")
            st.markdown("### Channel Insights (DEERPROMO)")

            best_ch = ch_month.loc[ch_month['cpa'].idxmin()] if ch_month['ftd'].sum() > 0 else None
            worst_ch_candidates = ch_month[ch_month['ftd'] > 0]
            worst_ch = worst_ch_candidates.loc[worst_ch_candidates['cpa'].idxmax()] if not worst_ch_candidates.empty else None
            top_volume = ch_month.loc[ch_month['ftd'].idxmax()]

            if best_ch is not None:
                st.markdown(f"- **Most efficient channel**: {best_ch['channel_clean']} ({best_ch['team']}) "
                           f"at {md_cost(best_ch['cpa'])} CPA with {md_num(best_ch['ftd'])} FTDs")
            if worst_ch is not None:
                st.markdown(f"- **Least efficient channel**: {worst_ch['channel_clean']} ({worst_ch['team']}) "
                           f"at {md_cost(worst_ch['cpa'])} CPA")
            st.markdown(f"- **Highest volume channel**: {top_volume['channel_clean']} ({top_volume['team']}) "
                       f"with {md_num(top_volume['ftd'])} FTDs")

            high_cost_low_ftd = ch_month[(ch_month['cost'] > ch_month['cost'].median()) &
                                          (ch_month['ftd'] < ch_month['ftd'].median())]
            if not high_cost_low_ftd.empty:
                ch_list = ", ".join(f"{r['channel_clean']} ({md_cost(r['cost'])} → {md_num(r['ftd'])} FTDs)"
                                   for _, r in high_cost_low_ftd.iterrows())
                st.warning(f"**Channels to review** (above-median cost, below-median FTD): {ch_list}")

    # ── 6. Facebook Ads Analysis ─────────────────────────────────────
    if platform_monthly:
        _render_platform_analysis(platform_monthly, 'Facebook', sel_month, prev_month)

    # ── 7. Google Ads Analysis ────────────────────────────────────────
    if platform_monthly:
        _render_platform_analysis(platform_monthly, 'Google', sel_month, prev_month)

    # ── 8. Recommendations ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("### General Recommendations")

    recs = []
    if curr['cpa'] > 15:
        recs.append("**Reduce CPA urgently** — Current CPA exceeds \\$15 target. Audit campaigns with highest spend-to-FTD ratio. Consider pausing underperforming ad sets.")
    elif curr['cpa'] > 13:
        recs.append("**Optimize CPA** — Getting close to the \\$14 threshold. Focus A/B testing on top-performing creatives and tighten audience targeting.")

    if curr['roas'] < 0.1:
        recs.append("**ROAS critical** — Below 0.10x. Review ARPPU trends and verify recharge tracking. Consider shifting budget to higher-ROAS channels.")
    elif curr['roas'] < 0.2:
        recs.append("**Improve ROAS** — Below 0.20x target. Focus on retaining FTDs and improving first-deposit values through better post-reg engagement.")

    if curr['conv_rate'] < 4:
        recs.append("**Low conversion rate** — Below 4%. Review landing page experience, registration flow, and offer incentives for first deposits.")

    if curr['ctr'] < 2:
        recs.append("**Low CTR** — Below 2%. Refresh ad creatives, test new headlines, and review audience targeting for better engagement.")

    if not month_data.empty and len(month_data) > 1:
        worst_agent = month_data.loc[month_data['cpa'].idxmax()]
        best_agent = month_data.loc[month_data['cpa'].idxmin()]
        if worst_agent['cpa'] > best_agent['cpa'] * 2:
            recs.append(f"**Performance gap**: {worst_agent['agent']}'s CPA ({md_cost(worst_agent['cpa'])}) is "
                       f"{worst_agent['cpa'] / best_agent['cpa']:.1f}x higher than {best_agent['agent']}'s. "
                       f"Review {worst_agent['agent']}'s campaign setup and consider sharing {best_agent['agent']}'s strategies.")

    if prev and _pct_change(curr['cost'], prev['cost']) is not None:
        cost_chg = _pct_change(curr['cost'], prev['cost'])
        ftd_chg = _pct_change(curr['ftd'], prev['ftd'])
        if cost_chg > 20 and (ftd_chg is None or ftd_chg < 10):
            recs.append("**Budget scaling issue** — Spend increased significantly without proportional FTD growth. Scale budgets more gradually and monitor diminishing returns.")

    if not recs:
        st.success("Overall performance looks strong. Continue current strategies and focus on incremental optimizations.")
    else:
        for i, rec in enumerate(recs, 1):
            st.markdown(f"{i}. {rec}")


# ── Tab 6: FB vs Google ──────────────────────────────────────────────
PLATFORM_METRICS = {
    'cost': {'label': 'Cost (USD)', 'fmt': fmt_cost, 'hib': False},
    'register': {'label': 'Register', 'fmt': fmt_num, 'hib': True},
    'ftd': {'label': 'FTD', 'fmt': fmt_num, 'hib': True},
    'deposit': {'label': 'Deposit (₱)', 'fmt': lambda v: f"₱{v:,.0f}" if v else "₱0", 'hib': True},
    'arppu': {'label': 'ARPPU (₱)', 'fmt': lambda v: f"₱{v:,.2f}" if v else "₱0.00", 'hib': True},
    'cpftd': {'label': 'Cost/FTD', 'fmt': fmt_cost, 'hib': False},
    'conv_rate': {'label': 'Conv Rate', 'fmt': fmt_pct, 'hib': True},
    'roas': {'label': 'ROAS', 'fmt': fmt_roas, 'hib': True},
}

SECTION_LABELS = {
    'daily_roi': 'Daily ROI',
    'roll_back': 'Roll Back',
    'violet': 'Violet',
}


def render_fb_vs_google(platform_monthly, sel_month, prev_month):
    """Render FB vs Google comparison tab."""
    has_any_data = False
    for section_key in ['daily_roi', 'roll_back', 'violet']:
        df = platform_monthly.get(section_key, pd.DataFrame())
        if not df.empty and sel_month in df['month_key'].values:
            has_any_data = True
            break

    if not has_any_data:
        st.warning("No FB/Google channel data available for the selected month.")
        return

    # Derive prev_month from platform data if P-tab doesn't have it
    if not prev_month:
        for section_key in ['daily_roi', 'roll_back', 'violet']:
            df_check = platform_monthly.get(section_key, pd.DataFrame())
            if df_check.empty:
                continue
            all_months = sorted(df_check['month_key'].unique())
            sel_idx = all_months.index(sel_month) if sel_month in all_months else -1
            if sel_idx > 0:
                prev_month = all_months[sel_idx - 1]
                break

    # Section selector
    section_sel = st.radio(
        "Attribution Window",
        ['daily_roi', 'roll_back', 'violet'],
        format_func=lambda x: SECTION_LABELS[x],
        horizontal=True,
        key="fbg_section",
    )

    df = platform_monthly.get(section_sel, pd.DataFrame())
    if df.empty:
        st.warning(f"No {SECTION_LABELS[section_sel]} data available.")
        return

    curr_data = df[df['month_key'] == sel_month]
    prev_data = df[df['month_key'] == prev_month] if prev_month else pd.DataFrame()

    fb_curr = curr_data[curr_data['platform'] == 'Facebook'].iloc[0].to_dict() if not curr_data[curr_data['platform'] == 'Facebook'].empty else {}
    google_curr = curr_data[curr_data['platform'] == 'Google'].iloc[0].to_dict() if not curr_data[curr_data['platform'] == 'Google'].empty else {}
    fb_prev = prev_data[prev_data['platform'] == 'Facebook'].iloc[0].to_dict() if not prev_data.empty and not prev_data[prev_data['platform'] == 'Facebook'].empty else {}
    google_prev = prev_data[prev_data['platform'] == 'Google'].iloc[0].to_dict() if not prev_data.empty and not prev_data[prev_data['platform'] == 'Google'].empty else {}

    # ── Summary cards for combined totals ──
    combined_curr = {}
    combined_prev = {}
    for key in ['cost', 'register', 'ftd', 'deposit']:
        combined_curr[key] = fb_curr.get(key, 0) + google_curr.get(key, 0)
        combined_prev[key] = fb_prev.get(key, 0) + google_prev.get(key, 0)

    # Weighted average ARPPU (by FTD count)
    fb_ftd_c = fb_curr.get('ftd', 0)
    g_ftd_c = google_curr.get('ftd', 0)
    total_ftd_c = fb_ftd_c + g_ftd_c
    combined_arppu_curr = ((fb_curr.get('arppu', 0) * fb_ftd_c + google_curr.get('arppu', 0) * g_ftd_c) / total_ftd_c) if total_ftd_c > 0 else 0
    fb_ftd_p = fb_prev.get('ftd', 0)
    g_ftd_p = google_prev.get('ftd', 0)
    total_ftd_p = fb_ftd_p + g_ftd_p
    combined_arppu_prev = ((fb_prev.get('arppu', 0) * fb_ftd_p + google_prev.get('arppu', 0) * g_ftd_p) / total_ftd_p) if total_ftd_p > 0 else 0

    # Derived combined metrics — ROAS = ARPPU / 57.7 / CPA
    combined_curr['cpftd'] = combined_curr['cost'] / combined_curr['ftd'] if combined_curr['ftd'] > 0 else 0
    combined_curr['roas'] = combined_arppu_curr / KPI_PHP_USD_RATE / combined_curr['cpftd'] if combined_curr['cpftd'] > 0 else 0
    combined_prev['cpftd'] = combined_prev['cost'] / combined_prev['ftd'] if combined_prev.get('ftd', 0) > 0 else 0
    combined_prev['roas'] = combined_arppu_prev / KPI_PHP_USD_RATE / combined_prev['cpftd'] if combined_prev.get('cpftd', 0) > 0 else 0

    card_metrics = ['cost', 'ftd', 'deposit', 'cpftd', 'roas']
    cols = st.columns(len(card_metrics))
    for i, m in enumerate(card_metrics):
        mc = PLATFORM_METRICS[m]
        with cols[i]:
            val = combined_curr.get(m, 0)
            pval = combined_prev.get(m, 0)
            delta = None
            if pval and pval != 0:
                pct = (val - pval) / abs(pval) * 100
                delta = f"{pct:+.1f}% MoM"
            delta_color = "inverse" if not mc['hib'] else "normal"
            st.metric(f"Combined {mc['label']}", mc['fmt'](val), delta, delta_color=delta_color)

    st.markdown(f"#### {SECTION_LABELS[section_sel]} — FB vs Google Comparison")

    # ── Main comparison table ──
    display_metrics = ['cost', 'register', 'ftd', 'deposit', 'arppu', 'cpftd', 'conv_rate', 'roas']

    html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Metric</th>'
    html += f'<th style="{TH}">Facebook</th>'
    if prev_month and fb_prev:
        html += f'<th style="{TH}">FB MoM</th>'
    html += f'<th style="{TH}">Google</th>'
    if prev_month and google_prev:
        html += f'<th style="{TH}">Google MoM</th>'
    html += f'<th style="{TH}">FB Share</th></tr>'

    for m in display_metrics:
        mc = PLATFORM_METRICS[m]
        fb_val = fb_curr.get(m, 0)
        g_val = google_curr.get(m, 0)
        fb_p = fb_prev.get(m, 0)
        g_p = google_prev.get(m, 0)
        total = fb_val + g_val if m in ['cost', 'register', 'ftd', 'deposit'] else 0

        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{mc["label"]}</td>'
        html += f'<td style="{TD};font-weight:600">{mc["fmt"](fb_val)}</td>'
        if prev_month and fb_prev:
            html += f'<td style="{TD}">{delta_html(fb_val, fb_p, mc["hib"])}</td>'
        html += f'<td style="{TD};font-weight:600">{mc["fmt"](g_val)}</td>'
        if prev_month and google_prev:
            html += f'<td style="{TD}">{delta_html(g_val, g_p, mc["hib"])}</td>'

        # Share column
        if total > 0:
            share = fb_val / total * 100
            html += f'<td style="{TD}">{share:.0f}% / {100-share:.0f}%</td>'
        else:
            html += f'<td style="{TD}">—</td>'
        html += '</tr>'

    html += '</table></div>'
    st.markdown(html, unsafe_allow_html=True)

    # ── Bar chart: FB vs Google key metrics ──
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        bar_metrics = ['cost', 'ftd', 'register']
        fb_vals = [fb_curr.get(m, 0) for m in bar_metrics]
        g_vals = [google_curr.get(m, 0) for m in bar_metrics]
        labels = [PLATFORM_METRICS[m]['label'] for m in bar_metrics]
        fig.add_trace(go.Bar(name='Facebook', x=labels, y=fb_vals, marker_color='#3b82f6'))
        fig.add_trace(go.Bar(name='Google', x=labels, y=g_vals, marker_color='#f59e0b'))
        fig.update_layout(barmode='group', title='Volume Metrics', height=350,
                          margin=dict(t=40, b=40), font=dict(color='#1e293b'),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff',
                          legend=dict(orientation='h', y=1.12))
        st.plotly_chart(fig, use_container_width=True, key="fbg_volume")

    with c2:
        fig = go.Figure()
        eff_metrics = ['cpftd', 'arppu']
        fb_vals = [fb_curr.get(m, 0) for m in eff_metrics]
        g_vals = [google_curr.get(m, 0) for m in eff_metrics]
        labels = [PLATFORM_METRICS[m]['label'] for m in eff_metrics]
        fig.add_trace(go.Bar(name='Facebook', x=labels, y=fb_vals, marker_color='#3b82f6'))
        fig.add_trace(go.Bar(name='Google', x=labels, y=g_vals, marker_color='#f59e0b'))
        fig.update_layout(barmode='group', title='Efficiency Metrics', height=350,
                          margin=dict(t=40, b=40), font=dict(color='#1e293b'),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff',
                          legend=dict(orientation='h', y=1.12))
        st.plotly_chart(fig, use_container_width=True, key="fbg_efficiency")

    # ── Attribution Window Comparison ──
    st.markdown("---")
    st.markdown("#### Attribution Window Comparison (All 3 Windows)")

    # Build comparison across windows for the selected month
    window_rows = []
    for sk, sl in SECTION_LABELS.items():
        wdf = platform_monthly.get(sk, pd.DataFrame())
        if wdf.empty:
            continue
        w_month = wdf[wdf['month_key'] == sel_month]
        if w_month.empty:
            continue
        fb_r = w_month[w_month['platform'] == 'Facebook']
        g_r = w_month[w_month['platform'] == 'Google']
        window_rows.append({
            'window': sl,
            'fb_cost': fb_r.iloc[0]['cost'] if not fb_r.empty else 0,
            'fb_ftd': fb_r.iloc[0]['ftd'] if not fb_r.empty else 0,
            'fb_deposit': fb_r.iloc[0]['deposit'] if not fb_r.empty else 0,
            'fb_roas': fb_r.iloc[0]['roas'] if not fb_r.empty else 0,
            'g_cost': g_r.iloc[0]['cost'] if not g_r.empty else 0,
            'g_ftd': g_r.iloc[0]['ftd'] if not g_r.empty else 0,
            'g_deposit': g_r.iloc[0]['deposit'] if not g_r.empty else 0,
            'g_roas': g_r.iloc[0]['roas'] if not g_r.empty else 0,
        })

    if window_rows:
        html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
        html += f'<tr style="background:#f1f5f9;color:#1e293b">'
        html += f'<th style="{TH}" rowspan="2">Window</th>'
        html += f'<th style="{TH};background:#dbeafe" colspan="4">Facebook</th>'
        html += f'<th style="{TH};background:#fef3c7" colspan="4">Google</th></tr>'
        html += f'<tr style="background:#f1f5f9;color:#1e293b">'
        for _ in range(2):
            html += f'<th style="{TH}">Cost</th><th style="{TH}">FTD</th>'
            html += f'<th style="{TH}">Deposit</th><th style="{TH}">ROAS</th>'
        html += '</tr>'

        for wr in window_rows:
            html += f'<tr style="background:#ffffff;color:#1e293b">'
            html += f'<td style="{TD};font-weight:700">{wr["window"]}</td>'
            html += f'<td style="{TD}">{fmt_cost(wr["fb_cost"])}</td>'
            html += f'<td style="{TD}">{fmt_num(wr["fb_ftd"])}</td>'
            html += f'<td style="{TD}">₱{wr["fb_deposit"]:,.0f}</td>'
            html += f'<td style="{TD};font-weight:600">{wr["fb_roas"]:.4f}x</td>'
            html += f'<td style="{TD}">{fmt_cost(wr["g_cost"])}</td>'
            html += f'<td style="{TD}">{fmt_num(wr["g_ftd"])}</td>'
            html += f'<td style="{TD}">₱{wr["g_deposit"]:,.0f}</td>'
            html += f'<td style="{TD};font-weight:600">{wr["g_roas"]:.4f}x</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

    # ── Monthly trend: FB vs Google ──
    months_in_data = sorted(df['month_key'].unique())
    if len(months_in_data) >= 2:
        st.markdown("---")
        st.markdown("#### FB vs Google Monthly Trend")
        trend_metric = st.selectbox("Metric", list(PLATFORM_METRICS.keys()), key="fbg_trend_m",
                                     format_func=lambda m: PLATFORM_METRICS[m]['label'])

        fb_trend = df[df['platform'] == 'Facebook'].sort_values('month_key')
        g_trend = df[df['platform'] == 'Google'].sort_values('month_key')

        mc = PLATFORM_METRICS[trend_metric]
        fig = go.Figure()
        if not fb_trend.empty:
            fig.add_trace(go.Scatter(
                x=fb_trend['month_key'], y=fb_trend[trend_metric],
                mode='lines+markers+text', name='Facebook',
                text=[mc['fmt'](v) for v in fb_trend[trend_metric]],
                textposition='top center',
                line=dict(color='#3b82f6', width=3), marker=dict(size=10)))
        if not g_trend.empty:
            fig.add_trace(go.Scatter(
                x=g_trend['month_key'], y=g_trend[trend_metric],
                mode='lines+markers+text', name='Google',
                text=[mc['fmt'](v) for v in g_trend[trend_metric]],
                textposition='bottom center',
                line=dict(color='#f59e0b', width=3), marker=dict(size=10)))
        fig.update_layout(yaxis=dict(title=mc['label']), height=400, margin=dict(t=30, b=40),
                          plot_bgcolor='#f8fafc', paper_bgcolor='#ffffff', font=dict(color='#1e293b'),
                          legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig, use_container_width=True, key="fbg_trend_chart")

    # ── Platform insights ──
    st.markdown("---")
    st.markdown("#### Platform Insights")
    if fb_curr and google_curr:
        fb_cost = fb_curr.get('cost', 0)
        g_cost = google_curr.get('cost', 0)
        total_cost = fb_cost + g_cost
        fb_ftd = fb_curr.get('ftd', 0)
        g_ftd = google_curr.get('ftd', 0)
        fb_roas = fb_curr.get('roas', 0)
        g_roas = google_curr.get('roas', 0)

        if total_cost > 0:
            fb_share = fb_cost / total_cost * 100
            st.markdown(f"- **Budget split**: Facebook {fb_share:.0f}% (${fb_cost:,.2f}) vs Google {100-fb_share:.0f}% (${g_cost:,.2f})")

        if fb_ftd + g_ftd > 0:
            fb_ftd_share = fb_ftd / (fb_ftd + g_ftd) * 100
            st.markdown(f"- **FTD split**: Facebook {fb_ftd_share:.0f}% ({fb_ftd:,}) vs Google {100-fb_ftd_share:.0f}% ({g_ftd:,})")

        if fb_roas > g_roas and g_roas > 0:
            st.success(f"Facebook ROAS ({fb_roas:.4f}x) outperforms Google ({g_roas:.4f}x) by {((fb_roas-g_roas)/g_roas*100):.0f}%")
        elif g_roas > fb_roas and fb_roas > 0:
            st.success(f"Google ROAS ({g_roas:.4f}x) outperforms Facebook ({fb_roas:.4f}x) by {((g_roas-fb_roas)/fb_roas*100):.0f}%")

        fb_cpftd = fb_curr.get('cpftd', 0)
        g_cpftd = google_curr.get('cpftd', 0)
        if fb_cpftd > 0 and g_cpftd > 0:
            if fb_cpftd < g_cpftd:
                st.info(f"Facebook acquires FTDs cheaper (${fb_cpftd:.2f}) vs Google (${g_cpftd:.2f}). Consider shifting more budget to FB.")
            else:
                st.info(f"Google acquires FTDs cheaper (${g_cpftd:.2f}) vs Facebook (${fb_cpftd:.2f}). Consider shifting more budget to Google.")

        # MoM comparison by platform
        if fb_prev and google_prev:
            fb_ftd_chg = _pct_change(fb_curr.get('ftd', 0), fb_prev.get('ftd', 0))
            g_ftd_chg = _pct_change(google_curr.get('ftd', 0), google_prev.get('ftd', 0))
            if fb_ftd_chg is not None:
                st.markdown(f"- **Facebook MoM**: FTD {_direction_word(fb_ftd_chg, True)}, "
                           f"ROAS {_direction_word(_pct_change(fb_curr.get('roas',0), fb_prev.get('roas',0)), True)}")
            if g_ftd_chg is not None:
                st.markdown(f"- **Google MoM**: FTD {_direction_word(g_ftd_chg, True)}, "
                           f"ROAS {_direction_word(_pct_change(google_curr.get('roas',0), google_prev.get('roas',0)), True)}")


# ── Main ─────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="Monthly Analysis", page_icon="📊", layout="wide")
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("Monthly Analysis")

    # Controls
    ctrl1, ctrl2, ctrl3 = st.columns([3, 3, 1])
    with ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", type="primary", key="ma_ref"):
            refresh_agent_performance_data()
            refresh_channel_data()
            st.rerun()

    # Load data — P-tab agent performance (FB DEERPROMO channels)
    ptab_data = load_agent_performance_data()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
    monthly = build_monthly_data(daily_df)
    channel_monthly = build_monthly_channel_data(daily_df)

    # Load FB + Google channel summary data (team-level, 3 attribution windows)
    fb_data = load_fb_channel_data()
    google_data = load_google_channel_data()
    platform_monthly = build_platform_monthly(fb_data, google_data)

    if monthly.empty:
        st.warning("No daily data available to build monthly analysis.")
        return

    months = sorted(monthly['month_key'].unique())

    with ctrl1:
        sel_idx = st.selectbox("Month", range(len(months)), index=len(months) - 1,
                               format_func=lambda i: months[i], key="ma_month")
    sel_month = months[sel_idx]
    prev_month = months[sel_idx - 1] if sel_idx > 0 else None

    with ctrl2:
        if prev_month:
            st.info(f"Comparing **{sel_month}** vs **{prev_month}**")
        else:
            st.info(f"Showing **{sel_month}** (no previous month for comparison)")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview", "Agent Breakdown", "Team Breakdown",
        "FB vs Google", "Trends", "Analysis & Insights"])

    with tab1:
        render_overview(monthly, months, sel_month, prev_month)
    with tab2:
        render_agents(monthly, months, sel_month, prev_month)
    with tab3:
        render_teams(monthly, channel_monthly, months, sel_month, prev_month)
    with tab4:
        render_fb_vs_google(platform_monthly, sel_month, prev_month)
    with tab5:
        render_trends(monthly, months)
    with tab6:
        render_analysis(monthly, channel_monthly, months, sel_month, prev_month, platform_monthly)


if not hasattr(st, '_is_recharge_import'):
    main()
