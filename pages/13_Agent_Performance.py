"""
Agent Performance Dashboard (P-tabs)
Shows per-agent FB advertising performance: monthly summary, daily trends, ad account breakdown.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import load_agent_performance_data, refresh_agent_performance_data
from config import CHANNEL_ROI_ENABLED

st.set_page_config(page_title="Agent Performance (P-tabs)", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 18px; border-radius: 12px; color: white; text-align: center;
    }
    .metric-card h4 { margin: 0 0 6px 0; font-size: 0.85rem; opacity: 0.85; }
    .metric-card h2 { margin: 0; font-size: 1.5rem; }
    .agent-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 16px; border-radius: 10px; color: white; margin-bottom: 8px;
    }
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

AGENT_COLORS = {
    'Mika': '#667eea', 'Adrian': '#f093fb', 'Jomar': '#4facfe',
    'Derr': '#43e97b', 'Ron': '#fa709a', 'Krissa': '#fee140',
    'Jason': '#a18cd1', 'Shila': '#fbc2eb',
}


def fmt_currency(v):
    if pd.isna(v) or v == 0:
        return "$0.00"
    return f"${v:,.2f}"


def fmt_int(v):
    if pd.isna(v):
        return "0"
    return f"{int(v):,}"


def fmt_pct(v):
    if pd.isna(v) or v == 0:
        return "0.0%"
    return f"{v:.1f}%"


def fmt_ratio(v):
    if pd.isna(v) or v == 0:
        return "0.00"
    return f"{v:.2f}"


def render_kpi_cards(cost, register, ftd, cpr, roas):
    cols = st.columns(5)
    cards = [
        ("Total Cost", fmt_currency(cost)),
        ("Registrations", fmt_int(register)),
        ("First Deposits", fmt_int(ftd)),
        ("Avg CPR", fmt_currency(cpr)),
        ("Avg ROAS", fmt_ratio(roas)),
    ]
    for col, (label, val) in zip(cols, cards):
        col.markdown(f"""
        <div class="metric-card">
            <h4>{label}</h4>
            <h2>{val}</h2>
        </div>""", unsafe_allow_html=True)


def main():
    st.title("📈 Agent Performance (P-tabs)")
    st.markdown("Per-agent FB advertising performance from Channel ROI P-tabs")

    if not CHANNEL_ROI_ENABLED:
        st.warning("Channel ROI Dashboard is disabled.")
        return

    with st.spinner("Loading agent performance data..."):
        data = load_agent_performance_data()

    monthly_df = data.get('monthly', pd.DataFrame())
    daily_df = data.get('daily', pd.DataFrame())
    ad_df = data.get('ad_accounts', pd.DataFrame())

    if daily_df.empty and monthly_df.empty:
        st.error("No agent performance data available. Check that P-tabs exist in the Channel ROI sheet.")
        return

    agents = sorted(daily_df['agent'].unique().tolist()) if not daily_df.empty else sorted(monthly_df['agent'].unique().tolist())

    # --- Sidebar ---
    with st.sidebar:
        st.header("Controls")

        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            refresh_agent_performance_data()
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        agent_options = ["All Agents"] + agents
        selected_agent = st.selectbox("Agent", agent_options)

        view_mode = st.radio("View", ["Monthly", "Daily"], horizontal=True)

        if not daily_df.empty:
            st.markdown("---")
            st.caption(f"Data: {len(agents)} agents, {len(daily_df)} daily rows")

    # --- Filter data ---
    if selected_agent != "All Agents":
        m_df = monthly_df[monthly_df['agent'] == selected_agent] if not monthly_df.empty else pd.DataFrame()
        d_df = daily_df[daily_df['agent'] == selected_agent] if not daily_df.empty else pd.DataFrame()
        a_df = ad_df[ad_df['agent'] == selected_agent] if not ad_df.empty else pd.DataFrame()
    else:
        m_df = monthly_df
        d_df = daily_df
        a_df = ad_df

    # ==========================================
    # MONTHLY VIEW
    # ==========================================
    if view_mode == "Monthly":
        st.markdown('<div class="section-header"><h3>Monthly Overview</h3></div>', unsafe_allow_html=True)

        if m_df.empty:
            st.info("No monthly data available yet.")
        else:
            # KPI cards
            total_cost = m_df['cost'].sum()
            total_reg = m_df['register'].sum()
            total_ftd = m_df['ftd'].sum()
            avg_cpr = total_cost / total_reg if total_reg > 0 else 0
            avg_roas = m_df['roas'].mean()
            render_kpi_cards(total_cost, total_reg, total_ftd, avg_cpr, avg_roas)

            st.markdown("")

            if selected_agent == "All Agents":
                # Cost by agent bar chart
                agent_monthly = m_df.groupby('agent').agg({
                    'cost': 'sum', 'register': 'sum', 'ftd': 'sum',
                    'impressions': 'sum', 'clicks': 'sum',
                }).reset_index()
                agent_monthly['cpr'] = agent_monthly.apply(
                    lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
                agent_monthly['roas'] = m_df.groupby('agent')['roas'].mean().values

                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(
                        agent_monthly.sort_values('cost', ascending=True),
                        y='agent', x='cost', orientation='h',
                        title='Cost by Agent',
                        color='agent', color_discrete_map=AGENT_COLORS,
                        text_auto='$.2s',
                    )
                    fig.update_layout(height=350, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.bar(
                        agent_monthly.sort_values('ftd', ascending=True),
                        y='agent', x='ftd', orientation='h',
                        title='First Deposits by Agent',
                        color='agent', color_discrete_map=AGENT_COLORS,
                        text_auto=True,
                    )
                    fig.update_layout(height=350, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                # Summary table
                st.markdown('<div class="section-header"><h3>Agent Monthly Summary</h3></div>', unsafe_allow_html=True)
                display_df = agent_monthly[['agent', 'cost', 'register', 'ftd', 'cpr', 'impressions', 'clicks', 'roas']].copy()
                display_df.columns = ['Agent', 'Cost', 'Register', 'FTD', 'CPR', 'Impressions', 'Clicks', 'ROAS']
                st.dataframe(
                    display_df.sort_values('Cost', ascending=False),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "Cost": st.column_config.NumberColumn(format="$%.2f"),
                        "CPR": st.column_config.NumberColumn(format="$%.2f"),
                        "ROAS": st.column_config.NumberColumn(format="%.2f"),
                        "Impressions": st.column_config.NumberColumn(format="%d"),
                        "Clicks": st.column_config.NumberColumn(format="%d"),
                    },
                )
            else:
                # Single agent monthly details
                st.dataframe(
                    m_df[['month', 'cost', 'register', 'cpr', 'ftd', 'cpd', 'conv_rate', 'impressions', 'clicks', 'ctr', 'arppu', 'roas']],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                        "cpr": st.column_config.NumberColumn("CPR", format="$%.2f"),
                        "cpd": st.column_config.NumberColumn("CPD", format="$%.2f"),
                        "conv_rate": st.column_config.NumberColumn("Conv %", format="%.1f%%"),
                        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "arppu": st.column_config.NumberColumn("ARPPU", format="$%.2f"),
                        "roas": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    },
                )

    # ==========================================
    # DAILY VIEW
    # ==========================================
    else:
        st.markdown('<div class="section-header"><h3>Daily Overview</h3></div>', unsafe_allow_html=True)

        if d_df.empty:
            st.info("No daily data available yet.")
        else:
            # KPI cards for latest date
            latest_date = d_df['date'].max()
            latest_data = d_df[d_df['date'] == latest_date]
            total_cost = latest_data['cost'].sum()
            total_reg = latest_data['register'].sum()
            total_ftd = latest_data['ftd'].sum()
            avg_cpr = total_cost / total_reg if total_reg > 0 else 0
            avg_roas = latest_data['roas'].mean()

            st.caption(f"Latest data: {latest_date.strftime('%b %d, %Y')}")
            render_kpi_cards(total_cost, total_reg, total_ftd, avg_cpr, avg_roas)
            st.markdown("")

            if selected_agent == "All Agents":
                # Daily cost trend by agent
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.line(
                        d_df, x='date', y='cost', color='agent',
                        title='Daily Cost Trend',
                        color_discrete_map=AGENT_COLORS, markers=True,
                    )
                    fig.update_layout(height=350, xaxis_tickformat='%m/%d')
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.line(
                        d_df, x='date', y='ftd', color='agent',
                        title='Daily First Deposits Trend',
                        color_discrete_map=AGENT_COLORS, markers=True,
                    )
                    fig.update_layout(height=350, xaxis_tickformat='%m/%d')
                    st.plotly_chart(fig, use_container_width=True)

                # Daily data table
                st.markdown('<div class="section-header"><h3>Daily Data</h3></div>', unsafe_allow_html=True)
                table_df = d_df[['agent', 'date', 'cost', 'register', 'cpr', 'ftd', 'cpd', 'conv_rate', 'impressions', 'clicks', 'ctr', 'roas']].copy()
                table_df['date'] = table_df['date'].dt.strftime('%m/%d/%Y')
                st.dataframe(
                    table_df.sort_values(['date', 'agent'], ascending=[False, True]),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                        "cpr": st.column_config.NumberColumn("CPR", format="$%.2f"),
                        "cpd": st.column_config.NumberColumn("CPD", format="$%.2f"),
                        "conv_rate": st.column_config.NumberColumn("Conv %", format="%.1f%%"),
                        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "roas": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    },
                )
            else:
                # Single agent daily view
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(
                        d_df, x='date', y='cost',
                        title=f'{selected_agent} - Daily Cost',
                        color_discrete_sequence=[AGENT_COLORS.get(selected_agent, '#667eea')],
                    )
                    fig.update_layout(height=300, xaxis_tickformat='%m/%d')
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.bar(
                        d_df, x='date', y='ftd',
                        title=f'{selected_agent} - Daily FTD',
                        color_discrete_sequence=[AGENT_COLORS.get(selected_agent, '#667eea')],
                    )
                    fig.update_layout(height=300, xaxis_tickformat='%m/%d')
                    st.plotly_chart(fig, use_container_width=True)

                # Daily table for this agent
                table_df = d_df[['date', 'cost', 'register', 'cpr', 'ftd', 'cpd', 'conv_rate', 'impressions', 'clicks', 'ctr', 'arppu', 'roas']].copy()
                table_df['date'] = table_df['date'].dt.strftime('%m/%d/%Y')
                st.dataframe(
                    table_df.sort_values('date', ascending=False),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                        "cpr": st.column_config.NumberColumn("CPR", format="$%.2f"),
                        "cpd": st.column_config.NumberColumn("CPD", format="$%.2f"),
                        "conv_rate": st.column_config.NumberColumn("Conv %", format="%.1f%%"),
                        "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "arppu": st.column_config.NumberColumn("ARPPU", format="$%.2f"),
                        "roas": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    },
                )

                # Ad account breakdown
                if not a_df.empty:
                    st.markdown(f'<div class="section-header"><h3>{selected_agent} - Ad Account Breakdown</h3></div>', unsafe_allow_html=True)

                    # Cost by ad account
                    acct_summary = a_df.groupby('ad_account').agg({
                        'cost': 'sum', 'impressions': 'sum', 'clicks': 'sum',
                    }).reset_index()
                    acct_summary['ctr'] = acct_summary.apply(
                        lambda x: (x['clicks'] / x['impressions'] * 100) if x['impressions'] > 0 else 0, axis=1)

                    fig = px.bar(
                        acct_summary.sort_values('cost', ascending=True),
                        y='ad_account', x='cost', orientation='h',
                        title='Cost by Ad Account',
                        text_auto='$.2s',
                    )
                    fig.update_layout(height=max(250, len(acct_summary) * 40), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # Ad account table
                    acct_summary.columns = ['Ad Account', 'Cost', 'Impressions', 'Clicks', 'CTR']
                    st.dataframe(
                        acct_summary.sort_values('Cost', ascending=False),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "Cost": st.column_config.NumberColumn(format="$%.2f"),
                            "Impressions": st.column_config.NumberColumn(format="%d"),
                            "Clicks": st.column_config.NumberColumn(format="%d"),
                            "CTR": st.column_config.NumberColumn(format="%.2f%%"),
                        },
                    )

                    # Per-account daily detail (expandable)
                    with st.expander("Per-Account Daily Detail"):
                        acct_daily = a_df.copy()
                        acct_daily['date'] = acct_daily['date'].dt.strftime('%m/%d/%Y')
                        st.dataframe(
                            acct_daily.sort_values(['date', 'ad_account'], ascending=[False, True]),
                            use_container_width=True, hide_index=True,
                            column_config={
                                "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                                "impressions": st.column_config.NumberColumn("Impressions", format="%d"),
                                "clicks": st.column_config.NumberColumn("Clicks", format="%d"),
                                "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                            },
                        )


main()
