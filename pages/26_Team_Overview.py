"""
Team Overview Page - Individual channel results from P sheet (Team Channel)
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

TEAM_COLORS = {
    'JASON / SHILA': '#3b82f6',
    'RON / ADRIAN': '#22c55e',
    'MIKA / JOMAR': '#a855f7',
}


def format_currency(v):
    return f"${v:,.2f}" if v else "$0.00"


def format_php(v):
    return f"₱{v:,.0f}" if v else "₱0"


def render_content(key_prefix="to"):
    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI is disabled.")
        return

    with st.spinner("Loading Team Channel data..."):
        data = load_team_channel_data()
        overall_df = data.get('overall', pd.DataFrame())
        daily_df = data.get('daily', pd.DataFrame())

    if overall_df.empty and daily_df.empty:
        st.error("No Team Channel data available. Check that the sheet exists and has data.")
        return

    # Inline controls
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 1.5, 1.5, 1])
    with ctrl1:
        teams = sorted(overall_df['team'].unique()) if not overall_df.empty else []
        selected_team = st.selectbox("Team Filter", ["All Teams"] + list(teams), key=f"{key_prefix}_team")
    with ctrl4:
        if st.button("Refresh", type="primary", use_container_width=True, key=f"{key_prefix}_refresh"):
            refresh_team_channel_data()
            st.cache_data.clear()
            st.rerun()

    # Date filter
    has_daily = not daily_df.empty
    if has_daily:
        min_date = daily_df['date'].min().date()
        max_date = daily_df['date'].max().date()
        default_start = max(min_date, max_date - timedelta(days=30))
        with ctrl2:
            start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date, key=f"{key_prefix}_from")
        with ctrl3:
            end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, key=f"{key_prefix}_to")

        filtered_daily = daily_df[
            (daily_df['date'].dt.date >= start_date) &
            (daily_df['date'].dt.date <= end_date)
        ]
    else:
        start_date = datetime.now().date() - timedelta(days=30)
        end_date = datetime.now().date()
        filtered_daily = pd.DataFrame()

    # Apply team filter
    filtered_overall = overall_df.copy()
    if selected_team != "All Teams":
        filtered_overall = filtered_overall[filtered_overall['team'] == selected_team]
        if has_daily and not filtered_daily.empty:
            team_channels = overall_df[overall_df['team'] == selected_team]['channel'].unique()
            filtered_daily = filtered_daily[filtered_daily['channel'].isin(team_channels)]

    # HEADER
    n_channels = len(filtered_overall) if not filtered_overall.empty else 0
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
        <h2 style="margin: 0;">Individual Channel Performance</h2>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')} &bull; {n_channels} channels &bull; {selected_team}</p>
    </div>
    """, unsafe_allow_html=True)

    # TOTALS
    st.subheader("Totals")

    if not filtered_overall.empty:
        total_cost = filtered_overall['cost'].sum()
        total_reg = int(filtered_overall['registrations'].sum())
        total_fr = int(filtered_overall['first_recharge'].sum())
        total_amt = filtered_overall['total_amount'].sum()
        avg_cpr = total_cost / total_reg if total_reg > 0 else 0
        avg_cpfd = total_cost / total_fr if total_fr > 0 else 0
        avg_roas = total_amt / total_cost if total_cost > 0 else 0

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Total Cost", format_currency(total_cost))
        with col2:
            st.metric("Registrations", f"{total_reg:,}")
        with col3:
            st.metric("1st Recharge", f"{total_fr:,}")
        with col4:
            st.metric("Total Amount", format_php(total_amt))
        with col5:
            st.metric("CPR", format_currency(avg_cpr))
        with col6:
            st.metric("ROAS", f"{avg_roas:.2f}")

    st.divider()

    # INDIVIDUAL CHANNEL CARDS
    st.subheader("Individual Channel Results")

    if not filtered_overall.empty:
        channel_df = filtered_overall.sort_values('cost', ascending=False).reset_index(drop=True)

        cols = st.columns(3)
        for idx, (_, r) in enumerate(channel_df.iterrows()):
            team = r['team']
            channel = r['channel']
            color = TEAM_COLORS.get(team, '#64748b')
            short_name = channel.replace('FB-FB-FB-', '')

            cpr = r['cost'] / r['registrations'] if r['registrations'] > 0 else 0
            cpfd = r['cost'] / r['first_recharge'] if r['first_recharge'] > 0 else 0
            roas = r['total_amount'] / r['cost'] if r['cost'] > 0 else 0

            if roas >= 3:
                perf_badge, perf_color = '🏆 Top', '#28a745'
            elif roas >= 2:
                perf_badge, perf_color = '⭐ Good', '#ffc107'
            elif roas >= 1:
                perf_badge, perf_color = '📈 Active', '#17a2b8'
            else:
                perf_badge, perf_color = '⚠️ Low', '#dc3545'

            with cols[idx % 3]:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 1.2rem; border-radius: 12px; border-left: 5px solid {color}; margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: #333;">{short_name}</h4>
                        <span style="background: {perf_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.7rem;">{perf_badge}</span>
                    </div>
                    <p style="margin: 2px 0 0 0; font-size: 0.75rem; color: {color}; font-weight: bold;">{team}</p>
                    <hr style="margin: 8px 0; border-color: #dee2e6;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.82rem;">
                        <div><strong>Cost:</strong> ${r['cost']:,.2f}</div>
                        <div><strong>1st Rech:</strong> {int(r['first_recharge']):,}</div>
                        <div><strong>Reg:</strong> {int(r['registrations']):,}</div>
                        <div><strong>Amount:</strong> ₱{r['total_amount']:,.0f}</div>
                        <div><strong>CPR:</strong> ${cpr:.2f}</div>
                        <div><strong>CPFD:</strong> ${cpfd:.2f}</div>
                        <div><strong>ARPPU:</strong> ₱{r['arppu']:.0f}</div>
                        <div><strong>ROAS:</strong> {roas:.2f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()

    # COMPARISON CHARTS
    st.subheader("Channel Comparison")

    if not filtered_overall.empty:
        chart_df = filtered_overall.copy()
        chart_df['short_name'] = chart_df['channel'].str.replace('FB-FB-FB-', '', regex=False)
        chart_df['cpr'] = chart_df.apply(lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
        chart_df['cpfd'] = chart_df.apply(lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        chart_df['roas'] = chart_df.apply(lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

        inner_tab1, inner_tab2 = st.tabs(["Performance Metrics", "Daily Trends"])

        with inner_tab1:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(
                    chart_df.sort_values('cost', ascending=True),
                    x='cost', y='short_name', orientation='h',
                    color='team', color_discrete_map=TEAM_COLORS,
                    title='Cost by Channel ($)', text='cost'
                )
                fig.update_traces(texttemplate='$%{text:,.0f}', textposition='inside')
                fig.update_layout(height=450, yaxis_title="", xaxis_title="Cost (USD)",
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.3))
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_cost")
            with col2:
                fig = px.bar(
                    chart_df.sort_values('first_recharge', ascending=True),
                    x='first_recharge', y='short_name', orientation='h',
                    color='team', color_discrete_map=TEAM_COLORS,
                    title='1st Recharge by Channel', text='first_recharge'
                )
                fig.update_traces(texttemplate='%{text:,}', textposition='inside')
                fig.update_layout(height=450, yaxis_title="", xaxis_title="1st Recharge",
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.3))
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_fr")

            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(
                    chart_df.sort_values('roas', ascending=True),
                    x='roas', y='short_name', orientation='h',
                    color='team', color_discrete_map=TEAM_COLORS,
                    title='ROAS by Channel', text='roas'
                )
                fig.update_traces(texttemplate='%{text:.2f}', textposition='inside')
                fig.update_layout(height=450, yaxis_title="", xaxis_title="ROAS",
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.3))
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_roas")
            with col2:
                fig = px.bar(
                    chart_df.sort_values('cpfd', ascending=True),
                    x='cpfd', y='short_name', orientation='h',
                    color='team', color_discrete_map=TEAM_COLORS,
                    title='CPFD by Channel ($)', text='cpfd'
                )
                fig.update_traces(texttemplate='$%{text:.2f}', textposition='inside')
                fig.update_layout(height=450, yaxis_title="", xaxis_title="CPFD (USD)",
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.3))
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_cpfd")

        with inner_tab2:
            if has_daily and not filtered_daily.empty:
                daily_agg = filtered_daily.copy()
                daily_agg['short_name'] = daily_agg['channel'].str.replace('FB-FB-FB-', '', regex=False)
                daily_agg['date_only'] = daily_agg['date'].dt.date
                daily_agg['roas'] = daily_agg.apply(
                    lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
                daily_agg['cpfd'] = daily_agg.apply(
                    lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

                metric_choice = st.selectbox("Select Metric",
                    ['cost', 'registrations', 'first_recharge', 'total_amount', 'roas', 'cpfd'],
                    key=f"{key_prefix}_metric")
                metric_labels = {
                    'cost': 'Cost ($)', 'registrations': 'Registrations', 'first_recharge': '1st Recharge',
                    'total_amount': 'Amount (₱)', 'roas': 'ROAS', 'cpfd': 'CPFD ($)'}

                fig = px.line(
                    daily_agg, x='date_only', y=metric_choice, color='short_name',
                    title=f'{metric_labels.get(metric_choice, metric_choice)} Daily Trend',
                    markers=True,
                )
                fig.update_layout(height=450, legend=dict(orientation='h', yanchor='bottom', y=-0.4))
                st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart_trend")
            else:
                st.info("No daily data available for trend analysis.")

    # LEADERBOARD
    st.divider()
    st.subheader("Channel Leaderboard")

    if not filtered_overall.empty:
        lb = filtered_overall.copy()
        lb['short_name'] = lb['channel'].str.replace('FB-FB-FB-', '', regex=False)
        lb['cpr'] = lb.apply(lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
        lb['cpfd'] = lb.apply(lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
        lb['roas'] = lb.apply(lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
        lb = lb.sort_values('roas', ascending=False).reset_index(drop=True)
        lb['rank'] = range(1, len(lb) + 1)

        display_lb = lb[['rank', 'short_name', 'team', 'cost', 'registrations', 'first_recharge', 'total_amount', 'cpr', 'cpfd', 'roas']].copy()
        display_lb.columns = ['#', 'Channel', 'Team', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'CPR ($)', 'CPFD ($)', 'ROAS']

        st.dataframe(
            display_lb,
            use_container_width=True,
            hide_index=True,
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "Channel": st.column_config.TextColumn(width="medium"),
                "Team": st.column_config.TextColumn(width="medium"),
                "Cost ($)": st.column_config.NumberColumn(format="$ %.2f"),
                "Reg": st.column_config.NumberColumn(format="%d"),
                "1st Rech": st.column_config.NumberColumn(format="%d"),
                "Amount (₱)": st.column_config.NumberColumn(format="₱ %.0f"),
                "CPR ($)": st.column_config.NumberColumn(format="$ %.2f"),
                "CPFD ($)": st.column_config.NumberColumn(format="$ %.2f"),
                "ROAS": st.column_config.NumberColumn(format="%.2f"),
            },
            key=f"{key_prefix}_leaderboard",
        )

    if has_daily:
        st.caption(f"Team Overview | {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")
    else:
        st.caption("Team Overview | Overall Data")


def main():
    st.set_page_config(page_title="Team Overview", page_icon="👥", layout="wide")
    st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.jpg")
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, width=120)

    st.title("👥 Team Overview & Comparison")
    render_content()


if not hasattr(st, '_is_recharge_import'):
    main()
