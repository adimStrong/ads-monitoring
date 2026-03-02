"""
Monthly Analysis Dashboard — Comprehensive monthly ad performance with MoM comparison,
per-agent/team breakdowns, channel breakdowns, and multi-month trends.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_agent_performance_data, refresh_agent_performance_data
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


def render_analysis(monthly, channel_monthly, months, sel_month, prev_month):
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
    summary_parts.append(f"In **{sel_month}**, the team spent a total of **{fmt_cost(curr['cost'])}** "
                         f"generating **{fmt_num(curr['ftd'])} FTDs** from **{fmt_num(curr['register'])} registrations**.")

    if prev:
        cost_pct = _pct_change(curr['cost'], prev['cost'])
        ftd_pct = _pct_change(curr['ftd'], prev['ftd'])
        cpa_pct = _pct_change(curr['cpa'], prev['cpa'])
        roas_pct = _pct_change(curr['roas'], prev['roas'])

        summary_parts.append(
            f"Compared to **{prev_month}**, ad spend {_direction_word(cost_pct, False)} "
            f"while FTD volume {_direction_word(ftd_pct, True)}.")

        summary_parts.append(
            f"CPA {_direction_word(cpa_pct, False)} to **{fmt_cost(curr['cpa'])}** "
            f"and ROAS {_direction_word(roas_pct, True)} to **{fmt_roas(curr['roas'])}**.")

        conv_pct = _pct_change(curr['conv_rate'], prev['conv_rate'])
        ctr_pct = _pct_change(curr['ctr'], prev['ctr'])
        summary_parts.append(
            f"Conversion rate {_direction_word(conv_pct, True)} at **{fmt_pct(curr['conv_rate'])}** "
            f"and CTR {_direction_word(ctr_pct, True)} at **{fmt_pct(curr['ctr'])}**.")

    st.markdown(" ".join(summary_parts))

    # ── 2. Cost Efficiency Analysis ──────────────────────────────────
    st.markdown("---")
    st.markdown("### Cost Efficiency Analysis")

    if prev:
        # Cost vs output efficiency
        cost_change = _pct_change(curr['cost'], prev['cost'])
        ftd_change = _pct_change(curr['ftd'], prev['ftd'])

        if cost_change is not None and ftd_change is not None:
            if ftd_change > cost_change:
                efficiency_icon = "checkmark"
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

    # CPA benchmark analysis
    cpa_val = curr['cpa']
    if cpa_val > 0:
        if cpa_val < 10:
            st.success(f"CPA at **{fmt_cost(cpa_val)}** is in the **excellent** range (< $10). Keep current strategy.")
        elif cpa_val < 14:
            st.info(f"CPA at **{fmt_cost(cpa_val)}** is in the **good** range ($10–$14). Room for optimization.")
        elif cpa_val <= 15:
            st.warning(f"CPA at **{fmt_cost(cpa_val)}** is in the **fair** range ($14–$15). Review underperforming campaigns.")
        else:
            st.error(f"CPA at **{fmt_cost(cpa_val)}** is **above target** (> $15). Immediate action needed on high-cost campaigns.")

    # ── 3. Agent Performance Insights ────────────────────────────────
    st.markdown("---")
    st.markdown("### Agent Performance Insights")

    if not month_data.empty and len(month_data) > 1:
        # Best / worst agents
        best_cpa = month_data.loc[month_data['cpa'].idxmin()]
        worst_cpa = month_data.loc[month_data['cpa'].idxmax()]
        best_roas = month_data.loc[month_data['roas'].idxmax()]
        worst_roas = month_data.loc[month_data['roas'].idxmin()]
        best_cvr = month_data.loc[month_data['conv_rate'].idxmax()]

        insights = []
        insights.append(
            f"**Top performer by CPA**: {best_cpa['agent']} at {fmt_cost(best_cpa['cpa'])} — "
            f"{((worst_cpa['cpa'] - best_cpa['cpa']) / worst_cpa['cpa'] * 100):.0f}% more efficient than "
            f"{worst_cpa['agent']} ({fmt_cost(worst_cpa['cpa'])}).")

        insights.append(
            f"**Best ROAS**: {best_roas['agent']} at {fmt_roas(best_roas['roas'])}. "
            f"**Lowest ROAS**: {worst_roas['agent']} at {fmt_roas(worst_roas['roas'])}.")

        insights.append(
            f"**Highest conversion rate**: {best_cvr['agent']} at {fmt_pct(best_cvr['conv_rate'])}.")

        for ins in insights:
            st.markdown(f"- {ins}")

        # MoM agent improvements / declines
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
                    improved.append(f"**{agent}**: CPA improved {abs(cpa_chg):.1f}% ({fmt_cost(pr['cpa'])} → {fmt_cost(row['cpa'])})")
                elif cpa_chg is not None and cpa_chg > 10:
                    declined.append(f"**{agent}**: CPA worsened {cpa_chg:.1f}% ({fmt_cost(pr['cpa'])} → {fmt_cost(row['cpa'])})")

                if roas_chg is not None and roas_chg > 10:
                    improved.append(f"**{agent}**: ROAS improved {roas_chg:.1f}% ({fmt_roas(pr['roas'])} → {fmt_roas(row['roas'])})")
                elif roas_chg is not None and roas_chg < -10:
                    declined.append(f"**{agent}**: ROAS declined {abs(roas_chg):.1f}% ({fmt_roas(pr['roas'])} → {fmt_roas(row['roas'])})")

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

        team_text = f"**{team_name}** ({members}): Spent {fmt_cost(t_cost)}, generated {fmt_num(t_ftd)} FTDs at {fmt_cost(t_cpa)} CPA with {fmt_pct(t_cvr)} conversion rate."

        # Compare teams
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

    # Team cost share
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

    # ── 5. Channel Insights ──────────────────────────────────────────
    if not channel_monthly.empty:
        ch_month = channel_monthly[channel_monthly['month_key'] == sel_month]
        if not ch_month.empty and len(ch_month) > 1:
            st.markdown("---")
            st.markdown("### Channel Insights")

            best_ch = ch_month.loc[ch_month['cpa'].idxmin()] if ch_month['ftd'].sum() > 0 else None
            worst_ch_candidates = ch_month[ch_month['ftd'] > 0]
            worst_ch = worst_ch_candidates.loc[worst_ch_candidates['cpa'].idxmax()] if not worst_ch_candidates.empty else None
            top_volume = ch_month.loc[ch_month['ftd'].idxmax()]

            if best_ch is not None:
                st.markdown(f"- **Most efficient channel**: {best_ch['channel_clean']} ({best_ch['team']}) "
                           f"at {fmt_cost(best_ch['cpa'])} CPA with {fmt_num(best_ch['ftd'])} FTDs")
            if worst_ch is not None:
                st.markdown(f"- **Least efficient channel**: {worst_ch['channel_clean']} ({worst_ch['team']}) "
                           f"at {fmt_cost(worst_ch['cpa'])} CPA")
            st.markdown(f"- **Highest volume channel**: {top_volume['channel_clean']} ({top_volume['team']}) "
                       f"with {fmt_num(top_volume['ftd'])} FTDs")

            # Channels with high cost but low FTD
            high_cost_low_ftd = ch_month[(ch_month['cost'] > ch_month['cost'].median()) &
                                          (ch_month['ftd'] < ch_month['ftd'].median())]
            if not high_cost_low_ftd.empty:
                st.warning("**Channels to review** (above-median cost, below-median FTD): " +
                          ", ".join(f"{r['channel_clean']} ({fmt_cost(r['cost'])} → {fmt_num(r['ftd'])} FTDs)"
                                   for _, r in high_cost_low_ftd.iterrows()))

    # ── 6. Recommendations ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Recommendations")

    recs = []
    # CPA-based recommendations
    if curr['cpa'] > 15:
        recs.append("**Reduce CPA urgently** — Current CPA exceeds $15 target. Audit campaigns with highest spend-to-FTD ratio. Consider pausing underperforming ad sets.")
    elif curr['cpa'] > 13:
        recs.append("**Optimize CPA** — Getting close to the $14 threshold. Focus A/B testing on top-performing creatives and tighten audience targeting.")

    # ROAS-based
    if curr['roas'] < 0.1:
        recs.append("**ROAS critical** — Below 0.10x. Review ARPPU trends and verify recharge tracking. Consider shifting budget to higher-ROAS channels.")
    elif curr['roas'] < 0.2:
        recs.append("**Improve ROAS** — Below 0.20x target. Focus on retaining FTDs and improving first-deposit values through better post-reg engagement.")

    # CVR-based
    if curr['conv_rate'] < 4:
        recs.append("**Low conversion rate** — Below 4%. Review landing page experience, registration flow, and offer incentives for first deposits.")

    # CTR-based
    if curr['ctr'] < 2:
        recs.append("**Low CTR** — Below 2%. Refresh ad creatives, test new headlines, and review audience targeting for better engagement.")

    # Agent-specific
    if not month_data.empty and len(month_data) > 1:
        worst_agent = month_data.loc[month_data['cpa'].idxmax()]
        best_agent = month_data.loc[month_data['cpa'].idxmin()]
        if worst_agent['cpa'] > best_agent['cpa'] * 2:
            recs.append(f"**Performance gap**: {worst_agent['agent']}'s CPA ({fmt_cost(worst_agent['cpa'])}) is "
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
            st.rerun()

    # Load data
    ptab_data = load_agent_performance_data()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
    monthly = build_monthly_data(daily_df)
    channel_monthly = build_monthly_channel_data(daily_df)

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Agent Breakdown", "Team Breakdown", "Trends", "Analysis & Insights"])

    with tab1:
        render_overview(monthly, months, sel_month, prev_month)
    with tab2:
        render_agents(monthly, months, sel_month, prev_month)
    with tab3:
        render_teams(monthly, channel_monthly, months, sel_month, prev_month)
    with tab4:
        render_trends(monthly, months)
    with tab5:
        render_analysis(monthly, channel_monthly, months, sel_month, prev_month)


if not hasattr(st, '_is_recharge_import'):
    main()
