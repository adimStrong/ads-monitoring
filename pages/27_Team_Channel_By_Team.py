"""
Team Channel Performance by Team
Refactored for combined Team page with render_content().
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_team_channel_data, refresh_team_channel_data
from config import CHANNEL_ROI_ENABLED, SIDEBAR_HIDE_CSS

CHANNEL_TO_TEAM = {
    'FB-FB-FB-DEERPROMO02': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO04': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO07': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO09': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO12': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO13': 'JASON / SHILA',
    'FB-FB-FB-DEERPROMO03': 'RON / ADRIAN',
    'FB-FB-FB-DEERPROMO06': 'RON / ADRIAN',
    'FB-FB-FB-DEERPROMO08': 'RON / ADRIAN',
    'FB-FB-FB-DEERPROMO10': 'RON / ADRIAN',
    'FB-FB-FB-DEERPROMO11': 'RON / ADRIAN',
    'FB-FB-FB-DEERPROMO01': 'MIKA / JOMAR',
    'FB-FB-FB-DEERPROMO05': 'MIKA / JOMAR',
}

TEAM_COLORS = {
    'JASON / SHILA': '#3b82f6',
    'RON / ADRIAN': '#22c55e',
    'MIKA / JOMAR': '#a855f7',
}

TEAM_ORDER = ['JASON / SHILA', 'RON / ADRIAN', 'MIKA / JOMAR']


def format_currency(v):
    return f"${v:,.2f}" if v else "$0.00"


def format_php(v):
    return f"₱{v:,.0f}" if v else "₱0"


def render_content(key_prefix="tc"):
    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI is disabled.")
        return

    with st.spinner("Loading Team Channel data..."):
        data = load_team_channel_data()
        team_actual_df = data.get('team_actual', pd.DataFrame())
        overall_df = data.get('overall', pd.DataFrame())
        daily_df = data.get('daily', pd.DataFrame())

    if team_actual_df.empty:
        st.error("No PER TEAM ACTUAL data available. Check the sheet.")
        return

    # Assign teams to daily data
    if not daily_df.empty:
        daily_df['promo_team'] = daily_df['channel'].map(CHANNEL_TO_TEAM)
        daily_df = daily_df[daily_df['promo_team'].notna()]

    # Inline controls
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.5, 1.5, 1, 1])
    with ctrl3:
        if st.button("Refresh", type="primary", use_container_width=True, key=f"{key_prefix}_refresh"):
            refresh_team_channel_data()
            st.cache_data.clear()
            st.rerun()

    has_daily = not daily_df.empty
    if has_daily:
        min_date = daily_df['date'].min().date()
        max_date = daily_df['date'].max().date()
        default_start = max(min_date, max_date - timedelta(days=30))

        # Session state for All Dates button
        ss_start_key = f'{key_prefix}_start'
        ss_end_key = f'{key_prefix}_end'
        if ss_start_key not in st.session_state:
            st.session_state[ss_start_key] = default_start
        if ss_end_key not in st.session_state:
            st.session_state[ss_end_key] = max_date

        with ctrl4:
            if st.button("All Dates", use_container_width=True, key=f"{key_prefix}_all_dates"):
                st.session_state[ss_start_key] = min_date
                st.session_state[ss_end_key] = max_date
                st.rerun()

        with ctrl1:
            start_date = st.date_input("From", value=st.session_state[ss_start_key],
                                        min_value=min_date, max_value=max_date, key=f"{key_prefix}_from")
        with ctrl2:
            end_date = st.date_input("To", value=st.session_state[ss_end_key],
                                      min_value=min_date, max_value=max_date, key=f"{key_prefix}_to")

        st.session_state[ss_start_key] = start_date
        st.session_state[ss_end_key] = end_date

        filtered_daily = daily_df[
            (daily_df['date'].dt.date >= start_date) &
            (daily_df['date'].dt.date <= end_date)
        ]
    else:
        start_date = datetime.now().date() - timedelta(days=30)
        end_date = datetime.now().date()
        filtered_daily = pd.DataFrame()

    # BUILD DATE-FILTERED TEAM AGGREGATES
    if has_daily and not filtered_daily.empty:
        filtered_team_df = filtered_daily.groupby('promo_team').agg({
            'cost': 'sum', 'registrations': 'sum', 'first_recharge': 'sum', 'total_amount': 'sum',
        }).reset_index().rename(columns={'promo_team': 'team'})

        filtered_team_df['cpfd'] = filtered_team_df.apply(
            lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        filtered_team_df['arppu'] = filtered_team_df.apply(
            lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        filtered_team_df['roas'] = filtered_team_df.apply(
            lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

        ch_map = team_actual_df.set_index('team')['channel_source'].to_dict()
        filtered_team_df['channel_source'] = filtered_team_df['team'].map(ch_map).fillna('')

        filtered_overall = filtered_daily.groupby('channel').agg({
            'cost': 'sum', 'registrations': 'sum', 'first_recharge': 'sum', 'total_amount': 'sum',
        }).reset_index()
        filtered_overall['team'] = filtered_overall['channel'].map(CHANNEL_TO_TEAM)
    else:
        filtered_team_df = team_actual_df.copy()
        filtered_overall = overall_df.copy()

    # HEADER
    date_label = f"{start_date.strftime('%b %d')} – {end_date.strftime('%b %d, %Y')}" if has_daily else ""
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
        <h2 style="margin: 0;">Performance by Team (Promo Mapping)</h2>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{len(filtered_team_df)} teams &bull; {date_label}</p>
    </div>
    """, unsafe_allow_html=True)

    # TEAM TOTALS
    total_cost = filtered_team_df['cost'].sum()
    total_reg = int(filtered_team_df['registrations'].sum())
    total_fr = int(filtered_team_df['first_recharge'].sum())
    total_amt = filtered_team_df['total_amount'].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cost", format_currency(total_cost))
    with col2:
        st.metric("Registrations", f"{total_reg:,}")
    with col3:
        st.metric("1st Recharge", f"{total_fr:,}")
    with col4:
        st.metric("Total Amount", format_php(total_amt))

    st.divider()

    # TEAM CARDS
    st.subheader("Team Summary")
    team_sorted = filtered_team_df.copy()
    team_sorted['sort_order'] = team_sorted['team'].apply(
        lambda x: TEAM_ORDER.index(x) if x in TEAM_ORDER else 99)
    team_sorted = team_sorted.sort_values('sort_order').reset_index(drop=True)

    cols = st.columns(2)
    for idx, (_, r) in enumerate(team_sorted.iterrows()):
        team = r['team']
        color = TEAM_COLORS.get(team, '#64748b')

        if r['roas'] >= 1:
            perf_badge, perf_color = '🏆 Top', '#28a745'
        elif r['roas'] >= 0.4:
            perf_badge, perf_color = '⭐ Good', '#ffc107'
        elif r['roas'] >= 0.25:
            perf_badge, perf_color = '📈 Active', '#17a2b8'
        else:
            perf_badge, perf_color = '⚠️ Low', '#dc3545'

        with cols[idx % 2]:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 1.5rem; border-radius: 12px; border-left: 5px solid {color}; margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #333;">{team}</h3>
                    <span style="background: {perf_color}; color: white; padding: 4px 10px; border-radius: 15px; font-size: 0.75rem;">{perf_badge}</span>
                </div>
                <p style="margin: 4px 0 0 0; font-size: 0.8rem; color: #666;">Channels: {r['channel_source']}</p>
                <hr style="margin: 10px 0; border-color: #dee2e6;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
                    <div><strong>Cost:</strong> ${r['cost']:,.2f}</div>
                    <div><strong>1st Recharge:</strong> {int(r['first_recharge']):,}</div>
                    <div><strong>Registrations:</strong> {int(r['registrations']):,}</div>
                    <div><strong>Amount:</strong> ₱{r['total_amount']:,.0f}</div>
                    <div><strong>CPFD:</strong> ${r['cpfd']:.2f}</div>
                    <div><strong>ARPPU:</strong> ₱{r['arppu']:.2f}</div>
                    <div><strong>ROAS:</strong> {r['roas']:.2f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # PER-CHANNEL BREAKDOWN BY TEAM (columns D-I)
    st.divider()
    st.subheader("Channel Breakdown by Team")

    for team in TEAM_ORDER:
        if filtered_overall.empty:
            break
        if 'team' in filtered_overall.columns:
            team_ch = filtered_overall[filtered_overall['team'] == team].copy()
        else:
            team_channels = [ch for ch, t in CHANNEL_TO_TEAM.items() if t == team]
            team_ch = filtered_overall[filtered_overall['channel'].isin(team_channels)].copy()
        if team_ch.empty:
            continue

        color = TEAM_COLORS.get(team, '#64748b')

        # Calculate derived metrics per channel
        team_ch['cpfd'] = team_ch.apply(
            lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        team_ch['arppu'] = team_ch.apply(
            lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        team_ch['roas'] = team_ch.apply(
            lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
        team_ch = team_ch.sort_values('cost', ascending=False)

        # Team header
        st.markdown(f"<h4 style='color:{color}; margin-bottom:0'>{team}</h4>", unsafe_allow_html=True)

        # Build HTML table with per-channel metrics
        tbl = '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">'
        tbl += '<tr style="background:#1e293b;color:#fff">'
        for col_name in ['Channel', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'ARPPU (₱)', 'CPFD ($)', 'ROAS']:
            tbl += f'<th style="padding:8px;text-align:center;border:1px solid #334155">{col_name}</th>'
        tbl += '</tr>'

        team_total_cost = 0
        team_total_reg = 0
        team_total_fr = 0
        team_total_amt = 0

        for _, ch in team_ch.iterrows():
            short = ch['channel'].replace('FB-FB-FB-', '')
            ch_roas = ch['roas']
            if ch_roas >= 1:
                roas_style = 'color:#22c55e;font-weight:bold'
            elif ch_roas >= 0.4:
                roas_style = 'color:#eab308'
            else:
                roas_style = 'color:#ef4444'

            tbl += f'<tr style="background:#0f172a;color:#e2e8f0;border:1px solid #334155">'
            tbl += f'<td style="padding:8px;border:1px solid #334155;font-weight:bold">{short}</td>'
            tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">${ch["cost"]:,.2f}</td>'
            tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{int(ch["registrations"]):,}</td>'
            tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{int(ch["first_recharge"]):,}</td>'
            tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">₱{ch["total_amount"]:,.0f}</td>'
            tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">₱{ch["arppu"]:,.0f}</td>'
            tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">${ch["cpfd"]:.2f}</td>'
            tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155;{roas_style}">{ch_roas:.2f}</td>'
            tbl += '</tr>'

            team_total_cost += ch['cost']
            team_total_reg += int(ch['registrations'])
            team_total_fr += int(ch['first_recharge'])
            team_total_amt += ch['total_amount']

        # Subtotal row
        sub_cpfd = team_total_cost / team_total_fr if team_total_fr > 0 else 0
        sub_arppu = team_total_amt / team_total_fr if team_total_fr > 0 else 0
        sub_roas = team_total_amt / team_total_cost if team_total_cost > 0 else 0
        tbl += f'<tr style="background:#1e293b;color:#fff;font-weight:bold;border:1px solid #334155">'
        tbl += f'<td style="padding:8px;border:1px solid #334155">TOTAL</td>'
        tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">${team_total_cost:,.2f}</td>'
        tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{team_total_reg:,}</td>'
        tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{team_total_fr:,}</td>'
        tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">₱{team_total_amt:,.0f}</td>'
        tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">₱{sub_arppu:,.0f}</td>'
        tbl += f'<td style="padding:8px;text-align:right;border:1px solid #334155">${sub_cpfd:.2f}</td>'
        tbl += f'<td style="padding:8px;text-align:center;border:1px solid #334155">{sub_roas:.2f}</td>'
        tbl += '</tr>'
        tbl += '</table>'

        st.markdown(tbl, unsafe_allow_html=True)

    # COMPARISON CHARTS
    st.divider()
    st.subheader("Team Comparison")

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Bar(
            x=team_sorted['team'], y=team_sorted['cost'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_sorted['team']],
            text=[f"${v:,.0f}" for v in team_sorted['cost']], textposition='outside',
        ))
        fig.add_hline(y=team_sorted['cost'].mean(), line_dash="dash", annotation_text="Avg")
        fig.update_layout(title='Total Cost ($)', height=380, yaxis_title="USD", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cmp_cost")
    with col2:
        fig = go.Figure(go.Bar(
            x=team_sorted['team'], y=team_sorted['first_recharge'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_sorted['team']],
            text=[f"{int(v):,}" for v in team_sorted['first_recharge']], textposition='outside',
        ))
        fig.add_hline(y=team_sorted['first_recharge'].mean(), line_dash="dash", annotation_text="Avg")
        fig.update_layout(title='1st Recharge Count', height=380, yaxis_title="Count", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cmp_fr")

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Bar(
            x=team_sorted['team'], y=team_sorted['roas'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_sorted['team']],
            text=[f"{v:.2f}" for v in team_sorted['roas']], textposition='outside',
        ))
        fig.add_hline(y=team_sorted['roas'].mean(), line_dash="dash", annotation_text="Avg")
        fig.update_layout(title='ROAS', height=380, yaxis_title="Ratio", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cmp_roas")
    with col2:
        fig = go.Figure(go.Bar(
            x=team_sorted['team'], y=team_sorted['cpfd'],
            marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_sorted['team']],
            text=[f"${v:.2f}" for v in team_sorted['cpfd']], textposition='outside',
        ))
        fig.add_hline(y=team_sorted['cpfd'].mean(), line_dash="dash", annotation_text="Avg")
        fig.update_layout(title='CPFD ($)', height=380, yaxis_title="USD", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_cmp_cpfd")

    # Radar chart
    st.subheader("Team Performance Radar")
    metrics = ['cost', 'registrations', 'first_recharge', 'total_amount', 'roas']
    metric_labels = {'cost': 'Cost', 'registrations': 'Reg', 'first_recharge': '1st Rech',
                     'total_amount': 'Amount', 'roas': 'ROAS'}

    radar_df = team_sorted.copy()
    for col in metrics:
        max_val = radar_df[col].max()
        radar_df[col + '_norm'] = (radar_df[col] / max_val * 100) if max_val > 0 else 0

    fig = go.Figure()
    for _, r in radar_df.iterrows():
        team = r['team']
        fig.add_trace(go.Scatterpolar(
            r=[r.get(f'{m}_norm', 0) for m in metrics],
            theta=[metric_labels.get(m, m) for m in metrics],
            fill='toself',
            name=team,
            line_color=TEAM_COLORS.get(team, '#64748b'),
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True, height=450,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_radar")

    # DAILY TRENDS
    st.divider()
    st.subheader("Daily Trends by Team")

    if has_daily and not filtered_daily.empty:
        daily_by_team = filtered_daily.groupby(['date', 'promo_team']).agg({
            'cost': 'sum', 'registrations': 'sum', 'first_recharge': 'sum', 'total_amount': 'sum',
        }).reset_index()
        daily_by_team['date_only'] = daily_by_team['date'].dt.date
        daily_by_team['cpfd'] = daily_by_team.apply(
            lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

        metric_choice = st.selectbox("Select Metric",
            ['cost', 'registrations', 'first_recharge', 'total_amount', 'cpfd'],
            key=f"{key_prefix}_trend_metric")
        metric_labels_full = {
            'cost': 'Cost ($)', 'registrations': 'Registrations', 'first_recharge': '1st Recharge',
            'total_amount': 'Amount (₱)', 'cpfd': 'CPFD ($)'}

        fig = px.line(
            daily_by_team, x='date_only', y=metric_choice, color='promo_team',
            title=f'{metric_labels_full.get(metric_choice, metric_choice)} Trend by Team',
            markers=True, color_discrete_map=TEAM_COLORS,
        )
        fig.update_layout(height=400, legend=dict(orientation='h', yanchor='bottom', y=-0.3))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_trend_chart")
    else:
        st.info("No daily data available for trend analysis.")

    # LEADERBOARD
    st.divider()
    st.subheader("Team Leaderboard")

    lb = team_sorted.sort_values('roas', ascending=False).reset_index(drop=True)
    lb['rank'] = range(1, len(lb) + 1)

    display_lb = lb[['rank', 'team', 'channel_source', 'cost', 'registrations', 'first_recharge',
                      'cpfd', 'total_amount', 'arppu', 'roas']].copy()
    display_lb.columns = ['#', 'Team', 'Channels', 'Cost ($)', 'Reg', '1st Rech',
                           'CPFD ($)', 'Amount (₱)', 'ARPPU (₱)', 'ROAS']

    st.dataframe(
        display_lb,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Team": st.column_config.TextColumn(width="medium"),
            "Channels": st.column_config.TextColumn(width="medium"),
            "Cost ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "Reg": st.column_config.NumberColumn(format="%d"),
            "1st Rech": st.column_config.NumberColumn(format="%d"),
            "CPFD ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "Amount (₱)": st.column_config.NumberColumn(format="₱ %.0f"),
            "ARPPU (₱)": st.column_config.NumberColumn(format="₱ %.2f"),
            "ROAS": st.column_config.NumberColumn(format="%.2f"),
        },
        key=f"{key_prefix}_lb",
    )

    st.caption(f"Team Channel Performance | {date_label}")


def main():
    st.set_page_config(page_title="Team Channel by Team", page_icon="👥", layout="wide")
    st.markdown("""
    <style>
        .section-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)
    st.title("👥 Team Channel Performance")
    render_content()


if not hasattr(st, '_is_recharge_import'):
    main()
