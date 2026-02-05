"""
Report Dashboard for Real-Time KPI Monitoring
Visual dashboard for screenshot-based reports
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader import load_facebook_ads_data
from config import (
    LOW_SPEND_THRESHOLD_USD, LAST_REPORT_DATA_FILE,
    FACEBOOK_ADS_PERSONS
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


def load_last_report_data():
    """Load previous report data for change detection"""
    try:
        report_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), LAST_REPORT_DATA_FILE)
        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading last report data: {e}")
    return None


def calculate_change(current, previous, key):
    """Calculate change between current and previous values"""
    if previous is None:
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
    current_date = now.strftime("%B %d, %Y")

    # Dashboard Header
    st.markdown(f"""
    <div class="dashboard-header">
        <h1>📊 ADVERTISER KPI DASHBOARD</h1>
        <p style="font-size: 1.2em; margin: 0;">{current_date} | {current_time}</p>
    </div>
    """, unsafe_allow_html=True)

    # Send Report Button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    with col_btn1:
        if st.button("📤 Send to Telegram", type="primary", use_container_width=True):
            try:
                from telegram_reporter import TelegramReporter
                from realtime_reporter import (
                    get_latest_date_data, load_previous_report, compare_with_previous,
                    check_low_spend, detect_no_change_agents, generate_text_summary,
                    prepare_report_data, save_current_report
                )
                from config import NO_CHANGE_ALERT

                with st.spinner("Sending report to Telegram..."):
                    # Get data
                    current_data, latest_date = get_latest_date_data()
                    if current_data is None or current_data.empty:
                        st.error("No data available")
                    else:
                        # Load previous for comparison
                        previous_data = load_previous_report()
                        changes = compare_with_previous(current_data, previous_data, latest_date)
                        low_spend = check_low_spend(current_data)
                        no_change = detect_no_change_agents(changes) if NO_CHANGE_ALERT else []

                        # Generate text summary
                        text_summary = generate_text_summary(
                            current_data, latest_date, changes, low_spend, no_change
                        )

                        # Send to Telegram
                        reporter = TelegramReporter()
                        reporter.send_message(text_summary)

                        # Save for next comparison
                        report_data = prepare_report_data(current_data, latest_date)
                        save_current_report(report_data)

                        st.success("✅ Report sent!")
            except ValueError as e:
                st.error(f"⚠️ Telegram not configured: {e}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    with col_btn2:
        if st.button("🔄 Refresh Data", type="secondary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("")  # Spacer

    # Load data
    with st.spinner("Loading data..."):
        fb_ads_df = load_facebook_ads_data()

    if fb_ads_df is None or fb_ads_df.empty:
        st.error("No Facebook Ads data available")
        return

    # Get latest date in data
    fb_ads_df['date_only'] = pd.to_datetime(fb_ads_df['date']).dt.date
    latest_date = fb_ads_df['date_only'].max()

    # Filter for latest date
    today_data = fb_ads_df[fb_ads_df['date_only'] == latest_date]

    if today_data.empty:
        st.warning(f"No data for {latest_date}")
        return

    # Load previous report for change detection
    previous_data = load_last_report_data()

    # Calculate team totals
    team_totals = {
        'spend': today_data['spend'].sum(),
        'register': int(today_data['register'].sum()),
        'ftd': int(today_data['result_ftd'].sum()),
        'impressions': int(today_data['impressions'].sum()),
        'clicks': int(today_data['clicks'].sum()),
        'reach': int(today_data['reach'].sum()),
    }

    # Derived metrics
    team_totals['cpr'] = team_totals['spend'] / team_totals['register'] if team_totals['register'] > 0 else 0
    team_totals['cpftd'] = team_totals['spend'] / team_totals['ftd'] if team_totals['ftd'] > 0 else 0
    team_totals['ctr'] = (team_totals['clicks'] / team_totals['impressions'] * 100) if team_totals['impressions'] > 0 else 0
    team_totals['conv_rate'] = (team_totals['ftd'] / team_totals['register'] * 100) if team_totals['register'] > 0 else 0

    # SECTION 1: Team Totals
    st.markdown("### 💰 TEAM TOTALS")

    col1, col2, col3, col4, col5 = st.columns(5)

    # Get previous totals for comparison
    prev_totals = previous_data.get('team_totals', {}) if previous_data else {}

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
    agent_data = today_data.groupby('person_name').agg({
        'spend': 'sum',
        'register': 'sum',
        'result_ftd': 'sum',
        'impressions': 'sum',
        'clicks': 'sum'
    }).reset_index()

    # Sort by spend descending
    agent_data = agent_data.sort_values('spend', ascending=False)

    # Get previous agent data
    prev_agents = previous_data.get('agents', {}) if previous_data else {}

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
                agent_name = agent['person_name']
                spend = agent['spend']
                reg = int(agent['register'])
                ftd = int(agent['result_ftd'])

                # Get previous data for this agent
                prev_agent = prev_agents.get(agent_name, {})

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
                elif not is_low_spend:
                    card_class += " agent-card-ok"

                # Status indicator
                if is_low_spend:
                    status = "⚠️ LOW SPEND"
                elif has_no_change:
                    status = "📊 No Change"
                else:
                    status = "✅ Active"

                # Calculate efficiency
                cpr = spend / reg if reg > 0 else 0
                cpftd = spend / ftd if ftd > 0 else 0

                with col:
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4 style="margin:0; color:#333;">{agent_name}</h4>
                        <p style="color:#666; margin:5px 0;">{status}</p>
                        <hr style="margin:10px 0;">
                        <p><strong>Spend:</strong> ${spend:,.2f} <span class="{get_change_class(spend_diff)}">{spend_change}</span></p>
                        <p><strong>Register:</strong> {reg:,}</p>
                        <p><strong>FTD:</strong> {ftd:,} <span class="{get_change_class(ftd_diff)}">{ftd_change}</span></p>
                        <p><strong>CPR:</strong> ${cpr:.2f}</p>
                        <p><strong>Cost/FTD:</strong> ${cpftd:.2f}</p>
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
            x='person_name',
            y='spend',
            title='Spend by Agent',
            color='spend',
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
            x='person_name',
            y='result_ftd',
            title='FTD by Agent',
            color='result_ftd',
            color_continuous_scale='Greens'
        )
        fig_ftd.update_layout(
            xaxis_title="Agent",
            yaxis_title="FTD Count",
            showlegend=False
        )
        st.plotly_chart(fig_ftd, use_container_width=True)

    # Cost Efficiency Chart
    agent_data['cpr'] = agent_data.apply(lambda x: x['spend'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agent_data['cpftd'] = agent_data.apply(lambda x: x['spend'] / x['result_ftd'] if x['result_ftd'] > 0 else 0, axis=1)

    col1, col2 = st.columns(2)

    with col1:
        # Cost per Register chart
        fig_cpr = px.bar(
            agent_data[agent_data['cpr'] > 0],
            x='person_name',
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
            x='person_name',
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
    st.caption(f"Data as of: {latest_date} | Dashboard generated: {now.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
