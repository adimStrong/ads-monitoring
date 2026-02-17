"""
Team Channel Performance Dashboard
Shows per-channel source performance across multiple teams
with daily, weekly, and monthly trends.
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

st.set_page_config(page_title="Team Channel Performance", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Apply shared sidebar hide CSS
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)


def format_currency(value):
    if pd.isna(value) or value == 0:
        return "$0.00"
    return f"${value:,.2f}"


def format_php(value):
    if pd.isna(value) or value == 0:
        return "₱0.00"
    return f"₱{value:,.2f}"


def format_number(value):
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"


def format_ratio(value):
    if pd.isna(value) or value == 0:
        return "0.00"
    return f"{value:.2f}"


def get_tue_mon_week(date):
    """Get Tuesday-Monday week number and year for a given date."""
    adjusted_date = date - timedelta(days=(date.weekday() - 1) % 7)
    week_num = adjusted_date.isocalendar()[1]
    year = adjusted_date.isocalendar()[0]
    return year, week_num


def make_pie_chart(labels, values, title, value_format="count"):
    """Create a formatted pie chart."""
    if value_format == "usd":
        template = "%{label}<br>%{percent}<br>$%{value:,.2f}"
    elif value_format == "php":
        template = "%{label}<br>%{percent}<br>₱%{value:,.0f}"
    else:
        template = "%{label}<br>%{percent}<br>%{value:,.0f}"

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.3,
        pull=[0.05] * len(labels),
        textposition='inside', texttemplate=template,
    )])
    fig.update_layout(title=dict(text=title, x=0.5, xanchor='center'),
                      height=400, showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.2))
    return fig


def render_overall_summary(overall_df):
    """Render overall summary using the OVERALL section from the sheet."""
    st.markdown('<div class="section-header"><h3>📈 OVERALL SUMMARY</h3></div>', unsafe_allow_html=True)

    if overall_df.empty:
        st.info("No overall data available")
        return

    total_cost = overall_df['cost'].sum()
    total_reg = overall_df['registrations'].sum()
    total_recharge = overall_df['first_recharge'].sum()
    total_amount = overall_df['total_amount'].sum()
    avg_arppu = total_amount / total_recharge if total_recharge > 0 else 0
    avg_cpr = total_cost / total_reg if total_reg > 0 else 0
    avg_cpfd = total_cost / total_recharge if total_recharge > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cost", format_currency(total_cost))
    with col2:
        st.metric("Registrations", format_number(total_reg))
    with col3:
        st.metric("1st Recharge", format_number(total_recharge))
    with col4:
        st.metric("Total Amount", format_php(total_amount))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg ARPPU", format_php(avg_arppu))
    with col2:
        st.metric("CPR (Cost/Reg)", format_currency(avg_cpr))
    with col3:
        st.metric("CPFD (Cost/1st Recharge)", format_currency(avg_cpfd))


def render_team_comparison(overall_df):
    """Render team comparison using overall per-team data."""
    st.markdown('<div class="section-header"><h3>👥 TEAM COMPARISON</h3></div>', unsafe_allow_html=True)

    if overall_df.empty:
        st.info("No team data available")
        return

    team_agg = overall_df.groupby('team').agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    team_agg['cpr'] = team_agg.apply(
        lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    team_agg['cpfd'] = team_agg.apply(
        lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    # Bar chart for key metrics
    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(team_agg.sort_values('cost', ascending=True),
                     x='cost', y='team', orientation='h',
                     title='Total Cost by Team ($)', text='cost')
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='inside')
        fig.update_layout(height=350, xaxis_title="Cost (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(team_agg.sort_values('first_recharge', ascending=True),
                     x='first_recharge', y='team', orientation='h',
                     title='1st Recharge by Team', text='first_recharge')
        fig.update_traces(texttemplate='%{text:,}', textposition='inside')
        fig.update_layout(height=350, xaxis_title="First Recharge", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(team_agg.sort_values('cpr', ascending=True),
                     x='cpr', y='team', orientation='h',
                     title='CPR by Team ($)', text='cpr')
        fig.update_traces(texttemplate='$%{text:,.2f}', textposition='inside')
        fig.update_layout(height=350, xaxis_title="Cost per Registration (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(team_agg.sort_values('cpfd', ascending=True),
                     x='cpfd', y='team', orientation='h',
                     title='CPFD by Team ($)', text='cpfd')
        fig.update_traces(texttemplate='$%{text:,.2f}', textposition='inside')
        fig.update_layout(height=350, xaxis_title="Cost per 1st Recharge (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(team_agg['team'], team_agg['total_amount'],
                             'Total Recharge Amount by Team', 'php')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = make_pie_chart(team_agg['team'], team_agg['registrations'],
                             'Registrations by Team', 'count')
        st.plotly_chart(fig, use_container_width=True)


def render_channel_breakdown(overall_df):
    """Render per-channel source horizontal bar charts using overall data."""
    st.markdown('<div class="section-header"><h3>📡 PER CHANNEL SOURCE BREAKDOWN</h3></div>', unsafe_allow_html=True)

    if overall_df.empty:
        st.info("No channel data available")
        return

    channel_agg = overall_df.groupby('channel').agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'arppu': 'mean',
    }).reset_index()

    channel_agg['cpr'] = channel_agg.apply(
        lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    channel_agg['cpfd'] = channel_agg.apply(
        lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        sorted_df = channel_agg.sort_values('cost', ascending=True)
        fig = px.bar(sorted_df, x='cost', y='channel', orientation='h',
                     title='Cost by Channel ($)', text='cost')
        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="Cost (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        sorted_df = channel_agg.sort_values('first_recharge', ascending=True)
        fig = px.bar(sorted_df, x='first_recharge', y='channel', orientation='h',
                     title='1st Recharge by Channel', text='first_recharge')
        fig.update_traces(texttemplate='%{text:,}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="First Recharge Count", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        sorted_df = channel_agg.sort_values('cpr', ascending=True)
        fig = px.bar(sorted_df, x='cpr', y='channel', orientation='h',
                     title='CPR by Channel ($)', text='cpr')
        fig.update_traces(texttemplate='$%{text:,.2f}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="Cost per Registration (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        sorted_df = channel_agg.sort_values('cpfd', ascending=True)
        fig = px.bar(sorted_df, x='cpfd', y='channel', orientation='h',
                     title='CPFD by Channel ($)', text='cpfd')
        fig.update_traces(texttemplate='$%{text:,.2f}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="Cost per 1st Recharge (USD)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        sorted_df = channel_agg.sort_values('total_amount', ascending=True)
        fig = px.bar(sorted_df, x='total_amount', y='channel', orientation='h',
                     title='Total Recharge Amount by Channel (₱)', text='total_amount')
        fig.update_traces(texttemplate='₱%{text:,.0f}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="Amount (PHP)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        sorted_df = channel_agg.sort_values('arppu', ascending=True)
        fig = px.bar(sorted_df, x='arppu', y='channel', orientation='h',
                     title='Avg ARPPU by Channel (₱)', text='arppu')
        fig.update_traces(texttemplate='₱%{text:,.0f}', textposition='inside')
        fig.update_layout(height=450, xaxis_title="ARPPU (PHP)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


def render_daily_trends(daily_df):
    """Render daily trend line charts grouped by channel."""
    st.markdown('<div class="section-header"><h3>📅 DAILY TRENDS</h3></div>', unsafe_allow_html=True)

    if daily_df.empty:
        st.info("No daily data available")
        return

    df = daily_df.copy()
    df['date_only'] = df['date'].dt.date

    daily = df.groupby(['date_only', 'channel']).agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    daily['roas'] = daily.apply(
        lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
    daily['cpr'] = daily.apply(
        lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    daily['cpfd'] = daily.apply(
        lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(daily, x='date_only', y='cost', color='channel',
                      markers=True, title='Daily Cost ($)')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Cost (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(daily, x='date_only', y='registrations', color='channel',
                      markers=True, title='Daily Registrations')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Registrations",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(daily, x='date_only', y='first_recharge', color='channel',
                      markers=True, title='Daily 1st Recharge Count')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="1st Recharge",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(daily, x='date_only', y='roas', color='channel',
                      markers=True, title='Daily ROAS')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="ROAS",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(daily, x='date_only', y='cpr', color='channel',
                      markers=True, title='Daily CPR ($)')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Cost per Registration (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(daily, x='date_only', y='cpfd', color='channel',
                      markers=True, title='Daily CPFD ($)')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Cost per 1st Recharge (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)


def render_weekly_summary(daily_df):
    """Render weekly summary grouped bar charts (Tue-Mon weeks)."""
    st.markdown('<div class="section-header"><h3>📆 WEEKLY SUMMARY (Tue-Mon)</h3></div>', unsafe_allow_html=True)

    if daily_df.empty:
        st.info("No weekly data available")
        return

    df = daily_df.copy()
    df['week_info'] = df['date'].apply(get_tue_mon_week)
    df['year'] = df['week_info'].apply(lambda x: x[0])
    df['week'] = df['week_info'].apply(lambda x: x[1])
    df['week_key'] = df.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)

    # Build week labels with date ranges
    weeks_info = df.groupby('week_key').agg({'date': ['min', 'max']}).reset_index()
    weeks_info.columns = ['week_key', 'date_start', 'date_end']
    weeks_info['week_label'] = weeks_info.apply(
        lambda x: f"{x['date_start'].strftime('%b %d')} - {x['date_end'].strftime('%b %d')}", axis=1)
    week_label_map = dict(zip(weeks_info['week_key'], weeks_info['week_label']))
    df['week_label'] = df['week_key'].map(week_label_map)

    weekly = df.groupby(['week_label', 'channel']).agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    weekly['roas'] = weekly.apply(
        lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
    weekly['cpr'] = weekly.apply(
        lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    weekly['cpfd'] = weekly.apply(
        lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(weekly, x='week_label', y='cost', color='channel',
                     barmode='group', title='Weekly Cost ($)')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="Cost (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(weekly, x='week_label', y='registrations', color='channel',
                     barmode='group', title='Weekly Registrations')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="Registrations",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(weekly, x='week_label', y='first_recharge', color='channel',
                     barmode='group', title='Weekly 1st Recharge')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="1st Recharge",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(weekly, x='week_label', y='roas', color='channel',
                     barmode='group', title='Weekly ROAS')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="ROAS",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(weekly, x='week_label', y='cpr', color='channel',
                     barmode='group', title='Weekly CPR ($)')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="Cost per Registration (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(weekly, x='week_label', y='cpfd', color='channel',
                     barmode='group', title='Weekly CPFD ($)')
        fig.update_layout(height=400, xaxis_title="Week", yaxis_title="Cost per 1st Recharge (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)


def render_monthly_summary(daily_df):
    """Render monthly summary grouped bar charts."""
    st.markdown('<div class="section-header"><h3>📊 MONTHLY SUMMARY</h3></div>', unsafe_allow_html=True)

    if daily_df.empty:
        st.info("No monthly data available")
        return

    df = daily_df.copy()
    df['month'] = df['date'].dt.to_period('M').astype(str)

    monthly = df.groupby(['month', 'channel']).agg({
        'cost': 'sum',
        'registrations': 'sum',
        'first_recharge': 'sum',
        'total_amount': 'sum',
    }).reset_index()

    monthly['roas'] = monthly.apply(
        lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)
    monthly['cpr'] = monthly.apply(
        lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
    monthly['cpfd'] = monthly.apply(
        lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(monthly, x='month', y='cost', color='channel',
                     barmode='group', title='Monthly Cost ($)')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="Cost (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(monthly, x='month', y='registrations', color='channel',
                     barmode='group', title='Monthly Registrations')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="Registrations",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(monthly, x='month', y='first_recharge', color='channel',
                     barmode='group', title='Monthly 1st Recharge')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="1st Recharge",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(monthly, x='month', y='roas', color='channel',
                     barmode='group', title='Monthly ROAS')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="ROAS",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(monthly, x='month', y='cpr', color='channel',
                     barmode='group', title='Monthly CPR ($)')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="Cost per Registration (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(monthly, x='month', y='cpfd', color='channel',
                     barmode='group', title='Monthly CPFD ($)')
        fig.update_layout(height=400, xaxis_title="Month", yaxis_title="Cost per 1st Recharge (USD)",
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)


def render_data_table(daily_df):
    """Render detailed data table with CSV download."""
    st.markdown('<div class="section-header"><h3>📋 DETAILED DATA TABLE</h3></div>', unsafe_allow_html=True)

    if daily_df.empty:
        st.info("No data available")
        return

    display_df = daily_df.copy()
    display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
    display_df = display_df.sort_values('date', ascending=False)

    display_cols = ['date', 'channel', 'cost', 'registrations',
                    'first_recharge', 'total_amount', 'arppu', 'cpr', 'cpfd', 'roas']
    display_df = display_df[[c for c in display_cols if c in display_df.columns]].copy()

    # Format for display
    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:,.2f}")
    display_df['registrations'] = display_df['registrations'].apply(lambda x: f"{x:,}")
    display_df['first_recharge'] = display_df['first_recharge'].apply(lambda x: f"{x:,}")
    display_df['total_amount'] = display_df['total_amount'].apply(lambda x: f"₱{x:,.2f}")
    display_df['arppu'] = display_df['arppu'].apply(lambda x: f"₱{x:,.2f}")
    if 'cpr' in display_df.columns:
        display_df['cpr'] = display_df['cpr'].apply(lambda x: f"${x:,.2f}")
    if 'cpfd' in display_df.columns:
        display_df['cpfd'] = display_df['cpfd'].apply(lambda x: f"${x:,.2f}")
    if 'roas' in display_df.columns:
        display_df['roas'] = display_df['roas'].apply(lambda x: f"{x:.2f}")

    display_df.columns = ['Date', 'Channel', 'Cost ($)', 'Registrations',
                           '1st Recharge', 'Total Amount (₱)', 'ARPPU (₱)',
                           'CPR ($)', 'CPFD ($)', 'ROAS']

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False)
    st.download_button(
        "📥 Download CSV",
        csv,
        f"team_channel_{datetime.now():%Y%m%d}.csv",
        "text/csv"
    )


def main():
    st.title("📊 Team Channel Performance")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    # Load data
    with st.spinner("Loading Team Channel data..."):
        data = load_team_channel_data()
        overall_df = data.get('overall', pd.DataFrame())
        daily_df = data.get('daily', pd.DataFrame())

    has_overall = not overall_df.empty
    has_daily = not daily_df.empty

    if not has_overall and not has_daily:
        st.error("No Team Channel data available.")
        st.info("Check that the 'Team Channel' sheet exists and has data.")
        return

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_team_channel_data()
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")

        # Channel filter (applies to daily trends)
        if has_daily:
            st.subheader("📡 Channel Filter")
            channels = sorted(daily_df['channel'].unique())
            selected_channels = st.multiselect("Channels", channels, default=channels)

            # Date range
            st.markdown("---")
            st.subheader("📅 Date Range")
            data_min_date = daily_df['date'].min().date()
            data_max_date = daily_df['date'].max().date()

            default_start = max(data_min_date, data_max_date - timedelta(days=30))

            # Session state for All Dates button
            if 'tc_start' not in st.session_state:
                st.session_state.tc_start = default_start
            if 'tc_end' not in st.session_state:
                st.session_state.tc_end = data_max_date

            if st.button("📅 All Dates", use_container_width=True):
                st.session_state.tc_start = data_min_date
                st.session_state.tc_end = data_max_date
                st.rerun()

            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input("From", value=st.session_state.tc_start,
                                          min_value=data_min_date, max_value=data_max_date,
                                          key='tc_from')
            with col2:
                date_to = st.date_input("To", value=st.session_state.tc_end,
                                        min_value=data_min_date, max_value=data_max_date,
                                        key='tc_to')

            st.session_state.tc_start = date_from
            st.session_state.tc_end = date_to

            st.caption(f"Data: {data_min_date.strftime('%b %d')} – {data_max_date.strftime('%b %d, %Y')}")

        # Team filter for overall section
        if has_overall:
            st.markdown("---")
            st.subheader("👥 Team Filter (Overall)")
            teams = sorted(overall_df['team'].unique())
            selected_team = st.selectbox("Team", ["All Teams"] + list(teams))

        st.markdown("---")
        st.subheader("Other Reports")
        st.markdown("📈 [Daily ROI](/Daily_ROI)")
        st.markdown("📈 [Counterpart](/Counterpart_Performance)")

    # Apply filters
    filtered_daily = daily_df.copy()
    if has_daily:
        if selected_channels:
            filtered_daily = filtered_daily[filtered_daily['channel'].isin(selected_channels)]
        filtered_daily = filtered_daily[
            (filtered_daily['date'].dt.date >= date_from) &
            (filtered_daily['date'].dt.date <= date_to)
        ]

    # Use sheet's overall data directly (authoritative source)
    filtered_overall = overall_df.copy()

    if has_overall and selected_team != "All Teams":
        filtered_overall = filtered_overall[filtered_overall['team'] == selected_team]

    # Render sections
    render_overall_summary(filtered_overall)

    if has_overall:
        st.divider()
        render_team_comparison(filtered_overall)

        st.divider()
        render_channel_breakdown(filtered_overall)

    if has_daily and not filtered_daily.empty:
        st.divider()
        render_daily_trends(filtered_daily)

        st.divider()
        render_weekly_summary(filtered_daily)

        st.divider()
        render_monthly_summary(filtered_daily)

        st.divider()
        render_data_table(filtered_daily)
    elif has_daily:
        st.divider()
        st.warning("No daily data available for the selected filters.")

    if has_daily:
        st.caption(f"Team Channel Performance | {date_from} to {date_to}")
    else:
        st.caption("Team Channel Performance | Overall Data")


if __name__ == "__main__":
    main()
