"""
Daily Analysis Dashboard — Day-over-day ad performance with DoD comparison,
per-agent breakdowns, and rolling trends.
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
)
from config import (
    AGENT_PERFORMANCE_TABS,
    KPI_PHP_USD_RATE,
    EXCLUDED_FROM_REPORTING,
    SIDEBAR_HIDE_CSS,
)

st.set_page_config(page_title="Daily Analysis", page_icon="D", layout="wide")
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

AGENTS_LIST = [t['agent'] for t in AGENT_PERFORMANCE_TABS if t['agent'].upper() not in EXCLUDED_FROM_REPORTING]

TEAM_MAP = {
    'Jason': 'JASON / SHILA', 'Shila': 'JASON / SHILA',
    'Ron': 'RON / ADRIAN', 'Adrian': 'RON / ADRIAN',
    'Mika': 'MIKA / JOMAR', 'Jomar': 'MIKA / JOMAR',
    'Der': 'DER',
}
TEAM_NAMES = ['JASON / SHILA', 'RON / ADRIAN', 'MIKA / JOMAR', 'DER']


# ── Helpers ──────────────────────────────────────────────────────────
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


def build_daily_data(daily_df):
    """Aggregate P-tab daily data per agent per date with derived metrics."""
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df = df[df['date'] <= pd.Timestamp.now()]

    agg = df.groupby(['agent', 'date']).agg(
        cost=('cost', 'sum'),
        register=('register', 'sum'),
        ftd=('ftd', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
    ).reset_index()

    # ARPPU from raw data
    arppu_rows = []
    for (agent, dt), grp in df.groupby(['agent', 'date']):
        arppu_col = pd.to_numeric(grp['arppu'], errors='coerce').fillna(0)
        nonzero = arppu_col[arppu_col > 0]
        arppu_rows.append({'agent': agent, 'date': dt, 'arppu': nonzero.iloc[-1] if len(nonzero) > 0 else 0})
    agg = agg.merge(pd.DataFrame(arppu_rows), on=['agent', 'date'], how='left')
    agg['arppu'] = agg['arppu'].fillna(0)

    # Derived metrics
    agg['cpa'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agg['cpr'] = agg.apply(lambda r: r['cost'] / r['register'] if r['register'] > 0 else 0, axis=1)
    agg['conv_rate'] = agg.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agg['ctr'] = agg.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)
    agg['roas'] = agg.apply(
        lambda r: r['arppu'] / KPI_PHP_USD_RATE / (r['cost'] / r['ftd']) if r['ftd'] > 0 and r['cost'] > 0 else 0, axis=1)

    agg['team'] = agg['agent'].map(TEAM_MAP).fillna('Unknown')
    agg['date_label'] = agg['date'].dt.strftime('%b %d (%a)')

    return agg.sort_values(['agent', 'date'])


def day_totals(df, date):
    """Get aggregate totals for a specific date."""
    rows = df[df['date'] == date]
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
def render_overview(daily, dates, sel_date, prev_date):
    curr = day_totals(daily, sel_date)
    prev = day_totals(daily, prev_date) if prev_date else {}

    if not curr:
        st.warning("No data for selected date.")
        return

    sel_label = sel_date.strftime('%b %d, %Y (%A)')
    prev_label = prev_date.strftime('%b %d (%a)') if prev_date else None
    st.markdown(f"**{sel_label}**" + (f" vs {prev_label}" if prev_label else ""))

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
                delta = f"{pct:+.1f}% DoD"
            st.metric(mc['label'], mc['fmt'](val), delta, delta_color=delta_color)

    # DoD comparison table
    st.markdown("#### Day-over-Day Comparison")
    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Metric</th>'
    if prev_date:
        html += f'<th style="{TH}">{prev_label}</th>'
    html += f'<th style="{TH}">{sel_date.strftime("%b %d")}</th>'
    if prev_date:
        html += f'<th style="{TH}">DoD</th>'
    html += '</tr>'

    for m, mc in METRIC_CONFIG.items():
        c_val = curr.get(m, 0)
        p_val = prev.get(m, 0)
        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{mc["label"]}</td>'
        if prev_date:
            html += f'<td style="{TD}">{mc["fmt"](p_val)}</td>'
        html += f'<td style="{TD};font-weight:600">{mc["fmt"](c_val)}</td>'
        if prev_date:
            html += f'<td style="{TD}">{delta_html(c_val, p_val, mc["hib"])}</td>'
        html += '</tr>'
    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Top / Bottom performers
    date_data = daily[daily['date'] == sel_date]
    if not date_data.empty and len(date_data) > 1:
        st.markdown("#### Top & Bottom Performers")
        for metric, label, hib in [('cpa', 'CPA', False), ('roas', 'ROAS', True), ('conv_rate', 'Conv Rate', True)]:
            mc = METRIC_CONFIG[metric]
            active = date_data[date_data[metric] > 0] if metric in ('roas', 'cpa') else date_data
            if len(active) < 2:
                continue
            best = active.loc[active[metric].idxmax()] if hib else active.loc[active[metric].idxmin()]
            worst = active.loc[active[metric].idxmin()] if hib else active.loc[active[metric].idxmax()]
            c1, c2 = st.columns(2)
            with c1:
                st.success(f"Best {label}: **{best['agent']}** ({mc['fmt'](best[metric])})")
            with c2:
                st.error(f"Worst {label}: **{worst['agent']}** ({mc['fmt'](worst[metric])})")


# ══════════════════════════════════════════════════════════════════════
# Tab 2: Agent Breakdown
# ══════════════════════════════════════════════════════════════════════
def render_agents(daily, sel_date, prev_date):
    date_data = daily[daily['date'] == sel_date].sort_values('agent')
    if date_data.empty:
        st.warning("No agent data for selected date.")
        return

    prev_data = daily[daily['date'] == prev_date] if prev_date else pd.DataFrame()

    # Agent comparison table
    st.markdown("#### All Agents")
    show_metrics = ['cost', 'register', 'ftd', 'cpa', 'conv_rate', 'ctr', 'roas']

    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Agent</th>'
    for m in show_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for _, row in date_data.iterrows():
        agent = row['agent']
        prev_row = prev_data[prev_data['agent'] == agent].iloc[0] if not prev_data.empty and agent in prev_data['agent'].values else None

        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{agent}</td>'
        for m in show_metrics:
            mc = METRIC_CONFIG[m]
            val = row[m]
            dod = ""
            if prev_row is not None:
                dod = " " + delta_html(val, prev_row[m], mc['hib'])
            html += f'<td style="{TD}">{mc["fmt"](val)}{dod}</td>'
        html += '</tr>'

    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Agent ranking
    st.markdown("#### Rankings")
    for metric, label, hib, medal in [
        ('cpa', 'CPA (lowest)', False, True),
        ('roas', 'ROAS (highest)', True, True),
        ('conv_rate', 'Conv Rate (highest)', True, True),
    ]:
        active = date_data[date_data[metric] > 0] if metric in ('roas', 'cpa') else date_data
        if active.empty:
            continue
        ranked = active.sort_values(metric, ascending=not hib).reset_index(drop=True)
        medals = ['🥇', '🥈', '🥉']
        parts = []
        for i, (_, r) in enumerate(ranked.head(3).iterrows()):
            m_icon = medals[i] if i < 3 else f"{i+1}."
            parts.append(f"{m_icon} {r['agent']} ({METRIC_CONFIG[metric]['fmt'](r[metric])})")
        st.markdown(f"**{label}:** {' | '.join(parts)}")


# ══════════════════════════════════════════════════════════════════════
# Tab 3: Team Breakdown
# ══════════════════════════════════════════════════════════════════════
def render_teams(daily, sel_date, prev_date):
    date_data = daily[daily['date'] == sel_date]
    if date_data.empty:
        st.warning("No team data for selected date.")
        return

    prev_data = daily[daily['date'] == prev_date] if prev_date else pd.DataFrame()

    # Team summary
    show_metrics = ['cost', 'register', 'ftd', 'cpa', 'conv_rate', 'roas']

    html = '<table style="width:100%;border-collapse:collapse;margin:8px 0">'
    html += f'<tr style="background:#f1f5f9;color:#1e293b"><th style="{TH}">Team</th>'
    for m in show_metrics:
        html += f'<th style="{TH}">{METRIC_CONFIG[m]["label"]}</th>'
    html += '</tr>'

    for team in TEAM_NAMES:
        team_data = date_data[date_data['team'] == team]
        if team_data.empty:
            continue
        prev_team = prev_data[prev_data['team'] == team] if not prev_data.empty else pd.DataFrame()

        vals = {
            'cost': team_data['cost'].sum(),
            'register': team_data['register'].sum(),
            'ftd': team_data['ftd'].sum(),
        }
        vals['cpa'] = vals['cost'] / vals['ftd'] if vals['ftd'] > 0 else 0
        vals['conv_rate'] = vals['ftd'] / vals['register'] * 100 if vals['register'] > 0 else 0
        vals['roas'] = (team_data['arppu'].mean() / KPI_PHP_USD_RATE / vals['cpa']) if vals['cpa'] > 0 else 0

        prev_vals = {}
        if not prev_team.empty:
            prev_vals['cost'] = prev_team['cost'].sum()
            prev_vals['register'] = prev_team['register'].sum()
            prev_vals['ftd'] = prev_team['ftd'].sum()
            prev_vals['cpa'] = prev_vals['cost'] / prev_vals['ftd'] if prev_vals['ftd'] > 0 else 0
            prev_vals['conv_rate'] = prev_vals['ftd'] / prev_vals['register'] * 100 if prev_vals['register'] > 0 else 0
            prev_vals['roas'] = (prev_team['arppu'].mean() / KPI_PHP_USD_RATE / prev_vals['cpa']) if prev_vals.get('cpa', 0) > 0 else 0

        html += f'<tr style="background:#ffffff;color:#1e293b">'
        html += f'<td style="{TD};font-weight:600;text-align:left">{team}</td>'
        for m in show_metrics:
            mc = METRIC_CONFIG[m]
            val = vals.get(m, 0)
            dod = ""
            if prev_vals:
                dod = " " + delta_html(val, prev_vals.get(m, 0), mc['hib'])
            html += f'<td style="{TD}">{mc["fmt"](val)}{dod}</td>'
        html += '</tr>'

    html += '</table>'
    st.markdown(html, unsafe_allow_html=True)

    # Team member breakdown
    st.markdown("#### Team Members")
    for team in TEAM_NAMES:
        team_agents = date_data[date_data['team'] == team]
        if team_agents.empty:
            continue
        with st.expander(f"{team} ({len(team_agents)} agents)", expanded=True):
            for _, row in team_agents.sort_values('ftd', ascending=False).iterrows():
                cols = st.columns([2, 1, 1, 1, 1, 1])
                cols[0].markdown(f"**{row['agent']}**")
                cols[1].metric("Cost", fmt_cost(row['cost']))
                cols[2].metric("FTD", fmt_num(row['ftd']))
                cols[3].metric("CPA", fmt_cost(row['cpa']))
                cols[4].metric("Conv", fmt_pct(row['conv_rate']))
                cols[5].metric("ROAS", fmt_roas(row['roas']))


# ══════════════════════════════════════════════════════════════════════
# Tab 4: Trends (Rolling)
# ══════════════════════════════════════════════════════════════════════
def render_trends(daily, dates):
    if len(dates) < 2:
        st.warning("Need at least 2 days of data for trends.")
        return

    # Overall daily totals
    overall = daily.groupby('date').agg(
        cost=('cost', 'sum'), ftd=('ftd', 'sum'),
        register=('register', 'sum'), clicks=('clicks', 'sum'),
        impressions=('impressions', 'sum'),
    ).reset_index().sort_values('date')
    overall['cpa'] = overall.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    overall['conv_rate'] = overall.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    overall['ctr'] = overall.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)
    overall['date_label'] = overall['date'].dt.strftime('%b %d')

    # Cost + FTD dual bar
    st.markdown("#### Cost & FTD Trend")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=overall['date_label'], y=overall['cost'], name='Cost ($)', marker_color='#3b82f6', yaxis='y'))
    fig.add_trace(go.Bar(x=overall['date_label'], y=overall['ftd'], name='FTD', marker_color='#22c55e', yaxis='y2'))
    fig.update_layout(
        yaxis=dict(title='Cost ($)', side='left'),
        yaxis2=dict(title='FTD', side='right', overlaying='y'),
        barmode='group', height=350, margin=dict(t=30, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    # CPA + Conv Rate + CTR lines
    st.markdown("#### Efficiency Metrics")
    c1, c2, c3 = st.columns(3)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=overall['date_label'], y=overall['cpa'], mode='lines+markers', name='CPA', line=dict(color='#ef4444')))
        fig.update_layout(title='CPA ($)', height=250, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=overall['date_label'], y=overall['conv_rate'], mode='lines+markers', name='Conv Rate', line=dict(color='#8b5cf6')))
        fig.update_layout(title='Conv Rate (%)', height=250, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=overall['date_label'], y=overall['ctr'], mode='lines+markers', name='CTR', line=dict(color='#f59e0b')))
        fig.update_layout(title='CTR (%)', height=250, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Per-agent trend
    st.markdown("#### Per-Agent Trend")
    metric_sel = st.selectbox("Select Metric", ['cost', 'ftd', 'cpa', 'conv_rate', 'ctr'], format_func=lambda x: METRIC_CONFIG[x]['label'], key='da_agent_metric')
    fig = go.Figure()
    colors = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4']
    for i, agent in enumerate(sorted(daily['agent'].unique())):
        agent_df = daily[daily['agent'] == agent].sort_values('date')
        fig.add_trace(go.Scatter(
            x=agent_df['date'].dt.strftime('%b %d'), y=agent_df[metric_sel],
            mode='lines+markers', name=agent, line=dict(color=colors[i % len(colors)]),
        ))
    fig.update_layout(height=350, margin=dict(t=30, b=30), legend=dict(orientation='h', yanchor='bottom', y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    # 7-day rolling average
    if len(dates) >= 7:
        st.markdown("#### 7-Day Rolling Average")
        overall_sorted = overall.sort_values('date')
        overall_sorted['cost_7d'] = overall_sorted['cost'].rolling(7, min_periods=1).mean()
        overall_sorted['ftd_7d'] = overall_sorted['ftd'].rolling(7, min_periods=1).mean()
        overall_sorted['cpa_7d'] = overall_sorted['cpa'].rolling(7, min_periods=1).mean()

        c1, c2, c3 = st.columns(3)
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=overall_sorted['date_label'], y=overall_sorted['cost'], name='Daily', marker_color='#93c5fd'))
            fig.add_trace(go.Scatter(x=overall_sorted['date_label'], y=overall_sorted['cost_7d'], name='7D Avg', line=dict(color='#1d4ed8', width=3)))
            fig.update_layout(title='Cost ($)', height=250, margin=dict(t=40, b=20), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=overall_sorted['date_label'], y=overall_sorted['ftd'], name='Daily', marker_color='#86efac'))
            fig.add_trace(go.Scatter(x=overall_sorted['date_label'], y=overall_sorted['ftd_7d'], name='7D Avg', line=dict(color='#15803d', width=3)))
            fig.update_layout(title='FTD', height=250, margin=dict(t=40, b=20), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with c3:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=overall_sorted['date_label'], y=overall_sorted['cpa'], name='Daily', marker_color='#fca5a5'))
            fig.add_trace(go.Scatter(x=overall_sorted['date_label'], y=overall_sorted['cpa_7d'], name='7D Avg', line=dict(color='#b91c1c', width=3)))
            fig.update_layout(title='CPA ($)', height=250, margin=dict(t=40, b=20), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════
# Tab 5: Analysis & Insights
# ══════════════════════════════════════════════════════════════════════
def render_analysis(daily, sel_date, prev_date):
    curr = day_totals(daily, sel_date)
    prev = day_totals(daily, prev_date) if prev_date else {}

    if not curr:
        st.warning("No data for analysis.")
        return

    sel_label = sel_date.strftime('%B %d, %Y')
    prev_label = prev_date.strftime('%B %d') if prev_date else None

    # Executive Summary
    st.markdown("#### Executive Summary")
    parts = []
    parts.append(f"On **{sel_label}**, total ad spend was **\\${curr['cost']:,.2f}** generating **{int(curr['ftd'])}** FTD from **{int(curr['register'])}** registrations.")

    if prev:
        cost_chg = _pct_change(curr['cost'], prev['cost'])
        ftd_chg = _pct_change(curr['ftd'], prev['ftd'])
        cpa_chg = _pct_change(curr['cpa'], prev['cpa'])
        parts.append(f"Compared to {prev_label}:")
        parts.append(f"- Cost {_direction_word(cost_chg, True)}")
        parts.append(f"- FTD {_direction_word(ftd_chg, True)}")
        parts.append(f"- CPA {_direction_word(cpa_chg, False)}")

    st.markdown("\n".join(parts))

    # Agent Performance
    date_data = daily[daily['date'] == sel_date]
    if not date_data.empty:
        st.markdown("#### Agent Performance Insights")
        best_ftd = date_data.loc[date_data['ftd'].idxmax()]
        best_cpa = date_data[date_data['cpa'] > 0]
        if not best_cpa.empty:
            best_cpa = best_cpa.loc[best_cpa['cpa'].idxmin()]
            st.markdown(f"- **Top FTD producer**: {best_ftd['agent']} with {int(best_ftd['ftd'])} FTD (\\${best_ftd['cost']:,.2f} spend)")
            st.markdown(f"- **Most efficient (CPA)**: {best_cpa['agent']} at \\${best_cpa['cpa']:,.2f}/FTD")

        # Agent changes vs yesterday
        if prev_date:
            prev_data = daily[daily['date'] == prev_date]
            if not prev_data.empty:
                st.markdown("**Day-over-Day Agent Changes:**")
                for _, row in date_data.sort_values('ftd', ascending=False).iterrows():
                    agent = row['agent']
                    prev_row = prev_data[prev_data['agent'] == agent]
                    if not prev_row.empty:
                        ftd_diff = int(row['ftd'] - prev_row.iloc[0]['ftd'])
                        cost_diff = row['cost'] - prev_row.iloc[0]['cost']
                        if ftd_diff != 0 or abs(cost_diff) > 10:
                            ftd_s = f"+{ftd_diff}" if ftd_diff > 0 else str(ftd_diff)
                            cost_s = f"+\\${cost_diff:,.0f}" if cost_diff > 0 else f"-\\${abs(cost_diff):,.0f}"
                            st.markdown(f"- **{agent}**: FTD {ftd_s}, Cost {cost_s}")

    # Recommendations
    if prev:
        st.markdown("#### Recommendations")
        recs = []
        if curr.get('cpa', 0) > prev.get('cpa', 0) * 1.1:
            recs.append("CPA increased significantly. Review ad targeting and creative performance.")
        if curr.get('conv_rate', 0) < prev.get('conv_rate', 0) * 0.9:
            recs.append("Conversion rate dropped. Check landing page performance and registration flow.")
        if curr.get('cost', 0) > prev.get('cost', 0) * 1.2 and curr.get('ftd', 0) <= prev.get('ftd', 0):
            recs.append("Spend increased but FTD flat/declined. Evaluate campaign efficiency.")
        if curr.get('ftd', 0) > prev.get('ftd', 0) * 1.1 and curr.get('cpa', 0) <= prev.get('cpa', 0):
            recs.append("Strong day - FTD up with stable/lower CPA. Consider scaling successful campaigns.")
        if not recs:
            recs.append("Performance is stable. Continue monitoring and optimizing campaigns.")
        for r in recs:
            st.markdown(f"- {r}")


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════
def main():
    st.title("Daily Analysis")
    st.markdown("Day-over-day ad performance analysis")

    with st.sidebar:
        if st.button("Refresh Data", type="primary", use_container_width=True):
            refresh_agent_performance_data()
            st.rerun()

    # Load data
    ptab = load_agent_performance_data()
    daily_df = ptab.get('daily', pd.DataFrame()) if ptab else pd.DataFrame()

    if daily_df is None or daily_df.empty:
        st.error("No P-tab data available.")
        return

    daily = build_daily_data(daily_df)
    if daily.empty:
        st.error("No daily data after processing.")
        return

    dates = sorted(daily['date'].unique())

    # Date selector
    with st.sidebar:
        st.subheader("Date Selection")
        date_options = sorted(dates, reverse=True)
        date_labels = {d: pd.Timestamp(d).strftime('%b %d, %Y (%a)') for d in date_options}

        sel_idx = 0
        sel_date = st.selectbox(
            "Select Date",
            date_options,
            index=sel_idx,
            format_func=lambda d: date_labels[d],
        )

        # Previous date
        sel_pos = list(date_options).index(sel_date)
        prev_date = date_options[sel_pos + 1] if sel_pos + 1 < len(date_options) else None

        if prev_date:
            st.caption(f"Comparing vs {date_labels[prev_date]}")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview", "Agent Breakdown", "Team Breakdown", "Trends", "Analysis & Insights"
    ])

    with tab1:
        render_overview(daily, dates, sel_date, prev_date)
    with tab2:
        render_agents(daily, sel_date, prev_date)
    with tab3:
        render_teams(daily, sel_date, prev_date)
    with tab4:
        render_trends(daily, dates)
    with tab5:
        render_analysis(daily, sel_date, prev_date)


main()
