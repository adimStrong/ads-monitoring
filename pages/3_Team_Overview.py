"""
Team Overview Page - Compare teams using Team Channel (P sheet) data
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
from config import CHANNEL_ROI_ENABLED

# Sidebar logo
logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.jpg")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)

st.title("👥 Team Overview & Comparison")

TEAM_COLORS = {
    'JASON / SHILA / ADRIAN': '#3b82f6',
    'RON / KRISSA': '#22c55e',
    'JOMAR / MIKA': '#a855f7',
    'DER': '#f59e0b',
}

TEAM_CHANNEL_MAP = {
    'JASON / SHILA / ADRIAN': 'Promo - 07 - 1, 2 - 13',
    'RON / KRISSA': 'Promo - 10 - 11',
    'JOMAR / MIKA': 'Promo - 6 - 8',
    'DER': 'Promo 9',
}


def format_currency(v):
    return f"${v:,.2f}" if v else "$0.00"


def format_php(v):
    return f"₱{v:,.0f}" if v else "₱0"


# ============================================================
# DATA LOADING
# ============================================================

if not CHANNEL_ROI_ENABLED:
    st.warning("Channel ROI is disabled.")
    st.stop()

with st.spinner("Loading Team Channel data..."):
    data = load_team_channel_data()
    overall_df = data.get('overall', pd.DataFrame())
    daily_df = data.get('daily', pd.DataFrame())

if overall_df.empty and daily_df.empty:
    st.error("No Team Channel data available. Check that the sheet exists and has data.")
    st.stop()

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("Controls")

if st.sidebar.button("🔄 Refresh Data", type="primary", use_container_width=True):
    refresh_team_channel_data()
    st.cache_data.clear()
    st.rerun()

# Date filter (for daily data)
has_daily = not daily_df.empty
if has_daily:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Date Range")
    min_date = daily_df['date'].min().date()
    max_date = daily_df['date'].max().date()
    default_start = max(min_date, max_date - timedelta(days=30))

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=default_start, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

    st.sidebar.caption(f"Data: {min_date.strftime('%b %d')} - {max_date.strftime('%b %d, %Y')}")

    # Filter daily data
    filtered_daily = daily_df[
        (daily_df['date'].dt.date >= start_date) &
        (daily_df['date'].dt.date <= end_date)
    ]
else:
    start_date = datetime.now().date() - timedelta(days=30)
    end_date = datetime.now().date()
    filtered_daily = pd.DataFrame()

# ============================================================
# HEADER
# ============================================================
teams = sorted(overall_df['team'].unique()) if not overall_df.empty else []
st.markdown(f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
    <h2 style="margin: 0;">Team Performance Overview</h2>
    <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')} &bull; {len(teams)} teams</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# TEAM TOTALS (from overall section)
# ============================================================
st.subheader("📊 Team Totals")

if not overall_df.empty:
    total_cost = overall_df['cost'].sum()
    total_reg = int(overall_df['registrations'].sum())
    total_fr = int(overall_df['first_recharge'].sum())
    total_amt = overall_df['total_amount'].sum()
    avg_cpr = total_cost / total_reg if total_reg > 0 else 0
    avg_cpfd = total_cost / total_fr if total_fr > 0 else 0
    avg_roas = total_amt / total_cost if total_cost > 0 else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("💵 Total Cost", format_currency(total_cost))
    with col2:
        st.metric("📝 Registrations", f"{total_reg:,}")
    with col3:
        st.metric("💰 1st Recharge", f"{total_fr:,}")
    with col4:
        st.metric("₱ Total Amount", format_php(total_amt))
    with col5:
        st.metric("📊 CPR", format_currency(avg_cpr))
    with col6:
        st.metric("📈 ROAS", f"{avg_roas:.2f}")
else:
    st.info("No overall data available.")

st.divider()

# ============================================================
# TEAM CARDS
# ============================================================
st.subheader("👤 Team Summary")

if not overall_df.empty:
    team_agg = overall_df.groupby('team').agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    team_agg['cpr'] = team_agg.apply(lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    team_agg['cpfd'] = team_agg.apply(lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    team_agg['arppu'] = team_agg.apply(lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    team_agg['roas'] = team_agg.apply(lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    # Sort by ROAS descending
    team_agg = team_agg.sort_values('roas', ascending=False).reset_index(drop=True)

    cols = st.columns(2)
    for idx, (_, r) in enumerate(team_agg.iterrows()):
        team = r['team']
        color = TEAM_COLORS.get(team, '#64748b')
        channels = TEAM_CHANNEL_MAP.get(team, '-')

        # Performance badge
        if r['roas'] >= 3:
            perf_badge = '🏆 Top'
            perf_color = '#28a745'
        elif r['roas'] >= 2:
            perf_badge = '⭐ Good'
            perf_color = '#ffc107'
        else:
            perf_badge = '📈 Active'
            perf_color = '#17a2b8'

        with cols[idx % 2]:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 1.5rem; border-radius: 12px; border-left: 5px solid {color}; margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: #333;">{team}</h3>
                    <span style="background: {perf_color}; color: white; padding: 4px 10px; border-radius: 15px; font-size: 0.75rem;">{perf_badge}</span>
                </div>
                <p style="margin: 4px 0 0 0; font-size: 0.8rem; color: #666;">Channels: {channels}</p>
                <hr style="margin: 10px 0; border-color: #dee2e6;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
                    <div><strong>Cost:</strong> ${r['cost']:,.2f}</div>
                    <div><strong>1st Recharge:</strong> {int(r['first_recharge']):,}</div>
                    <div><strong>Registrations:</strong> {int(r['registrations']):,}</div>
                    <div><strong>Amount:</strong> ₱{r['total_amount']:,.0f}</div>
                    <div><strong>CPR:</strong> ${r['cpr']:.2f}</div>
                    <div><strong>CPFD:</strong> ${r['cpfd']:.2f}</div>
                    <div><strong>ARPPU:</strong> ₱{r['arppu']:.0f}</div>
                    <div><strong>ROAS:</strong> {r['roas']:.2f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

st.divider()

# ============================================================
# COMPARISON CHARTS
# ============================================================
st.subheader("📈 Performance Comparison")

if not overall_df.empty:
    tab1, tab2 = st.tabs(["Performance Metrics", "Daily Trends"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure(go.Bar(
                x=team_agg['team'], y=team_agg['cost'],
                marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
                text=[f"${v:,.0f}" for v in team_agg['cost']], textposition='outside',
            ))
            fig.add_hline(y=team_agg['cost'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(title='Total Cost ($)', height=380, yaxis_title="USD", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = go.Figure(go.Bar(
                x=team_agg['team'], y=team_agg['first_recharge'],
                marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
                text=[f"{int(v):,}" for v in team_agg['first_recharge']], textposition='outside',
            ))
            fig.add_hline(y=team_agg['first_recharge'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(title='1st Recharge Count', height=380, yaxis_title="Count", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure(go.Bar(
                x=team_agg['team'], y=team_agg['roas'],
                marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
                text=[f"{v:.2f}" for v in team_agg['roas']], textposition='outside',
            ))
            fig.add_hline(y=team_agg['roas'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(title='ROAS', height=380, yaxis_title="Ratio", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = go.Figure(go.Bar(
                x=team_agg['team'], y=team_agg['cpfd'],
                marker_color=[TEAM_COLORS.get(t, '#64748b') for t in team_agg['team']],
                text=[f"${v:.2f}" for v in team_agg['cpfd']], textposition='outside',
            ))
            fig.add_hline(y=team_agg['cpfd'].mean(), line_dash="dash", annotation_text="Avg")
            fig.update_layout(title='CPFD ($)', height=380, yaxis_title="USD", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Radar chart
        st.subheader("🎯 Team Performance Radar")

        metrics = ['cost', 'registrations', 'first_recharge', 'total_amount', 'roas']
        metric_labels = {'cost': 'Cost', 'registrations': 'Registrations', 'first_recharge': '1st Recharge',
                         'total_amount': 'Amount', 'roas': 'ROAS'}

        radar_df = team_agg.copy()
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
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if has_daily and not filtered_daily.empty:
            # Aggregate daily by team (map channels to teams using overall_df)
            # Build channel->team mapping from overall data
            channel_team = overall_df[['team', 'channel']].drop_duplicates()
            daily_with_team = filtered_daily.merge(channel_team, on='channel', how='left', suffixes=('', '_mapped'))
            # Use mapped team, fallback to original
            if 'team_mapped' in daily_with_team.columns:
                daily_with_team['team_final'] = daily_with_team['team_mapped'].fillna(daily_with_team['team'])
            else:
                daily_with_team['team_final'] = daily_with_team['team']

            daily_by_team = daily_with_team.groupby(['date', 'team_final']).agg({
                'cost': 'sum',
                'registrations': 'sum',
                'first_recharge': 'sum',
                'total_amount': 'sum',
            }).reset_index()
            daily_by_team.rename(columns={'team_final': 'team'}, inplace=True)
            daily_by_team['date_only'] = daily_by_team['date'].dt.date
            daily_by_team['roas'] = daily_by_team.apply(
                lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
            daily_by_team['cpfd'] = daily_by_team.apply(
                lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

            metric_choice = st.selectbox("Select Metric",
                ['cost', 'registrations', 'first_recharge', 'total_amount', 'roas', 'cpfd'])
            metric_labels_full = {
                'cost': 'Cost ($)', 'registrations': 'Registrations', 'first_recharge': '1st Recharge',
                'total_amount': 'Amount (₱)', 'roas': 'ROAS', 'cpfd': 'CPFD ($)'}

            fig = px.line(
                daily_by_team, x='date_only', y=metric_choice, color='team',
                title=f'{metric_labels_full.get(metric_choice, metric_choice)} Trend by Team',
                markers=True,
                color_discrete_map=TEAM_COLORS,
            )
            fig.update_layout(height=400, legend=dict(orientation='h', yanchor='bottom', y=1.02))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No daily data available for trend analysis.")

# ============================================================
# LEADERBOARD
# ============================================================
st.divider()
st.subheader("🏆 Team Leaderboard")

if not overall_df.empty:
    lb = team_agg.copy()
    lb = lb.sort_values('roas', ascending=False).reset_index(drop=True)
    lb['rank'] = range(1, len(lb) + 1)

    display_lb = lb[['rank', 'team', 'cost', 'registrations', 'first_recharge', 'total_amount', 'cpr', 'cpfd', 'roas']].copy()
    display_lb.columns = ['#', 'Team', 'Cost ($)', 'Reg', '1st Rech', 'Amount (₱)', 'CPR ($)', 'CPFD ($)', 'ROAS']

    st.dataframe(
        display_lb,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Team": st.column_config.TextColumn(width="medium"),
            "Cost ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "Reg": st.column_config.NumberColumn(format="%d"),
            "1st Rech": st.column_config.NumberColumn(format="%d"),
            "Amount (₱)": st.column_config.NumberColumn(format="₱ %.0f"),
            "CPR ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "CPFD ($)": st.column_config.NumberColumn(format="$ %.2f"),
            "ROAS": st.column_config.NumberColumn(format="%.2f"),
        }
    )

if has_daily:
    st.caption(f"Team Overview | {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")
else:
    st.caption("Team Overview | Overall Data")
