"""
Weekly KPI Dashboard — Per-agent weekly KPI scores with Week-over-Week comparison.
Aggregates P-tab daily data into Tue-Mon weeks and scores CPA, ROAS, CVR, CTR.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import (
    load_agent_performance_data,
    refresh_agent_performance_data,
    score_kpi,
)
from config import (
    AGENT_PERFORMANCE_TABS,
    KPI_SCORING,
    KPI_PHP_USD_RATE,
    EXCLUDED_FROM_REPORTING,
    SIDEBAR_HIDE_CSS,
)

KPI_AGENTS = [t for t in AGENT_PERFORMANCE_TABS if t['agent'].upper() not in EXCLUDED_FROM_REPORTING]


# ── Tue-Mon week helpers ─────────────────────────────────────────────
def get_tue_mon_week(date):
    """Week starts Tuesday, ends Monday."""
    adjusted = date - timedelta(days=(date.weekday() - 1) % 7)
    return adjusted.isocalendar()[0], adjusted.isocalendar()[1]


def build_weekly_agent_df(daily_df):
    """Aggregate daily P-tab data into Tue-Mon weekly rows per agent.
    Returns DataFrame with columns: agent, week_key, week_label, days,
        cost, register, ftd, impressions, clicks, arppu,
        cpa, roas, cvr, ctr + score columns.
    """
    if daily_df is None or daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])

    df['week_info'] = df['date'].apply(get_tue_mon_week)
    df['week_key'] = df['week_info'].apply(lambda x: f"{x[0]}-W{x[1]:02d}")

    # Aggregate per agent per week
    agg = df.groupby(['agent', 'week_key']).agg(
        cost=('cost', 'sum'),
        register=('register', 'sum'),
        ftd=('ftd', 'sum'),
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
        date_start=('date', 'min'),
        date_end=('date', 'max'),
    ).reset_index()

    # ARPPU: last non-zero value per agent per week
    arppu_rows = []
    for (agent, wk), grp in df.groupby(['agent', 'week_key']):
        grp_sorted = grp.sort_values('date')
        arppu_col = pd.to_numeric(grp_sorted['arppu'], errors='coerce').fillna(0)
        nonzero = arppu_col[arppu_col > 0]
        arppu_rows.append({'agent': agent, 'week_key': wk, 'arppu': nonzero.iloc[-1] if len(nonzero) > 0 else 0})
    arppu_df = pd.DataFrame(arppu_rows)
    agg = agg.merge(arppu_df, on=['agent', 'week_key'], how='left')
    agg['arppu'] = agg['arppu'].fillna(0)

    # Derived metrics
    agg['cpa'] = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    cpd = agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agg['roas'] = agg.apply(
        lambda r: r['arppu'] / KPI_PHP_USD_RATE / (r['cost'] / r['ftd']) if r['ftd'] > 0 and r['cost'] > 0 else 0, axis=1)
    agg['cvr'] = agg.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agg['ctr'] = agg.apply(lambda r: r['clicks'] / r['impressions'] * 100 if r['impressions'] > 0 else 0, axis=1)

    # Scores
    for metric in ['cpa', 'roas', 'cvr', 'ctr']:
        agg[f'{metric}_score'] = agg[metric].apply(lambda v: score_kpi(metric, v)[0])

    agg['auto_weighted'] = (
        agg['cpa_score'] * KPI_SCORING['cpa']['weight'] +
        agg['roas_score'] * KPI_SCORING['roas']['weight'] +
        agg['cvr_score'] * KPI_SCORING['cvr']['weight'] +
        agg['ctr_score'] * KPI_SCORING['ctr']['weight']
    ).round(2)

    # Week labels and day counts
    agg['days'] = (agg['date_end'] - agg['date_start']).dt.days + 1
    agg['week_label'] = agg.apply(
        lambda r: f"{r['date_start'].strftime('%b %d')} – {r['date_end'].strftime('%b %d')}", axis=1)

    return agg.sort_values(['agent', 'week_key'])


# ── Display helpers ───────────────────────────────────────────────────
def score_badge(score):
    if score == 0:
        return '<span style="color:#64748b">-</span>'
    colors = {1: '#ef4444', 2: '#f97316', 3: '#eab308', 4: '#22c55e'}
    c = colors.get(score, '#64748b')
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold">{score}</span>'


def arrow_delta(curr, prev, higher_is_better=True):
    """Return (arrow_html, pct_str) for WoW comparison."""
    if prev == 0 and curr == 0:
        return '<span style="color:#64748b">—</span>', '—'
    if prev == 0:
        return '<span style="color:#22c55e">▲ new</span>', 'new'
    pct = (curr - prev) / abs(prev) * 100
    if abs(pct) < 0.1:
        return '<span style="color:#64748b">→ 0%</span>', '0%'
    is_good = (pct > 0) == higher_is_better
    color = '#22c55e' if is_good else '#ef4444'
    arrow = '▲' if pct > 0 else '▼'
    return f'<span style="color:{color}">{arrow} {abs(pct):.1f}%</span>', f'{pct:+.1f}%'


def wow_table(prev_label, curr_label, metrics, prev_vals, curr_vals, higher_is_better_map):
    """Build a 3-row WoW comparison HTML table."""
    th_style = 'padding:6px 10px;text-align:center;border:1px solid #334155'
    td_style = 'padding:5px 10px;text-align:center;border:1px solid #334155'

    html = '<table style="width:100%;border-collapse:collapse;font-size:13px;margin:8px 0">'
    # Header
    html += f'<tr style="background:#1e293b;color:#fff"><th style="{th_style}">Week</th>'
    for m in metrics:
        html += f'<th style="{th_style}">{m}</th>'
    html += '</tr>'
    # Prev row
    html += f'<tr style="background:#0f172a;color:#94a3b8"><td style="{td_style}">{prev_label}</td>'
    for v in prev_vals:
        html += f'<td style="{td_style}">{v}</td>'
    html += '</tr>'
    # Curr row
    html += f'<tr style="background:#0f172a;color:#f1f5f9;font-weight:bold"><td style="{td_style}">{curr_label}</td>'
    for v in curr_vals:
        html += f'<td style="{td_style}">{v}</td>'
    html += '</tr>'
    # Delta row
    html += f'<tr style="background:#0f172a"><td style="{td_style};color:#94a3b8">Δ WoW</td>'
    for i, m in enumerate(metrics):
        p_num = prev_vals[i] if isinstance(prev_vals[i], (int, float)) else 0
        c_num = curr_vals[i] if isinstance(curr_vals[i], (int, float)) else 0
        # Try parse from formatted strings
        try:
            p_num = float(str(prev_vals[i]).replace('$', '').replace('%', '').replace('x', '').replace(',', '').replace('₱', ''))
        except:
            p_num = 0
        try:
            c_num = float(str(curr_vals[i]).replace('$', '').replace('%', '').replace('x', '').replace(',', '').replace('₱', ''))
        except:
            c_num = 0
        hib = higher_is_better_map.get(m, True)
        a, _ = arrow_delta(c_num, p_num, hib)
        html += f'<td style="{td_style}">{a}</td>'
    html += '</tr></table>'
    return html


# ── Main render ───────────────────────────────────────────────────────
def render_content(key_prefix="wk"):
    agent_names = ["All Agents"] + [t['agent'] for t in KPI_AGENTS]

    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    with ctrl1:
        selected = st.selectbox("Agent", agent_names, key=f"{key_prefix}_agent")
    with ctrl3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", type="primary", key=f"{key_prefix}_ref"):
            refresh_agent_performance_data()
            st.rerun()

    ptab_data = load_agent_performance_data()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
    weekly = build_weekly_agent_df(daily_df)

    if weekly.empty:
        st.warning("No daily data available to build weekly KPIs.")
        return

    weeks_sorted = sorted(weekly['week_key'].unique())

    # Week selector
    week_labels = {}
    for wk in weeks_sorted:
        subset = weekly[weekly['week_key'] == wk].iloc[0]
        days = int(subset['days'])
        tag = f" ⚠️ ({days}/7 days)" if days < 7 else ""
        week_labels[wk] = f"{subset['week_label']}{tag}"

    with ctrl2:
        sel_wk_idx = st.selectbox(
            "Week", range(len(weeks_sorted)),
            index=len(weeks_sorted) - 1,
            format_func=lambda i: week_labels[weeks_sorted[i]],
            key=f"{key_prefix}_week")
    sel_week = weeks_sorted[sel_wk_idx]
    prev_week = weeks_sorted[sel_wk_idx - 1] if sel_wk_idx > 0 else None

    st.info("Weekly KPIs cover **CPA, ROAS, CVR, CTR** only (4 of 7 auto KPIs). Account Dev, A/B Testing, and Reporting are monthly-only data sources.")

    # ──────────────────────────────────────────────────────────────────
    if selected == "All Agents":
        st.subheader(f"All Agents — {week_labels[sel_week]}")

        wk_data = weekly[weekly['week_key'] == sel_week]
        prev_data = weekly[weekly['week_key'] == prev_week] if prev_week else pd.DataFrame()

        # Summary table
        th = 'padding:6px;text-align:center;border:1px solid #334155'
        td = 'padding:5px;text-align:center;border:1px solid #334155'
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += f'<tr style="background:#1e293b;color:#fff">'
        for c in ['Agent', 'CPA', 'Score', 'ROAS', 'Score', 'CVR', 'Score', 'CTR', 'Score', 'Weekly Auto']:
            html += f'<th style="{th}">{c}</th>'
        html += '</tr>'

        for _, r in wk_data.iterrows():
            agent = r['agent']
            html += f'<tr style="background:#0f172a;color:#e2e8f0;border:1px solid #334155">'
            html += f'<td style="{td};font-weight:bold;color:#f1f5f9">{agent}</td>'
            html += f'<td style="{td}">${r["cpa"]:.2f}</td>'
            html += f'<td style="{td}">{score_badge(int(r["cpa_score"]))}</td>'
            html += f'<td style="{td}">{r["roas"]:.4f}x</td>'
            html += f'<td style="{td}">{score_badge(int(r["roas_score"]))}</td>'
            html += f'<td style="{td}">{r["cvr"]:.1f}%</td>'
            html += f'<td style="{td}">{score_badge(int(r["cvr_score"]))}</td>'
            html += f'<td style="{td}">{r["ctr"]:.2f}%</td>'
            html += f'<td style="{td}">{score_badge(int(r["ctr_score"]))}</td>'
            html += f'<td style="{td};font-weight:bold;color:#60a5fa">{r["auto_weighted"]:.2f}</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

        # WoW comparison
        if prev_week and not prev_data.empty:
            st.markdown("#### Week-over-Week Comparison")
            metrics = ['CPA', 'ROAS', 'CVR', 'CTR', 'Weighted']
            hib = {'CPA': False, 'ROAS': True, 'CVR': True, 'CTR': True, 'Weighted': True}

            for _, r in wk_data.iterrows():
                agent = r['agent']
                prev_row = prev_data[prev_data['agent'] == agent]
                if prev_row.empty:
                    continue
                pr = prev_row.iloc[0]
                st.markdown(f"**{agent}**")
                st.markdown(wow_table(
                    week_labels.get(prev_week, prev_week), week_labels.get(sel_week, sel_week),
                    metrics,
                    [f"${pr['cpa']:.2f}", f"{pr['roas']:.4f}x", f"{pr['cvr']:.1f}%", f"{pr['ctr']:.2f}%", f"{pr['auto_weighted']:.2f}"],
                    [f"${r['cpa']:.2f}", f"{r['roas']:.4f}x", f"{r['cvr']:.1f}%", f"{r['ctr']:.2f}%", f"{r['auto_weighted']:.2f}"],
                    hib,
                ), unsafe_allow_html=True)

        # Grouped bar chart
        st.subheader("Auto Scores by Agent")
        agents = wk_data['agent'].tolist()
        fig = go.Figure()
        for metric, label, color in [
            ('cpa_score', 'CPA', '#3b82f6'), ('roas_score', 'ROAS', '#22c55e'),
            ('cvr_score', 'CVR', '#a855f7'), ('ctr_score', 'CTR', '#f59e0b'),
        ]:
            fig.add_trace(go.Bar(name=label, x=agents, y=wk_data[metric].tolist(), marker_color=color))
        fig.update_layout(barmode='group', yaxis=dict(title='Score (1-4)', range=[0, 4.5]),
                          height=400, margin=dict(t=30, b=40), legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_bar")

    # ──────────────────────────────────────────────────────────────────
    else:
        agent_name = selected
        agent_weeks = weekly[weekly['agent'] == agent_name].sort_values('week_key')
        if agent_weeks.empty:
            st.warning(f"No weekly data for {agent_name}")
            return

        curr = agent_weeks[agent_weeks['week_key'] == sel_week]
        if curr.empty:
            st.warning(f"No data for {agent_name} in selected week")
            return
        curr = curr.iloc[0]

        prev_row = agent_weeks[agent_weeks['week_key'] == prev_week].iloc[0] if (
            prev_week and not agent_weeks[agent_weeks['week_key'] == prev_week].empty) else None

        st.subheader(f"{agent_name} — {week_labels[sel_week]}")

        # Metric cards with WoW delta
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            delta = f"{((curr['cpa'] - prev_row['cpa']) / prev_row['cpa'] * 100):+.1f}% WoW" if prev_row is not None and prev_row['cpa'] > 0 else None
            st.metric("CPA", f"${curr['cpa']:.2f}", delta, delta_color="inverse")
        with c2:
            delta = f"{((curr['roas'] - prev_row['roas']) / prev_row['roas'] * 100):+.1f}% WoW" if prev_row is not None and prev_row['roas'] > 0 else None
            st.metric("ROAS", f"{curr['roas']:.4f}x", delta)
        with c3:
            delta = f"{((curr['cvr'] - prev_row['cvr']) / prev_row['cvr'] * 100):+.1f}% WoW" if prev_row is not None and prev_row['cvr'] > 0 else None
            st.metric("CVR", f"{curr['cvr']:.1f}%", delta)
        with c4:
            delta = f"{((curr['ctr'] - prev_row['ctr']) / prev_row['ctr'] * 100):+.1f}% WoW" if prev_row is not None and prev_row['ctr'] > 0 else None
            st.metric("CTR", f"{curr['ctr']:.2f}%", delta)
        with c5:
            delta = f"{((curr['auto_weighted'] - prev_row['auto_weighted']) / prev_row['auto_weighted'] * 100):+.1f}% WoW" if prev_row is not None and prev_row['auto_weighted'] > 0 else None
            st.metric("Weekly Auto", f"{curr['auto_weighted']:.2f}", delta)

        # Full weekly history table
        st.divider()
        st.subheader("Weekly History")
        th = 'padding:6px;text-align:center;border:1px solid #334155'
        td = 'padding:5px;text-align:center;border:1px solid #334155'
        html = '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        html += f'<tr style="background:#1e293b;color:#fff">'
        for c in ['Week', 'Days', 'CPA', 'Score', 'ROAS', 'Score', 'CVR', 'Score', 'CTR', 'Score', 'Weighted']:
            html += f'<th style="{th}">{c}</th>'
        html += '</tr>'

        prev_r = None
        for _, r in agent_weeks.iterrows():
            incomplete = ' ⚠️' if r['days'] < 7 else ''
            html += f'<tr style="background:#0f172a;color:#e2e8f0">'
            html += f'<td style="{td};white-space:nowrap">{r["week_label"]}{incomplete}</td>'
            html += f'<td style="{td}">{int(r["days"])}</td>'

            for metric, fmt, hib in [
                ('cpa', '${:.2f}', False), ('roas', '{:.4f}x', True),
                ('cvr', '{:.1f}%', True), ('ctr', '{:.2f}%', True),
            ]:
                val = r[metric]
                html += f'<td style="{td}">{fmt.format(val)}'
                if prev_r is not None and prev_r[metric] > 0:
                    a, _ = arrow_delta(val, prev_r[metric], hib)
                    html += f' <span style="font-size:11px">{a}</span>'
                html += '</td>'
                html += f'<td style="{td}">{score_badge(int(r[f"{metric}_score"]))}</td>'

            html += f'<td style="{td};font-weight:bold;color:#60a5fa">{r["auto_weighted"]:.2f}</td>'
            html += '</tr>'
            prev_r = r
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

        # Score trend line chart
        st.divider()
        st.subheader("Score Trend")
        fig = go.Figure()
        for metric, label, color in [
            ('cpa_score', 'CPA', '#3b82f6'), ('roas_score', 'ROAS', '#22c55e'),
            ('cvr_score', 'CVR', '#a855f7'), ('ctr_score', 'CTR', '#f59e0b'),
        ]:
            fig.add_trace(go.Scatter(
                x=agent_weeks['week_label'], y=agent_weeks[metric],
                mode='lines+markers', name=label, line=dict(color=color, width=2),
            ))
        fig.update_layout(yaxis=dict(title='Score (1-4)', range=[0, 4.5]),
                          height=350, margin=dict(t=30, b=40), legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_trend")


def main():
    st.set_page_config(page_title="Weekly KPI", page_icon="📅", layout="wide")
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("📅 Weekly KPI Monitoring")
    render_content(key_prefix="wk")


if not hasattr(st, '_is_recharge_import'):
    main()
