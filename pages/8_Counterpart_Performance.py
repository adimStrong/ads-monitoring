"""
Counterpart Performance Dashboard
Compares Facebook vs Google channel performance with daily, weekly, and monthly trends
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_counterpart_data, refresh_counterpart_data
from config import CHANNEL_ROI_ENABLED

st.set_page_config(page_title="Counterpart Performance", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .fb-card {
        background: linear-gradient(135deg, #1877f2 0%, #42a5f5 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .google-card {
        background: linear-gradient(135deg, #ea4335 0%, #ff6b6b 100%);
        padding: 20px; border-radius: 15px; color: white; text-align: center;
    }
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


def format_currency(value):
    """Format value as currency."""
    if pd.isna(value) or value == 0:
        return "$0.00"
    return f"${value:,.2f}"


def format_number(value):
    """Format value as integer with comma separators."""
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"


def format_ratio(value):
    """Format value as ratio with 2 decimals."""
    if pd.isna(value) or value == 0:
        return "0.00"
    return f"{value:.2f}"


def make_pie_chart(labels, values, title, value_format="count"):
    """Create a formatted pie chart with proper value display.

    Args:
        labels: Series/list of labels
        values: Series/list of values
        title: Chart title
        value_format: "count" for plain numbers, "usd" for $, "php" for PHP
    """
    if value_format == "usd":
        template = "%{label}<br>%{percent}<br>$%{value:,.2f}"
    elif value_format == "php":
        template = "%{label}<br>%{percent}<br>₱%{value:,.0f}"
    else:
        template = "%{label}<br>%{percent}<br>%{value:,.0f}"

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,
        pull=[0.05] * len(labels),
        textposition='auto',
        texttemplate=template,
    )])
    fig.update_layout(title=title, height=400, showlegend=False)
    return fig


def aggregate_daily_counterpart(df):
    """Aggregate counterpart data by date."""
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['date_only'] = df['date'].dt.date

    agg_df = df.groupby('date_only').agg({
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    # Calculate derived metrics
    agg_df['cost_per_recharge'] = agg_df.apply(
        lambda x: x['spending'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)
    agg_df['arppu'] = agg_df.apply(
        lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    return agg_df.sort_values('date_only')


def aggregate_weekly_counterpart(df):
    """Aggregate counterpart data by week with date range labels."""
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['week'] = df['date'].dt.isocalendar().week
    df['year'] = df['date'].dt.isocalendar().year
    df['week_key'] = df.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)

    # Aggregate with min/max dates for each week
    agg_df = df.groupby('week_key').agg({
        'date': ['min', 'max'],
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    # Flatten column names
    agg_df.columns = ['week_key', 'date_start', 'date_end', 'first_recharge', 'total_amount', 'spending']

    # Create readable date range label (e.g., "Jan 27 - Feb 2")
    agg_df['week_label'] = agg_df.apply(
        lambda x: f"{x['date_start'].strftime('%b %d')} - {x['date_end'].strftime('%b %d')}", axis=1)

    agg_df['cost_per_recharge'] = agg_df.apply(
        lambda x: x['spending'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)
    agg_df['arppu'] = agg_df.apply(
        lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    return agg_df.sort_values('week_key')


def aggregate_monthly_counterpart(df):
    """Aggregate counterpart data by month."""
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M').astype(str)

    agg_df = df.groupby('month').agg({
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    agg_df['cost_per_recharge'] = agg_df.apply(
        lambda x: x['spending'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)
    agg_df['arppu'] = agg_df.apply(
        lambda x: x['total_amount'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)

    return agg_df.sort_values('month')


def render_overall_summary(overall_df, channel_name):
    """Render overall summary with pie charts using OVERALL PERFORMANCE data from sheet."""
    st.markdown(f'<div class="section-header"><h3>📊 OVERALL PERFORMANCE - {channel_name.upper()}</h3></div>', unsafe_allow_html=True)

    if overall_df.empty:
        st.info(f"No {channel_name} overall data available")
        return

    # Use the OVERALL PERFORMANCE data directly from sheet
    channel_agg = overall_df.copy()

    # Calculate ROAS if not already present
    if 'roas' not in channel_agg.columns or channel_agg['roas'].isna().all():
        channel_agg['roas'] = channel_agg.apply(
            lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)

    # Display totals
    totals = {
        'first_recharge': channel_agg['first_recharge'].sum(),
        'total_amount': channel_agg['total_amount'].sum(),
        'spending': channel_agg['spending'].sum(),
    }
    totals['arppu'] = totals['total_amount'] / totals['first_recharge'] if totals['first_recharge'] > 0 else 0
    totals['cost_per_recharge'] = totals['spending'] / totals['first_recharge'] if totals['first_recharge'] > 0 else 0
    totals['roas'] = totals['total_amount'] / totals['spending'] if totals['spending'] > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total First Recharge", format_number(totals['first_recharge']))
        st.metric("Total Recharge Amount", format_currency(totals['total_amount']))
    with col2:
        st.metric("Avg ARPPU", format_currency(totals['arppu']))
        st.metric("Total Spending", format_currency(totals['spending']))
    with col3:
        st.metric("Avg Cost/Recharge", format_currency(totals['cost_per_recharge']))
        st.metric("Overall ROAS", format_ratio(totals['roas']))

    # Pie charts for distribution
    st.markdown("#### Channel Source Distribution")
    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(channel_agg['channel'], channel_agg['first_recharge'],
                            'First Recharge by Channel Source', 'count')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = make_pie_chart(channel_agg['channel'], channel_agg['total_amount'],
                            'Total Recharge Amount by Channel Source', 'php')
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(channel_agg['channel'], channel_agg['spending'],
                            'Spending by Channel Source', 'usd')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Bar chart for ROAS comparison
        fig = px.bar(channel_agg.sort_values('roas', ascending=True),
                    x='roas', y='channel', orientation='h',
                    title='ROAS by Channel Source')
        fig.update_layout(height=400, xaxis_title="ROAS", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


def render_daily_trends(df, channel_name):
    """Render daily trend charts comparing channel sources."""
    st.markdown('<div class="section-header"><h3>📈 DAILY TRENDS BY CHANNEL SOURCE</h3></div>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No daily data available for charts")
        return

    # Filter out summary rows
    df_filtered = df[~df['channel'].str.contains('平均|总计|Average|Total', case=False, na=False)].copy()

    if df_filtered.empty:
        st.warning("No daily data available for charts")
        return

    df_filtered['date'] = pd.to_datetime(df_filtered['date'])
    df_filtered['date_only'] = df_filtered['date'].dt.date

    # Aggregate by date and channel source
    daily_by_channel = df_filtered.groupby(['date_only', 'channel']).agg({
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    daily_by_channel['roas'] = daily_by_channel.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)

    # Row 1: First Recharge and Total Recharge Amount
    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(daily_by_channel, x='date_only', y='first_recharge', color='channel',
                     markers=True, title='First Recharge by Channel Source')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="First Recharge",
                         legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(daily_by_channel, x='date_only', y='total_amount', color='channel',
                     markers=True, title='Total Recharge Amount by Channel Source')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Amount (USD)",
                         legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    # Row 2: Spending and ROAS
    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(daily_by_channel, x='date_only', y='spending', color='channel',
                     markers=True, title='Spending by Channel Source')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Spending (USD)",
                         legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.line(daily_by_channel, x='date_only', y='roas', color='channel',
                     markers=True, title='ROAS by Channel Source')
        fig.update_layout(height=350, xaxis_title="Date", yaxis_title="ROAS",
                         legend=dict(orientation="h", yanchor="bottom", y=-0.4))
        st.plotly_chart(fig, use_container_width=True)


def get_tue_mon_week(date):
    """Get Tuesday-Monday week number and year for a given date.
    Week starts on Tuesday (weekday=1) and ends on Monday (weekday=0)."""
    # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    # Shift date so Tuesday becomes day 0 of the week
    adjusted_date = date - timedelta(days=(date.weekday() - 1) % 7)
    week_num = adjusted_date.isocalendar()[1]
    year = adjusted_date.isocalendar()[0]
    return year, week_num


def render_weekly_summary(df, channel_name):
    """Render weekly summary with pie charts comparing channel sources (Tue-Mon weeks)."""
    st.markdown('<div class="section-header"><h3>📆 WEEKLY SUMMARY BY CHANNEL SOURCE (Tue-Mon)</h3></div>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No weekly data available for charts")
        return

    # Filter out summary rows
    df_filtered = df[~df['channel'].str.contains('平均|总计|Average|Total', case=False, na=False)].copy()

    if df_filtered.empty:
        st.warning("No weekly data available for charts")
        return

    df_filtered['date'] = pd.to_datetime(df_filtered['date'])

    # Calculate Tue-Mon week
    df_filtered['week_info'] = df_filtered['date'].apply(get_tue_mon_week)
    df_filtered['year'] = df_filtered['week_info'].apply(lambda x: x[0])
    df_filtered['week'] = df_filtered['week_info'].apply(lambda x: x[1])
    df_filtered['week_key'] = df_filtered.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)

    # Get unique weeks with date ranges
    weeks_info = df_filtered.groupby('week_key').agg({
        'date': ['min', 'max']
    }).reset_index()
    weeks_info.columns = ['week_key', 'date_start', 'date_end']
    weeks_info['week_label'] = weeks_info.apply(
        lambda x: f"{x['date_start'].strftime('%b %d')} - {x['date_end'].strftime('%b %d')}", axis=1)
    weeks_info = weeks_info.sort_values('week_key')

    # Check if latest week is complete (should have 7 days: Wed to Tue)
    weeks_info['days_count'] = weeks_info.apply(
        lambda x: (x['date_end'] - x['date_start']).days + 1, axis=1)
    weeks_info['is_complete'] = weeks_info['days_count'] >= 7

    # Let user select a week
    week_options = weeks_info['week_label'].tolist()
    selected_week_label = st.selectbox("Select Week", week_options, index=len(week_options)-1 if week_options else 0)

    # Get the week info for selected week
    selected_week_row = weeks_info[weeks_info['week_label'] == selected_week_label].iloc[0]
    selected_week_key = selected_week_row['week_key']
    is_complete = selected_week_row['is_complete']
    days_count = selected_week_row['days_count']

    # Show warning if week is not complete
    if not is_complete:
        st.warning(f"⚠️ This week is not yet complete ({int(days_count)}/7 days)")

    # Filter data for selected week
    week_data = df_filtered[df_filtered['week_key'] == selected_week_key]

    # Aggregate by channel source for selected week
    weekly_agg = week_data.groupby('channel').agg({
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    weekly_agg['roas'] = weekly_agg.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)

    st.markdown(f"#### Week: {selected_week_label}")

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(weekly_agg['channel'], weekly_agg['first_recharge'],
                            'First Recharge Distribution', 'count')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = make_pie_chart(weekly_agg['channel'], weekly_agg['total_amount'],
                            'Total Recharge Amount Distribution', 'php')
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(weekly_agg['channel'], weekly_agg['spending'],
                            'Spending Distribution', 'usd')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(weekly_agg.sort_values('roas', ascending=True),
                    x='roas', y='channel', orientation='h',
                    title='ROAS Comparison')
        fig.update_layout(height=400, xaxis_title="ROAS", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


def render_monthly_summary(df, channel_name):
    """Render monthly summary with pie charts comparing channel sources."""
    st.markdown('<div class="section-header"><h3>📊 MONTHLY SUMMARY BY CHANNEL SOURCE</h3></div>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No monthly data available for charts")
        return

    # Filter out summary rows
    df_filtered = df[~df['channel'].str.contains('平均|总计|Average|Total', case=False, na=False)].copy()

    if df_filtered.empty:
        st.warning("No monthly data available for charts")
        return

    df_filtered['date'] = pd.to_datetime(df_filtered['date'])
    df_filtered['month'] = df_filtered['date'].dt.to_period('M').astype(str)

    # Get unique months
    months = sorted(df_filtered['month'].unique())

    # Let user select a month
    selected_month = st.selectbox("Select Month", months, index=len(months)-1 if months else 0, key="month_select")

    # Filter data for selected month
    month_data = df_filtered[df_filtered['month'] == selected_month]

    # Aggregate by channel source for selected month
    monthly_agg = month_data.groupby('channel').agg({
        'first_recharge': 'sum',
        'total_amount': 'sum',
        'spending': 'sum',
    }).reset_index()

    monthly_agg['roas'] = monthly_agg.apply(
        lambda x: x['total_amount'] / x['spending'] if x['spending'] > 0 else 0, axis=1)

    st.markdown(f"#### Month: {selected_month}")

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(monthly_agg['channel'], monthly_agg['first_recharge'],
                            'First Recharge Distribution', 'count')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = make_pie_chart(monthly_agg['channel'], monthly_agg['total_amount'],
                            'Total Recharge Amount Distribution', 'php')
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig = make_pie_chart(monthly_agg['channel'], monthly_agg['spending'],
                            'Spending Distribution', 'usd')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(monthly_agg.sort_values('roas', ascending=True),
                    x='roas', y='channel', orientation='h',
                    title='ROAS Comparison')
        fig.update_layout(height=400, xaxis_title="ROAS", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


def render_data_table(df, channel_name):
    """Render detailed data table for a single channel."""
    st.markdown('<div class="section-header"><h3>📋 DETAILED DATA</h3></div>', unsafe_allow_html=True)

    if df.empty:
        st.info(f"No {channel_name} data available")
        return

    display_df = df.copy()
    display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%Y-%m-%d')
    display_df = display_df.sort_values('date', ascending=False)

    # Select and rename columns for display
    display_cols = ['date', 'channel', 'first_recharge', 'total_amount', 'arppu', 'spending', 'cost_per_recharge', 'roas']
    display_df = display_df[display_cols]
    display_df.columns = ['Date', 'Channel', 'First Recharge', 'Total Recharge Amount', 'ARPPU', 'Spending', 'Cost/Recharge', 'ROAS']

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False)
    channel_lower = channel_name.lower()
    st.download_button(
        f"📥 Download {channel_name} CSV",
        csv,
        f"counterpart_{channel_lower}_{datetime.now():%Y%m%d}.csv",
        "text/csv"
    )


def main():
    st.title("📊 Counterpart Performance Dashboard")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    # Load data
    with st.spinner("Loading data..."):
        data = load_counterpart_data()
        fb_df = data.get('fb', pd.DataFrame())
        google_df = data.get('google', pd.DataFrame())
        fb_overall_df = data.get('fb_overall', pd.DataFrame())
        google_overall_df = data.get('google_overall', pd.DataFrame())

    # Check data availability
    has_fb = not fb_df.empty
    has_google = not google_df.empty

    if not has_fb and not has_google:
        st.error("No Counterpart Performance data available.")
        st.info("Check that the 'Counterpart Performance' sheet exists and has data.")
        return

    # Build channel options based on available data
    channel_options = []
    if has_fb:
        channel_options.append("Facebook")
    if has_google:
        channel_options.append("Google")

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_counterpart_data()
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("📢 Select Channel")
        selected_channel = st.radio("Channel", channel_options, index=0)

        # Get the selected dataframe
        if selected_channel == "Facebook":
            selected_df = fb_df.copy()
        else:
            selected_df = google_df.copy()

        selected_df['date'] = pd.to_datetime(selected_df['date'])

        # Date range based on selected channel
        data_min_date = selected_df['date'].min().date()
        data_max_date = selected_df['date'].max().date()
        yesterday = datetime.now().date() - timedelta(days=1)
        max_selectable_date = min(data_max_date, yesterday)

        st.markdown("---")
        st.subheader("📅 Date Range")

        default_start = max(data_min_date, max_selectable_date - timedelta(days=30))
        date_from = st.date_input("From", value=default_start, min_value=data_min_date, max_value=max_selectable_date)
        date_to = st.date_input("To", value=max_selectable_date, min_value=data_min_date, max_value=max_selectable_date)

        st.markdown("---")
        st.subheader("Other Reports")
        st.markdown("📈 [Daily ROI](/Daily_ROI)")
        st.markdown("📈 [Roll Back](/Roll_Back)")
        st.markdown("📈 [Violet](/Violet)")

    # Filter by date
    filtered_df = selected_df[(selected_df['date'].dt.date >= date_from) & (selected_df['date'].dt.date <= date_to)]

    if filtered_df.empty:
        st.warning("No data available for the selected date range.")
        return

    # Display channel indicator
    channel_icon = "📘" if selected_channel == "Facebook" else "📕"
    st.markdown(f"### {channel_icon} {selected_channel} Performance Report")

    # Get overall data for selected channel
    selected_overall_df = fb_overall_df if selected_channel == "Facebook" else google_overall_df

    # Render sections for single channel
    render_overall_summary(selected_overall_df, selected_channel)

    st.divider()
    render_daily_trends(filtered_df, selected_channel)

    st.divider()
    render_weekly_summary(filtered_df, selected_channel)

    st.divider()
    render_monthly_summary(filtered_df, selected_channel)

    st.divider()
    render_data_table(filtered_df, selected_channel)

    st.caption(f"Counterpart Performance Dashboard | {selected_channel} | {date_from} to {date_to}")


if __name__ == "__main__":
    main()
