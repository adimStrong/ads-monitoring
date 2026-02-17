"""
Report Dashboard for Real-Time KPI Monitoring
Visual dashboard for screenshot-based reports
Data source: P-tabs (P6-P13) from Channel ROI sheet
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_agent_performance_data
from config import (
    LOW_SPEND_THRESHOLD_USD,
    EXCLUDED_PERSONS,
)

st.set_page_config(
    page_title="Advertiser KPI Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for dashboard cards
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 5px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .metric-card-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    .metric-card-orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    .metric-card-blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    }
    .metric-card-gold {
        background: linear-gradient(135deg, #f5af19 0%, #f12711 100%);
    }
    .metric-value {
        font-size: 2em;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 0.9em;
        opacity: 0.9;
    }
    .agent-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 10px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .agent-card-warning {
        border-left-color: #f5576c;
        background: #fff5f5;
    }
    .agent-card-ok {
        border-left-color: #38ef7d;
    }
    .change-up {
        color: #38ef7d;
        font-weight: bold;
    }
    .change-down {
        color: #f5576c;
        font-weight: bold;
    }
    .change-neutral {
        color: #888;
    }
    .alert-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .alert-box-danger {
        background: #f8d7da;
        border-color: #f5c6cb;
    }
    .dashboard-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)



def calculate_change(current, previous, key):
    """Calculate change between current and previous values"""
    if not previous or key not in previous:
        return None, "─"

    prev_val = previous.get(key, 0)
    diff = current - prev_val

    if diff > 0:
        return diff, f"↑ +{diff:,.0f}" if isinstance(diff, (int, float)) else f"↑ +{diff}"
    elif diff < 0:
        return diff, f"↓ {diff:,.0f}" if isinstance(diff, (int, float)) else f"↓ {diff}"
    else:
        return 0, "─"


def get_change_class(diff):
    """Get CSS class based on change direction"""
    if diff is None or diff == 0:
        return "change-neutral"
    elif diff > 0:
        return "change-up"
    else:
        return "change-down"


def main():
    # Get current timestamp
    now = datetime.now()
    current_time = now.strftime("%I:%M %p")

    # Dashboard Header (date updated after data loads below)
    header_placeholder = st.empty()

    # Send Report Button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    with col_btn1:
        if st.button("📤 Send to Telegram", type="primary", use_container_width=True):
            try:
                from telegram_reporter import TelegramReporter
                from send_daily_report import send_report
                with st.spinner("Sending report to Telegram..."):
                    success = send_report()
                    if success:
                        st.success("✅ Report sent!")
                    else:
                        st.error("❌ Failed to send report")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    with col_btn2:
        if st.button("🔄 Refresh Data", type="secondary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("")  # Spacer

    # Load P-tab data
    with st.spinner("Loading P-tab data..."):
        ptab_data = load_agent_performance_data()

    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()

    if daily_df is None or daily_df.empty:
        st.error("No P-tab data available")
        return

    # Exclude agents
    excluded = [e.upper() for e in EXCLUDED_PERSONS] if EXCLUDED_PERSONS else []
    if excluded:
        daily_df = daily_df[~daily_df['agent'].str.upper().isin(excluded)]

    # Get all dates in data
    daily_df['date_only'] = pd.to_datetime(daily_df['date']).dt.date
    available_dates = sorted(daily_df['date_only'].unique(), reverse=True)

    if not available_dates:
        st.error("No dates available in P-tab data")
        return

    # Date filter
    col_date, col_spacer = st.columns([1, 3])
    with col_date:
        selected_date = st.selectbox(
            "📅 Select Date",
            options=available_dates,
            index=0,
            format_func=lambda d: d.strftime("%b %d, %Y (%A)"),
        )

    # Filter for selected date
    today_data = daily_df[daily_df['date_only'] == selected_date]

    if today_data.empty:
        st.warning(f"No data for {selected_date}")
        return

    # Update header with selected date
    current_date = selected_date.strftime("%B %d, %Y")

    # Render header with selected date
    header_placeholder.markdown(f"""
    <div class="dashboard-header">
        <h1>📊 ADVERTISER KPI DASHBOARD</h1>
        <p style="font-size: 1.2em; margin: 0;">{current_date} | {current_time}</p>
    </div>
    """, unsafe_allow_html=True)

    # Get yesterday's data for change detection
    yesterday_date = selected_date - timedelta(days=1)
    yesterday_data = daily_df[daily_df['date_only'] == yesterday_date]

    # Calculate team totals
    team_totals = {
        'spend': today_data['cost'].sum(),
        'register': int(today_data['register'].sum()),
        'ftd': int(today_data['ftd'].sum()),
        'impressions': int(today_data['impressions'].sum()),
        'clicks': int(today_data['clicks'].sum()),
    }

    # Derived metrics
    team_totals['cpr'] = team_totals['spend'] / team_totals['register'] if team_totals['register'] > 0 else 0
    team_totals['cpftd'] = team_totals['spend'] / team_totals['ftd'] if team_totals['ftd'] > 0 else 0
    team_totals['ctr'] = (team_totals['clicks'] / team_totals['impressions'] * 100) if team_totals['impressions'] > 0 else 0
    team_totals['conv_rate'] = (team_totals['ftd'] / team_totals['register'] * 100) if team_totals['register'] > 0 else 0

    # Yesterday's team totals for comparison
    if not yesterday_data.empty:
        prev_totals = {
            'spend': yesterday_data['cost'].sum(),
            'register': int(yesterday_data['register'].sum()),
            'ftd': int(yesterday_data['ftd'].sum()),
            'impressions': int(yesterday_data['impressions'].sum()),
            'clicks': int(yesterday_data['clicks'].sum()),
        }
    else:
        prev_totals = {}

    # SECTION 1: Team Totals
    st.markdown("### 💰 TEAM TOTALS")
    if prev_totals:
        st.caption(f"vs {yesterday_date.strftime('%b %d, %Y')}")
    else:
        st.caption("No previous day data for comparison")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        spend_diff, spend_change = calculate_change(team_totals['spend'], prev_totals, 'spend')
        change_class = get_change_class(spend_diff)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Spend</div>
            <div class="metric-value">${team_totals['spend']:,.2f}</div>
            <div class="{change_class}">{spend_change}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        reg_diff, reg_change = calculate_change(team_totals['register'], prev_totals, 'register')
        change_class = get_change_class(reg_diff)
        st.markdown(f"""
        <div class="metric-card metric-card-green">
            <div class="metric-label">Registrations</div>
            <div class="metric-value">{team_totals['register']:,}</div>
            <div class="{change_class}">{reg_change}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        ftd_diff, ftd_change = calculate_change(team_totals['ftd'], prev_totals, 'ftd')
        change_class = get_change_class(ftd_diff)
        st.markdown(f"""
        <div class="metric-card metric-card-gold">
            <div class="metric-label">FTD (First Deposit)</div>
            <div class="metric-value">{team_totals['ftd']:,}</div>
            <div class="{change_class}">{ftd_change}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card metric-card-blue">
            <div class="metric-label">Cost Per Register</div>
            <div class="metric-value">${team_totals['cpr']:.2f}</div>
            <div class="metric-label">Target: &lt;$2</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="metric-card metric-card-orange">
            <div class="metric-label">Cost Per FTD</div>
            <div class="metric-value">${team_totals['cpftd']:.2f}</div>
            <div class="metric-label">Target: &lt;$8</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # SECTION 2: Agent Performance Cards
    st.markdown("### 👥 AGENT PERFORMANCE")

    # Get agent data
    agent_data = today_data.groupby('agent').agg({
        'cost': 'sum',
        'register': 'sum',
        'ftd': 'sum',
        'impressions': 'sum',
        'clicks': 'sum'
    }).reset_index()

    # Sort by cost descending
    agent_data = agent_data.sort_values('cost', ascending=False)

    # Get previous agent data from yesterday's P-tab data
    prev_agents = {}
    if not yesterday_data.empty:
        yest_agent_data = yesterday_data.groupby('agent').agg({
            'cost': 'sum', 'register': 'sum', 'ftd': 'sum',
            'impressions': 'sum', 'clicks': 'sum'
        }).reset_index()
        for _, row in yest_agent_data.iterrows():
            prev_agents[row['agent']] = {
                'spend': row['cost'], 'register': int(row['register']),
                'ftd': int(row['ftd']), 'impressions': int(row['impressions']),
                'clicks': int(row['clicks']),
            }

    # Check for low spend and no change alerts
    low_spend_agents = []
    no_change_agents = []

    # Create agent cards in rows of 4
    num_agents = len(agent_data)
    cols_per_row = 4

    for i in range(0, num_agents, cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < num_agents:
                agent = agent_data.iloc[i + j]
                agent_name = agent['agent']
                spend = agent['cost']
                reg = int(agent['register'])
                ftd = int(agent['ftd'])

                # Get previous data for this agent (try both original name and uppercase)
                prev_agent = prev_agents.get(agent_name, prev_agents.get(agent_name.upper(), {}))

                # Calculate changes
                spend_diff, spend_change = calculate_change(spend, prev_agent, 'spend')
                ftd_diff, ftd_change = calculate_change(ftd, prev_agent, 'ftd')

                # Check for alerts
                is_low_spend = spend < LOW_SPEND_THRESHOLD_USD
                has_no_change = (spend_diff == 0 and ftd_diff == 0 and prev_agent)

                if is_low_spend:
                    low_spend_agents.append((agent_name, spend))
                if has_no_change:
                    no_change_agents.append(agent_name)

                # Determine card style
                card_class = "agent-card"
                if is_low_spend:
                    card_class += " agent-card-warning"
                else:
                    card_class += " agent-card-ok"

                # Status indicator
                if is_low_spend:
                    status = "⚠️ LOW SPEND"
                elif has_no_change:
                    status = "📊 No Change"
                else:
                    status = "✅ Active"

                # Calculate efficiency
                impressions = int(agent['impressions'])
                clicks = int(agent['clicks'])
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cpr = spend / reg if reg > 0 else 0
                cpftd = spend / ftd if ftd > 0 else 0
                conv_rate = (ftd / reg * 100) if reg > 0 else 0

                with col:
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4 style="margin:0; color:#333;">{agent_name}</h4>
                        <p style="color:#666; margin:5px 0;">{status}</p>
                        <hr style="margin:10px 0;">
                        <p><strong>Spend:</strong> ${spend:,.2f} <span class="{get_change_class(spend_diff)}">{spend_change}</span></p>
                        <p><strong>Register:</strong> {reg:,}</p>
                        <p><strong>FTD:</strong> {ftd:,} <span class="{get_change_class(ftd_diff)}">{ftd_change}</span></p>
                        <p><strong>CTR:</strong> {ctr:.2f}%</p>
                        <p><strong>CPR:</strong> ${cpr:.2f}</p>
                        <p><strong>Cost/FTD:</strong> ${cpftd:.2f}</p>
                        <p><strong>Conv:</strong> {conv_rate:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

    # SECTION 3: Spend vs Results Chart
    st.markdown("### 📈 SPEND VS RESULTS")

    col1, col2 = st.columns(2)

    with col1:
        # Bar chart: Spend by agent
        fig_spend = px.bar(
            agent_data,
            x='agent',
            y='cost',
            title='Spend by Agent',
            color='cost',
            color_continuous_scale='Blues'
        )
        fig_spend.update_layout(
            xaxis_title="Agent",
            yaxis_title="Spend (USD)",
            showlegend=False
        )
        st.plotly_chart(fig_spend, use_container_width=True)

    with col2:
        # Bar chart: FTD by agent
        fig_ftd = px.bar(
            agent_data,
            x='agent',
            y='ftd',
            title='FTD by Agent',
            color='ftd',
            color_continuous_scale='Greens'
        )
        fig_ftd.update_layout(
            xaxis_title="Agent",
            yaxis_title="FTD Count",
            showlegend=False
        )
        st.plotly_chart(fig_ftd, use_container_width=True)

    # Cost Efficiency Chart
    agent_data['cpr'] = agent_data.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agent_data['cpftd'] = agent_data.apply(lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        # Cost per Register chart
        fig_cpr = px.bar(
            agent_data[agent_data['cpr'] > 0],
            x='agent',
            y='cpr',
            title='Cost Per Register by Agent',
            color='cpr',
            color_continuous_scale='Reds_r'  # Lower is better (reversed)
        )
        fig_cpr.add_hline(y=2, line_dash="dash", line_color="green", annotation_text="Target: $2")
        fig_cpr.update_layout(
            xaxis_title="Agent",
            yaxis_title="CPR (USD)",
            showlegend=False
        )
        st.plotly_chart(fig_cpr, use_container_width=True)

    with col2:
        # Cost per FTD chart
        fig_cpftd = px.bar(
            agent_data[agent_data['cpftd'] > 0],
            x='agent',
            y='cpftd',
            title='Cost Per FTD by Agent',
            color='cpftd',
            color_continuous_scale='Oranges_r'  # Lower is better (reversed)
        )
        fig_cpftd.add_hline(y=8, line_dash="dash", line_color="green", annotation_text="Target: $8")
        fig_cpftd.update_layout(
            xaxis_title="Agent",
            yaxis_title="Cost/FTD (USD)",
            showlegend=False
        )
        st.plotly_chart(fig_cpftd, use_container_width=True)

    st.markdown("---")

    # SECTION 4: Alerts & Notifications
    st.markdown("### ⚠️ ALERTS & NOTIFICATIONS")

    if low_spend_agents or no_change_agents:
        for agent_name, spend in low_spend_agents:
            st.markdown(f"""
            <div class="alert-box alert-box-danger">
                <strong>⚠️ {agent_name}:</strong> Low spend (${spend:.2f}) - Please focus and work hard!
            </div>
            """, unsafe_allow_html=True)

        for agent_name in no_change_agents:
            st.markdown(f"""
            <div class="alert-box">
                <strong>📊 {agent_name}:</strong> No change detected since last report
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ All agents are performing well! No alerts at this time.")

    # Footer with data timestamp
    st.markdown("---")
    st.caption(f"Data as of: {selected_date} | Dashboard generated: {now.strftime('%Y-%m-%d %H:%M:%S')} | Source: P-tabs")


if __name__ == "__main__":
    main()
