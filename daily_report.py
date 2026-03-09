"""
Daily Report Generator for BINGO365 Monitoring
Generates and sends daily reports to Telegram
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import load_agent_performance_data, load_agent_content_data, load_indian_promotion_content
from channel_data_loader import (
    load_agent_performance_data as load_ptab_data,
    count_ab_testing, score_ab_testing,
    count_created_assets, score_account_dev,
)
from config import AGENTS, FACEBOOK_ADS_PERSONS, EXCLUDED_PERSONS, AGENT_PERFORMANCE_TABS
from telegram_reporter import TelegramReporter


def load_all_agent_data():
    """
    Load all data for all agents from Google Sheets

    Returns:
        tuple: (all_ads, all_creative, all_sms, all_content) - lists of DataFrames
    """
    all_ads = []
    all_creative = []
    all_sms = []
    all_content = []

    for agent in AGENTS:
        # Load performance data (running ads, creative, sms)
        try:
            running_ads, creative, sms = load_agent_performance_data(
                agent['name'],
                agent['sheet_performance']
            )

            if running_ads is not None and not running_ads.empty:
                all_ads.append(running_ads)
            if creative is not None and not creative.empty:
                all_creative.append(creative)
            if sms is not None and not sms.empty:
                all_sms.append(sms)
        except Exception as e:
            print(f"Error loading performance data for {agent['name']}: {e}")

        # Load content data
        try:
            content = load_agent_content_data(
                agent['name'],
                agent['sheet_content']
            )

            if content is not None and not content.empty:
                all_content.append(content)
        except Exception as e:
            print(f"Error loading content data for {agent['name']}: {e}")

    # Load Indian Promotion content (additional copywriting data)
    try:
        indian_content = load_indian_promotion_content()
        if indian_content is not None and not indian_content.empty:
            all_content.append(indian_content)
            print(f"Loaded {len(indian_content)} rows from Indian Promotion sheet")
    except Exception as e:
        print(f"Error loading Indian Promotion data: {e}")

    return all_ads, all_creative, all_sms, all_content


def get_data_for_date_range(ads_list, creative_list, sms_list, content_list, start_date, end_date):
    """
    Filter data for a specific date range

    Args:
        ads_list, creative_list, sms_list, content_list: Lists of DataFrames
        start_date, end_date: Date range to filter

    Returns:
        tuple: Filtered DataFrames (ads_df, creative_df, sms_df, content_df)
    """
    ads_df = pd.DataFrame()
    creative_df = pd.DataFrame()
    sms_df = pd.DataFrame()
    content_df = pd.DataFrame()

    if ads_list:
        ads_df = pd.concat(ads_list, ignore_index=True)
        if 'date' in ads_df.columns:
            ads_df['date_only'] = pd.to_datetime(ads_df['date']).dt.date
            ads_df = ads_df[(ads_df['date_only'] >= start_date) & (ads_df['date_only'] <= end_date)]

    if creative_list:
        creative_df = pd.concat(creative_list, ignore_index=True)
        if 'date' in creative_df.columns:
            creative_df['date_only'] = pd.to_datetime(creative_df['date']).dt.date
            creative_df = creative_df[(creative_df['date_only'] >= start_date) & (creative_df['date_only'] <= end_date)]

    if sms_list:
        sms_df = pd.concat(sms_list, ignore_index=True)
        if 'date' in sms_df.columns:
            sms_df['date_only'] = pd.to_datetime(sms_df['date']).dt.date
            sms_df = sms_df[(sms_df['date_only'] >= start_date) & (sms_df['date_only'] <= end_date)]

    if content_list:
        content_df = pd.concat(content_list, ignore_index=True)
        # Filter content by date if date column exists
        if 'date' in content_df.columns:
            content_df['date_only'] = pd.to_datetime(content_df['date']).dt.date
            content_df = content_df[(content_df['date_only'] >= start_date) & (content_df['date_only'] <= end_date)]

    return ads_df, creative_df, sms_df, content_df


def calculate_agent_stats(creative_df, sms_df, content_df):
    """
    Calculate stats per agent

    Note: creative_total and sms_total are daily totals (same value for all rows on same date),
    so we group by date first to avoid double-counting.

    Returns:
        dict: {agent_name: {'creative': X, 'sms': Y, 'copywriting': Z}}
    """
    stats = {}

    # Creative stats - group by agent+date, take first value (avoid duplicates), then sum
    if not creative_df.empty and 'agent_name' in creative_df.columns:
        for agent in creative_df['agent_name'].unique():
            if agent not in stats:
                stats[agent] = {'creative': 0, 'sms': 0, 'copywriting': 0}
            agent_data = creative_df[creative_df['agent_name'] == agent]
            if 'creative_total' in agent_data.columns and 'date' in agent_data.columns:
                # Group by date and take first value (daily total), then sum across dates
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['creative_total'].first()
                stats[agent]['creative'] = int(daily_totals.sum())
            else:
                stats[agent]['creative'] = len(agent_data)

    # SMS stats - same logic, group by date first
    if not sms_df.empty and 'agent_name' in sms_df.columns:
        for agent in sms_df['agent_name'].unique():
            if agent not in stats:
                stats[agent] = {'creative': 0, 'sms': 0, 'copywriting': 0}
            agent_data = sms_df[sms_df['agent_name'] == agent]
            if 'sms_total' in agent_data.columns and 'date' in agent_data.columns:
                # Group by date and take first value (daily total), then sum across dates
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['sms_total'].first()
                stats[agent]['sms'] = int(daily_totals.sum())
            else:
                stats[agent]['sms'] = len(agent_data)

    # Copywriting stats - only count Primary Text entries
    if not content_df.empty and 'agent_name' in content_df.columns:
        # Filter for Primary Text only
        if 'content_type' in content_df.columns:
            primary_df = content_df[content_df['content_type'] == 'Primary Text']
        else:
            primary_df = content_df

        for agent in primary_df['agent_name'].unique():
            if agent not in stats:
                stats[agent] = {'creative': 0, 'sms': 0, 'copywriting': 0}
            stats[agent]['copywriting'] = len(primary_df[primary_df['agent_name'] == agent])

    return stats


def classify_performance_tier(cost, ftd):
    """
    Classify a person into a performance tier based on cost and FTD.

    Tiers:
    - Top Performers: FTD >= 50 OR Cost >= $1,000
    - Mid Performers: FTD >= 20 OR Cost >= $400
    - Developing: Below mid tier thresholds
    """
    if ftd >= 50 or cost >= 1000:
        return 'top'
    elif ftd >= 20 or cost >= 400:
        return 'mid'
    else:
        return 'developing'


def generate_facebook_ads_section(daily_df, target_date, compare_days=7):
    """
    Generate Facebook Ads performance section from P-tab daily data.
    Uses Performance Tier Grouping (Top/Mid/Developing).

    Args:
        daily_df: DataFrame from P-tab daily data (columns: agent, date, cost, register, ftd, impressions, clicks, ctr, etc.)
        target_date: The date to report on (T+1)
        compare_days: Number of days for average comparison

    Returns:
        str: Formatted Facebook Ads section
    """
    if daily_df.empty:
        return ""

    # Filter for target date
    daily_df = daily_df.copy()
    daily_df['date_only'] = pd.to_datetime(daily_df['date']).dt.date
    t1_data = daily_df[daily_df['date_only'] == target_date]

    # Get comparison period data
    week_ago = target_date - timedelta(days=compare_days-1)
    period_data = daily_df[(daily_df['date_only'] >= week_ago) & (daily_df['date_only'] <= target_date)]

    # Expected agents from P-tab config
    expected_agents = [t['agent'] for t in AGENT_PERFORMANCE_TABS]

    if t1_data.empty:
        report = "💰 <b>FACEBOOK ADS (T+1)</b>\n"
        report += "<b>⚠️ NO DATA</b>\n<pre>"
        for agent in expected_agents:
            report += f"{agent}: No data for this date\n"
        report += "</pre>\n\n"
        return report

    # Aggregate T+1 totals
    t1_totals = {
        'cost': t1_data['cost'].sum(),
        'impressions': t1_data['impressions'].sum(),
        'clicks': t1_data['clicks'].sum(),
        'register': t1_data['register'].sum(),
        'ftd': t1_data['ftd'].sum(),
    }

    # Calculate derived metrics for T+1
    t1_totals['ctr'] = (t1_totals['clicks'] / t1_totals['impressions'] * 100) if t1_totals['impressions'] > 0 else 0
    t1_totals['cpr'] = (t1_totals['cost'] / t1_totals['register']) if t1_totals['register'] > 0 else 0
    t1_totals['cpftd'] = (t1_totals['cost'] / t1_totals['ftd']) if t1_totals['ftd'] > 0 else 0

    # Calculate 7-day averages
    avg_totals = {}
    if not period_data.empty:
        daily_agg = period_data.groupby('date_only').agg({
            'cost': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'register': 'sum',
            'ftd': 'sum'
        }).reset_index()

        num_days = len(daily_agg)
        avg_totals = {
            'cost': daily_agg['cost'].sum() / num_days if num_days > 0 else 0,
            'impressions': daily_agg['impressions'].sum() / num_days if num_days > 0 else 0,
            'clicks': daily_agg['clicks'].sum() / num_days if num_days > 0 else 0,
            'register': daily_agg['register'].sum() / num_days if num_days > 0 else 0,
            'ftd': daily_agg['ftd'].sum() / num_days if num_days > 0 else 0,
        }

    # Build report section
    report = "💰 <b>FACEBOOK ADS (T+1)</b>\n"
    report += "<pre>"
    report += f"{'Metric':<12}{'T+1':>12}{'7D Avg':>12}{'Diff':>10}\n"
    report += "-" * 46 + "\n"

    # Cost
    t1_cost = t1_totals['cost']
    avg_cost = avg_totals.get('cost', 0)
    diff_cost = t1_cost - avg_cost
    diff_str = f"+${diff_cost:,.0f}" if diff_cost >= 0 else f"-${abs(diff_cost):,.0f}"
    report += f"{'Cost':<12}${t1_cost:>10,.2f}${avg_cost:>10,.2f}{diff_str:>10}\n"

    # Impressions
    t1_impr = int(t1_totals['impressions'])
    avg_impr = avg_totals.get('impressions', 0)
    diff_impr = t1_impr - avg_impr
    diff_str = f"+{diff_impr:,.0f}" if diff_impr >= 0 else f"{diff_impr:,.0f}"
    report += f"{'Impressions':<12}{t1_impr:>12,}{avg_impr:>12,.0f}{diff_str:>10}\n"

    # Clicks
    t1_clicks = int(t1_totals['clicks'])
    avg_clicks = avg_totals.get('clicks', 0)
    diff_clicks = t1_clicks - avg_clicks
    diff_str = f"+{diff_clicks:,.0f}" if diff_clicks >= 0 else f"{diff_clicks:,.0f}"
    report += f"{'Clicks':<12}{t1_clicks:>12,}{avg_clicks:>12,.0f}{diff_str:>10}\n"

    # CTR
    avg_ctr = (avg_totals.get('clicks', 0) / avg_totals.get('impressions', 1) * 100) if avg_totals.get('impressions', 0) > 0 else 0
    diff_ctr = t1_totals['ctr'] - avg_ctr
    diff_str = f"+{diff_ctr:.2f}%" if diff_ctr >= 0 else f"{diff_ctr:.2f}%"
    report += f"{'CTR':<12}{t1_totals['ctr']:>11.2f}%{avg_ctr:>11.2f}%{diff_str:>10}\n"

    # Register
    t1_reg = int(t1_totals['register'])
    avg_reg = avg_totals.get('register', 0)
    diff_reg = t1_reg - avg_reg
    diff_str = f"+{diff_reg:,.0f}" if diff_reg >= 0 else f"{diff_reg:,.0f}"
    report += f"{'Register':<12}{t1_reg:>12,}{avg_reg:>12,.0f}{diff_str:>10}\n"

    # FTD (First Time Deposit)
    t1_ftd = int(t1_totals['ftd'])
    avg_ftd = avg_totals.get('ftd', 0)
    diff_ftd = t1_ftd - avg_ftd
    diff_str = f"+{diff_ftd:,.0f}" if diff_ftd >= 0 else f"{diff_ftd:,.0f}"
    report += f"{'FTD':<12}{t1_ftd:>12,}{avg_ftd:>12,.0f}{diff_str:>10}\n"

    # Conversion Rate (FTD / Register)
    t1_conv = (t1_ftd / t1_reg * 100) if t1_reg > 0 else 0
    avg_conv = (avg_ftd / avg_reg * 100) if avg_reg > 0 else 0
    diff_conv = t1_conv - avg_conv
    diff_str = f"+{diff_conv:.1f}%" if diff_conv >= 0 else f"{diff_conv:.1f}%"
    report += f"{'Conv Rate':<12}{t1_conv:>11.1f}%{avg_conv:>11.1f}%{diff_str:>10}\n"

    # Cost metrics (CPR and Cost/FTD only)
    report += "-" * 46 + "\n"
    report += f"{'CPR':<12}${t1_totals['cpr']:>10,.2f}\n"
    report += f"{'Cost/FTD':<12}${t1_totals['cpftd']:>10,.2f}\n"
    report += "</pre>\n\n"

    # Group by agent and calculate metrics
    agent_data = t1_data.groupby('agent').agg({
        'cost': 'sum',
        'register': 'sum',
        'ftd': 'sum',
        'impressions': 'sum',
        'clicks': 'sum'
    }).reset_index()

    # Calculate derived metrics and tier
    agent_data['cpr'] = agent_data.apply(
        lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1
    )
    agent_data['cpftd'] = agent_data.apply(
        lambda x: x['cost'] / x['ftd'] if x['ftd'] > 0 else 0, axis=1
    )
    agent_data['tier'] = agent_data.apply(
        lambda x: classify_performance_tier(x['cost'], x['ftd']), axis=1
    )

    # Define tier info
    tiers = [
        ('top', '🥇 TOP PERFORMERS', 'FTD >= 50 or Cost >= $1,000'),
        ('mid', '🥈 MID PERFORMERS', 'FTD >= 20 or Cost >= $400'),
        ('developing', '🥉 DEVELOPING', 'Below thresholds'),
    ]

    for tier_key, tier_name, tier_desc in tiers:
        tier_agents = agent_data[agent_data['tier'] == tier_key].sort_values('ftd', ascending=False)

        if not tier_agents.empty:
            report += f"<b>{tier_name}</b>\n"
            report += f"<i>{tier_desc}</i>\n<pre>"

            for _, row in tier_agents.iterrows():
                name = row['agent']
                cost = row['cost']
                reg = int(row['register'])
                ftd = int(row['ftd'])
                cpr = row['cpr']
                cpftd = row['cpftd']
                conv_rate = (ftd / reg * 100) if reg > 0 else 0

                report += f"{name}\n"
                report += f"  Cost: ${cost:,.2f} | Reg: {reg} | FTD: {ftd} | Conv: {conv_rate:.1f}%\n"
                if cpr > 0:
                    report += f"  CPR: ${cpr:.2f}"
                else:
                    report += f"  CPR: -"
                if cpftd > 0:
                    report += f" | Cost/FTD: ${cpftd:.2f}\n"
                else:
                    report += f" | Cost/FTD: -\n"

            # Tier subtotal
            tier_cost = tier_agents['cost'].sum()
            tier_reg = int(tier_agents['register'].sum())
            tier_ftd = int(tier_agents['ftd'].sum())
            tier_conv = (tier_ftd / tier_reg * 100) if tier_reg > 0 else 0

            report += "-" * 40 + "\n"
            report += f"Subtotal: ${tier_cost:,.2f} | Reg: {tier_reg} | FTD: {tier_ftd} | Conv: {tier_conv:.1f}%\n"
            report += "</pre>\n\n"

    # Check for agents with no data
    agents_with_data = set(agent_data['agent'].values)
    no_data_agents = [a for a in expected_agents if a not in agents_with_data]

    if no_data_agents:
        report += "<b>⚠️ NO DATA</b>\n<pre>"
        for agent in no_data_agents:
            report += f"{agent}: No data for this date\n"
        report += "</pre>\n\n"

    # Grand total
    grand_conv = (t1_totals['ftd'] / t1_totals['register'] * 100) if t1_totals['register'] > 0 else 0
    report += "<b>GRAND TOTAL:</b>\n<pre>"
    report += f"Cost: ${t1_totals['cost']:,.2f} | Reg: {int(t1_totals['register'])} | FTD: {int(t1_totals['ftd'])} | Conv: {grand_conv:.1f}%\n"
    report += f"CPR: ${t1_totals['cpr']:.2f} | Cost/FTD: ${t1_totals['cpftd']:.2f}\n"
    report += "</pre>\n\n"

    return report


def generate_monthly_overview(monthly_df):
    """
    Generate monthly overview summary from P-tab monthly data.

    Args:
        monthly_df: DataFrame from P-tab monthly data (columns: agent, month, cost, register, ftd, conv_rate, cpr, cpd, etc.)

    Returns:
        str: Formatted monthly overview section
    """
    if monthly_df is None or monthly_df.empty:
        return ""

    df = monthly_df.copy()

    # Get latest month
    latest_month = df['month'].max()
    month_data = df[df['month'] == latest_month]

    if month_data.empty:
        return ""

    expected_agents = [t['agent'] for t in AGENT_PERFORMANCE_TABS]

    report = f"📅 <b>MONTHLY OVERVIEW ({latest_month})</b>\n<pre>"
    report += f"{'Agent':<8}{'Cost':>10}{'Reg':>6}{'FTD':>5}{'Conv':>7}{'CPR':>8}{'CPFTD':>8}\n"
    report += "-" * 52 + "\n"

    total_cost = 0
    total_reg = 0
    total_ftd = 0

    for agent in expected_agents:
        agent_data = month_data[month_data['agent'] == agent]
        if agent_data.empty:
            report += f"{agent:<8} No data available\n"
            continue

        cost = agent_data['cost'].sum()
        reg = int(agent_data['register'].sum())
        ftd = int(agent_data['ftd'].sum())
        conv = (ftd / reg * 100) if reg > 0 else 0
        cpr = (cost / reg) if reg > 0 else 0
        cpftd = (cost / ftd) if ftd > 0 else 0

        total_cost += cost
        total_reg += reg
        total_ftd += ftd

        report += f"{agent:<8}${cost:>8,.0f}{reg:>6}{ftd:>5}{conv:>6.1f}%${cpr:>6,.0f}${cpftd:>6,.0f}\n"

    total_conv = (total_ftd / total_reg * 100) if total_reg > 0 else 0
    total_cpr = (total_cost / total_reg) if total_reg > 0 else 0
    total_cpftd = (total_cost / total_ftd) if total_ftd > 0 else 0

    report += "-" * 52 + "\n"
    report += f"{'TOTAL':<8}${total_cost:>8,.0f}{total_reg:>6}{total_ftd:>5}{total_conv:>6.1f}%${total_cpr:>6,.0f}${total_cpftd:>6,.0f}\n"
    report += "</pre>\n\n"

    return report


def generate_by_campaign_section(ad_accounts_df, target_date):
    """
    Generate By Campaign section from P-tab ad account data.

    Args:
        ad_accounts_df: DataFrame from load_ptab_data()['ad_accounts']
        target_date: Date to report on

    Returns:
        str: Formatted By Campaign section
    """
    if ad_accounts_df is None or ad_accounts_df.empty:
        return ""

    df = ad_accounts_df.copy()
    df['date_only'] = pd.to_datetime(df['date']).dt.date
    t1_data = df[df['date_only'] == target_date]

    if t1_data.empty:
        return ""

    report = "📊 <b>BY CAMPAIGN (T+1)</b>\n"

    for agent in sorted(t1_data['agent'].unique()):
        agent_data = t1_data[t1_data['agent'] == agent].sort_values('cost', ascending=False)
        total_cost = agent_data['cost'].sum()

        report += f"\n<b>{agent}</b> (${total_cost:,.2f})\n<pre>"
        for _, row in agent_data.iterrows():
            acct = row['ad_account']
            cost = row['cost']
            impr = int(row['impressions'])
            clicks = int(row['clicks'])
            ctr = row['ctr']
            acct_short = acct[:25] + '..' if len(acct) > 25 else acct
            report += f"  {acct_short}\n"
            report += f"    ${cost:,.2f} | {impr:,} imp | {clicks:,} clk | {ctr:.1f}%\n"
        report += "</pre>"

    report += "\n\n"
    return report


def generate_t1_report(all_ads, all_creative, all_sms, all_content, daily_df=None):
    """
    Generate T+1 report (yesterday) with comparison to 7-day average.
    Uses P-tab daily data for FB Ads section.

    Returns:
        str: Formatted T+1 report
    """
    yesterday = datetime.now().date() - timedelta(days=1)

    # Build report - Facebook Ads only (from P-tab data)
    report = f"📊 <b>Advertiser KPI Report</b> - {yesterday.strftime('%b %d, %Y')}\n"
    report += f"<i>vs Last 7 Days Average</i>\n\n"

    # Facebook Ads Section from P-tab data
    if daily_df is not None and not daily_df.empty:
        fb_section = generate_facebook_ads_section(daily_df, yesterday)
        report += fb_section
    else:
        report += "⚠️ No P-tab data available for this date.\n"

    return report


def generate_weekly_report(all_ads, all_creative, all_sms, all_content):
    """
    Generate weekly report (last 7 days summary)

    Returns:
        str: Formatted weekly report
    """
    today = datetime.now().date()
    week_ago = today - timedelta(days=6)

    # Get weekly data
    ads_df, creative_df, sms_df, _ = get_data_for_date_range(
        all_ads, all_creative, all_sms, all_content,
        week_ago, today
    )

    # Content (no date filter)
    content_df = pd.concat(all_content, ignore_index=True) if all_content else pd.DataFrame()

    report = f"📊 <b>Advertiser KPI Weekly Report</b>\n"
    report += f"<i>{week_ago.strftime('%b %d')} - {today.strftime('%b %d, %Y')}</i>\n\n"

    # Creative Weekly Summary
    report += "🎨 <b>CREATIVE (7 Days)</b>\n<pre>"
    report += f"{'Name':<10}{'Total':>7}{'Daily':>7}\n"
    report += "-" * 24 + "\n"

    total_creative = 0
    agent_creative = {}

    if not creative_df.empty and 'agent_name' in creative_df.columns:
        for agent in sorted(creative_df['agent_name'].unique()):
            agent_data = creative_df[creative_df['agent_name'] == agent]
            # Group by date to avoid double-counting (creative_total is daily total)
            if 'creative_total' in agent_data.columns and 'date' in agent_data.columns:
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['creative_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            agent_creative[agent] = total
            total_creative += total
            daily = total / 7
            report += f"{agent:<10}{total:>7}{daily:>7.1f}\n"

    report += "-" * 24 + "\n"
    report += f"{'TOTAL':<10}{total_creative:>7}{total_creative/7:>7.1f}\n"
    report += "</pre>\n\n"

    # SMS Weekly Summary
    report += "📱 <b>SMS (7 Days)</b>\n<pre>"
    report += f"{'Name':<10}{'Total':>7}{'Daily':>7}\n"
    report += "-" * 24 + "\n"

    total_sms = 0
    agent_sms = {}

    if not sms_df.empty and 'agent_name' in sms_df.columns:
        for agent in sorted(sms_df['agent_name'].unique()):
            agent_data = sms_df[sms_df['agent_name'] == agent]
            # Group by date to avoid double-counting (sms_total is daily total)
            if 'sms_total' in agent_data.columns and 'date' in agent_data.columns:
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['sms_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            agent_sms[agent] = total
            total_sms += total
            daily = total / 7
            report += f"{agent:<10}{total:>7}{daily:>7.1f}\n"

    report += "-" * 24 + "\n"
    report += f"{'TOTAL':<10}{total_sms:>7}{total_sms/7:>7.1f}\n"
    report += "</pre>\n\n"

    # Copywriting Summary - only Primary Text entries
    if not content_df.empty:
        # Filter for Primary Text only
        if 'content_type' in content_df.columns:
            primary_df = content_df[content_df['content_type'] == 'Primary Text']
        else:
            primary_df = content_df

        if not primary_df.empty:
            total_primary = len(primary_df)

            report += "📝 <b>COPYWRITING (Primary Text)</b>\n"
            report += f"Total: <b>{total_primary}</b>\n\n"

            report += "<pre>"
            report += f"{'Name':<10}{'Posts':>6}\n"
            report += "-" * 16 + "\n"
            for agent in sorted(primary_df['agent_name'].unique()):
                count = len(primary_df[primary_df['agent_name'] == agent])
                report += f"{agent:<10}{count:>6}\n"
            report += "</pre>"

    return report


def check_running_ads(ads_list, target_date=None):
    """
    Check if there are running ads for the target date
    """
    if target_date is None:
        target_date = datetime.now().date()

    if not ads_list:
        return False, pd.DataFrame()

    ads_df = pd.concat(ads_list, ignore_index=True)

    if 'date' in ads_df.columns:
        ads_df['date_only'] = pd.to_datetime(ads_df['date']).dt.date
        target_ads = ads_df[ads_df['date_only'] == target_date]

        if 'total_ad' in target_ads.columns:
            total_ads = target_ads['total_ad'].sum()
            return total_ads > 0, target_ads

    return False, pd.DataFrame()


def generate_ads_report(ads_df, report_date):
    """Generate report when ads are running"""
    report = f"📊 <b>Advertiser KPI Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
    report += "🎯 <b>RUNNING ADS SUMMARY</b>\n"
    report += "<pre>"
    report += f"{'Name':<10}{'Ads':>6}{'Impr':>10}{'Clicks':>8}{'CTR%':>7}\n"
    report += "-" * 41 + "\n"

    total_ads_sum = 0
    total_impressions = 0
    total_clicks = 0

    for agent_name in sorted(ads_df['agent_name'].unique()):
        agent_data = ads_df[ads_df['agent_name'] == agent_name]

        ads_count = int(agent_data['total_ad'].sum()) if 'total_ad' in agent_data.columns else 0
        impressions = int(agent_data['impressions'].sum()) if 'impressions' in agent_data.columns else 0
        clicks = int(agent_data['clicks'].sum()) if 'clicks' in agent_data.columns else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0

        total_ads_sum += ads_count
        total_impressions += impressions
        total_clicks += clicks

        report += f"{agent_name:<10}{ads_count:>6}{impressions:>10,}{clicks:>8,}{ctr:>6.1f}%\n"

    report += "-" * 41 + "\n"

    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    report += f"{'TOTAL':<10}{total_ads_sum:>6}{total_impressions:>10,}{total_clicks:>8,}{overall_ctr:>6.1f}%\n"
    report += "</pre>\n"

    return report


def generate_no_ads_report(creative_list, sms_list, content_list, report_date):
    """Generate report when no ads are running"""
    report = f"📊 <b>Advertiser KPI Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
    report += "⚠️ <b>No Running Ads Today</b>\n\n"

    # Creative Summary
    if creative_list:
        creative_df = pd.concat(creative_list, ignore_index=True)
        report += "🎨 <b>CREATIVE</b>\n<pre>"
        report += f"{'Name':<10}{'Total':>6}  {'Types'}\n"
        report += "-" * 35 + "\n"

        total_creative = 0
        for agent in sorted(creative_df['agent_name'].unique()):
            agent_data = creative_df[creative_df['agent_name'] == agent]
            # Group by date to avoid double-counting (creative_total is daily total)
            if 'creative_total' in agent_data.columns and 'date' in agent_data.columns:
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['creative_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            total_creative += total

            types_list = agent_data['creative_type'].unique() if 'creative_type' in agent_data.columns else []
            types = ', '.join([str(t) for t in types_list[:2] if pd.notna(t)])
            report += f"{agent:<10}{total:>6}  {types}\n"

        report += "-" * 35 + "\n"
        report += f"{'TOTAL':<10}{total_creative:>6}\n"
        report += "</pre>\n\n"

    # SMS Summary
    if sms_list:
        sms_df = pd.concat(sms_list, ignore_index=True)
        report += "📱 <b>SMS</b>\n<pre>"
        report += f"{'Name':<10}{'Total':>6}  {'Top Type'}\n"
        report += "-" * 40 + "\n"

        total_sms = 0
        for agent in sorted(sms_df['agent_name'].unique()):
            agent_data = sms_df[sms_df['agent_name'] == agent]
            # Group by date to avoid double-counting (sms_total is daily total)
            if 'sms_total' in agent_data.columns and 'date' in agent_data.columns:
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['sms_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            total_sms += total

            if 'sms_type' in agent_data.columns:
                top_type = agent_data['sms_type'].mode().iloc[0] if len(agent_data['sms_type'].mode()) > 0 else ''
                top_type = str(top_type)[:20] + '...' if len(str(top_type)) > 20 else str(top_type)
            else:
                top_type = ''

            report += f"{agent:<10}{total:>6}  {top_type}\n"

        report += "-" * 40 + "\n"
        report += f"{'TOTAL':<10}{total_sms:>6}\n"
        report += "</pre>\n\n"

    # Copywriting Summary - only Primary Text entries
    if content_list:
        content_df = pd.concat(content_list, ignore_index=True)

        # Filter for Primary Text only
        if 'content_type' in content_df.columns:
            primary_df = content_df[content_df['content_type'] == 'Primary Text']
        else:
            primary_df = content_df

        if not primary_df.empty:
            total_primary = len(primary_df)

            report += "📝 <b>COPYWRITING (Primary Text)</b>\n"
            report += f"Total: <b>{total_primary}</b>\n\n"

            report += "<pre>"
            report += f"{'Name':<10}{'Posts':>6}\n"
            report += "-" * 16 + "\n"
            for agent in sorted(primary_df['agent_name'].unique()):
                agent_count = len(primary_df[primary_df['agent_name'] == agent])
                report += f"{agent:<10}{agent_count:>6}\n"
            report += "</pre>"

    return report


def generate_ab_testing_section(ab_data):
    """Generate A/B Testing Progress section for Telegram report.

    Args:
        ab_data: dict from load_ab_testing_data()

    Returns:
        str: HTML-formatted section or None on error
    """
    try:
        counts = count_ab_testing(ab_data)
        if not counts:
            return None

        # Sort by published_ad descending
        sorted_agents = sorted(counts.items(), key=lambda x: x[1].get('published_ad', 0), reverse=True)

        msg = '\U0001f9ea <b>A/B Testing Progress</b>\n\n<pre>\n'
        msg += f'{"Agent":<10} {"Texts":>5}  {"Published":>9}  {"Score":>5}\n'
        msg += '\u2500' * 38 + '\n'

        total_texts = 0
        total_published = 0

        for agent, info in sorted_agents:
            texts = info.get('primary_text', 0)
            published = info.get('published_ad', 0)
            score = score_ab_testing(published)
            total_texts += texts
            total_published += published

            t_str = str(texts) if texts > 0 else '-'
            p_str = str(published) if published > 0 else '-'
            msg += f'{agent.title():<10} {t_str:>5}  {p_str:>9}  {score}/4\n'

        msg += '\u2500' * 38 + '\n'
        msg += f'{"TOTAL":<10} {total_texts:>5}  {total_published:>9}\n'
        msg += '</pre>\n\n'
        msg += '<b>Scoring:</b> 4 (\u226520) | 3 (11-19) | 2 (6-10) | 1 (&lt;6)'

        return msg
    except Exception as e:
        print(f"[ERROR] generate_ab_testing_section: {e}")
        return None


def generate_account_dev_section(assets_df):
    """Generate Account Dev Progress section for Telegram report.

    Args:
        assets_df: DataFrame from load_created_assets_data()

    Returns:
        str: HTML-formatted section or None on error
    """
    try:
        counts = count_created_assets(assets_df)
        if not counts:
            return None

        # Sort by total_accounts descending
        sorted_agents = sorted(counts.items(), key=lambda x: x[1].get('total_accounts', 0), reverse=True)

        msg = '\U0001f3d7 <b>Account Dev Progress</b>\n\n<pre>\n'
        msg += f'{"Agent":<10} {"Gmail":>5}  {"FB Acct":>7}  {"Total":>5}  {"Score":>5}\n'
        msg += '\u2500' * 41 + '\n'

        total_gmail = 0
        total_fb = 0
        total_all = 0

        for agent, info in sorted_agents:
            gmail = info.get('gmail', 0)
            fb = info.get('fb_accounts', 0)
            total = info.get('total_accounts', 0)
            score = score_account_dev(total)
            total_gmail += gmail
            total_fb += fb
            total_all += total

            g_str = str(gmail) if gmail > 0 else '-'
            f_str = str(fb) if fb > 0 else '-'
            t_str = str(total) if total > 0 else '0'
            msg += f'{agent.title():<10} {g_str:>5}  {f_str:>7}  {t_str:>5}  {score}/4\n'

        msg += '\u2500' * 41 + '\n'
        msg += f'{"TOTAL":<10} {total_gmail:>5}  {total_fb:>7}  {total_all:>5}\n'
        msg += '</pre>\n\n'
        msg += '<b>Scoring:</b> 4 (\u22655) | 3 (3-4) | 2 (2) | 1 (&lt;2)'

        return msg
    except Exception as e:
        print(f"[ERROR] generate_account_dev_section: {e}")
        return None


def generate_executive_summary(daily_df, target_date):
    """
    Generate a clean, single-message executive summary (VIP Handler style).
    Includes overall KPIs with day-over-day delta + agent performance table.
    """
    if daily_df is None or daily_df.empty:
        return None

    df = daily_df.copy()
    df['date_only'] = pd.to_datetime(df['date']).dt.date
    t1 = df[df['date_only'] == target_date]

    if t1.empty:
        return None

    # Previous day for delta
    prev_date = target_date - timedelta(days=1)
    prev = df[df['date_only'] == prev_date]

    # 7-day average
    week_ago = target_date - timedelta(days=7)
    week_data = df[(df['date_only'] > week_ago) & (df['date_only'] <= target_date)]
    n_days = week_data['date_only'].nunique()

    # Totals
    def _totals(data):
        cost = data['cost'].sum()
        reg = int(data['register'].sum())
        ftd = int(data['ftd'].sum())
        impr = int(data['impressions'].sum())
        clicks = int(data['clicks'].sum())
        ctr = (clicks / impr * 100) if impr > 0 else 0
        conv = (ftd / reg * 100) if reg > 0 else 0
        cpa = (cost / ftd) if ftd > 0 else 0
        cpr = (cost / reg) if reg > 0 else 0
        return {'cost': cost, 'register': reg, 'ftd': ftd, 'impressions': impr,
                'clicks': clicks, 'ctr': ctr, 'conv': conv, 'cpa': cpa, 'cpr': cpr}

    curr = _totals(t1)
    prev_t = _totals(prev) if not prev.empty else None

    def _delta(val, prev_val, fmt='num', inverse=False):
        if prev_val is None or prev_val == 0:
            return ""
        pct = (val - prev_val) / abs(prev_val) * 100
        if abs(pct) < 0.5:
            return ""
        sign = "+" if pct > 0 else ""
        return f" ({sign}{pct:.0f}%)"

    # Build report
    lines = []
    lines.append(f"<b>Advertiser KPI Dashboard</b>")
    lines.append(f"<b>Daily Report - {target_date.strftime('%B %d, %Y')}</b>")
    lines.append("")

    # Executive Summary
    lines.append("<b>Executive Summary</b>")
    p = prev_t
    lines.append(f"Cost: <b>${curr['cost']:,.2f}</b>{_delta(curr['cost'], p['cost'] if p else 0)}")
    lines.append(f"Register: <b>{curr['register']:,}</b>{_delta(curr['register'], p['register'] if p else 0)} | FTD: <b>{curr['ftd']:,}</b>{_delta(curr['ftd'], p['ftd'] if p else 0)}")
    lines.append(f"CPA: <b>${curr['cpa']:,.2f}</b>{_delta(curr['cpa'], p['cpa'] if p else 0, inverse=True)} | Conv: <b>{curr['conv']:.1f}%</b>{_delta(curr['conv'], p['conv'] if p else 0)}")
    lines.append(f"CTR: <b>{curr['ctr']:.2f}%</b>{_delta(curr['ctr'], p['ctr'] if p else 0)} | CPR: <b>${curr['cpr']:,.2f}</b>{_delta(curr['cpr'], p['cpr'] if p else 0, inverse=True)}")

    if n_days > 1:
        avg_cost = week_data.groupby('date_only')['cost'].sum().mean()
        avg_ftd = week_data.groupby('date_only')['ftd'].sum().mean()
        lines.append(f"<i>7D Avg: ${avg_cost:,.0f}/day | {avg_ftd:.0f} FTD/day</i>")

    # Agent Performance Table
    lines.append("")
    lines.append("<b>Agent Performance</b>")

    agent_t1 = t1.groupby('agent').agg(
        cost=('cost', 'sum'), register=('register', 'sum'),
        ftd=('ftd', 'sum'), clicks=('clicks', 'sum'),
        impressions=('impressions', 'sum')
    ).reset_index()

    agent_prev = None
    if not prev.empty:
        agent_prev = prev.groupby('agent').agg(
            cost=('cost', 'sum'), ftd=('ftd', 'sum')
        ).reset_index().set_index('agent')

    agent_t1['conv'] = agent_t1.apply(lambda r: r['ftd'] / r['register'] * 100 if r['register'] > 0 else 0, axis=1)
    agent_t1['cpa'] = agent_t1.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    agent_t1 = agent_t1.sort_values('ftd', ascending=False)

    table = []
    table.append(f"{'Agent':<8} {'Cost':>8} {'Reg':>5} {'FTD':>4} {'Conv':>6} {'CPA':>7} {'Chg':>5}")
    table.append('─' * 48)

    expected_agents = [t['agent'] for t in AGENT_PERFORMANCE_TABS]
    for _, row in agent_t1.iterrows():
        cost_s = f"${row['cost']:,.0f}"
        conv_s = f"{row['conv']:.1f}%"
        cpa_s = f"${row['cpa']:,.0f}" if row['cpa'] > 0 else "-"
        chg = ""
        if agent_prev is not None and row['agent'] in agent_prev.index:
            prev_ftd = agent_prev.loc[row['agent'], 'ftd']
            diff = int(row['ftd'] - prev_ftd)
            chg = f"+{diff}" if diff > 0 else str(diff)
        table.append(f"{row['agent']:<8} {cost_s:>8} {int(row['register']):>5} {int(row['ftd']):>4} {conv_s:>6} {cpa_s:>7} {chg:>5}")

    # No data agents
    agents_with_data = set(agent_t1['agent'].values)
    no_data = [a for a in expected_agents if a not in agents_with_data]
    for a in no_data:
        table.append(f"{a:<8}  No data")

    # Grand total line
    table.append('─' * 48)
    total_conv = f"{curr['conv']:.1f}%"
    total_cpa = f"${curr['cpa']:,.0f}" if curr['cpa'] > 0 else "-"
    table.append(f"{'TOTAL':<8} ${curr['cost']:>7,.0f} {curr['register']:>5} {curr['ftd']:>4} {total_conv:>6} {total_cpa:>7}")

    lines.append("<pre>" + "\n".join(table) + "</pre>")

    return "\n".join(lines)


def generate_operations_summary(reporting_data=None, ab_data=None, assets_df=None):
    """
    Generate a clean operations summary combining reporting accuracy,
    A/B testing, and account dev into one message.
    """
    lines = []
    lines.append("<b>Operations Dashboard</b>")
    lines.append("")

    has_content = False

    # Reporting Accuracy
    if reporting_data:
        has_content = True
        agents = sorted(reporting_data.items(), key=lambda x: x[1].get('avg_minute', 99))
        lines.append("<b>Reporting Accuracy</b>")
        tbl = []
        tbl.append(f"{'Agent':<10} {'Rpts':>4} {'Avg':>5} {'Score':>5}")
        tbl.append('─' * 28)
        for agent, info in agents:
            count = info.get('report_count', 0)
            avg = info.get('avg_minute', 0)
            score = info.get('score', 0)
            tbl.append(f"{agent:<10} {count:>4} {avg:>4.0f}m {score:>3}/4")
        lines.append("<pre>" + "\n".join(tbl) + "</pre>")
        lines.append("")

    # A/B Testing
    if ab_data:
        counts = count_ab_testing(ab_data)
        if counts:
            has_content = True
            sorted_agents = sorted(counts.items(), key=lambda x: x[1].get('published_ad', 0), reverse=True)
            lines.append("<b>A/B Testing</b>")
            tbl = []
            tbl.append(f"{'Agent':<10} {'Texts':>5} {'Pub':>4} {'Score':>5}")
            tbl.append('─' * 28)
            for agent, info in sorted_agents:
                texts = info.get('primary_text', 0)
                published = info.get('published_ad', 0)
                score = score_ab_testing(published)
                t_s = str(texts) if texts > 0 else '-'
                p_s = str(published) if published > 0 else '-'
                tbl.append(f"{agent.title():<10} {t_s:>5} {p_s:>4} {score:>3}/4")
            lines.append("<pre>" + "\n".join(tbl) + "</pre>")
            lines.append("")

    # Account Dev
    if assets_df is not None and not assets_df.empty:
        counts = count_created_assets(assets_df)
        if counts:
            has_content = True
            sorted_agents = sorted(counts.items(), key=lambda x: x[1].get('total_accounts', 0), reverse=True)
            lines.append("<b>Account Dev</b>")
            tbl = []
            tbl.append(f"{'Agent':<10} {'Gmail':>5} {'FB':>4} {'Tot':>4} {'Score':>5}")
            tbl.append('─' * 32)
            for agent, info in sorted_agents:
                gmail = info.get('gmail', 0)
                fb = info.get('fb_accounts', 0)
                total = info.get('total_accounts', 0)
                score = score_account_dev(total)
                tbl.append(f"{agent.title():<10} {gmail:>5} {fb:>4} {total:>4} {score:>3}/4")
            lines.append("<pre>" + "\n".join(tbl) + "</pre>")
            lines.append("")

    if not has_content:
        return None

    lines.append("<a href='https://ads-monitoring.streamlit.app'>View Dashboard</a>")

    return "\n".join(lines)


def generate_daily_report(report_date=None, send_to_telegram=True):
    """Generate and optionally send daily report using P-tab data only"""
    if report_date is None:
        report_date = datetime.now().date()

    print(f"Generating report for {report_date}...")

    # Load P-tab data (daily, monthly, ad_accounts)
    ptab_data = load_ptab_data()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
    monthly_df = ptab_data.get('monthly', pd.DataFrame()) if ptab_data else pd.DataFrame()
    ad_accounts_df = ptab_data.get('ad_accounts', pd.DataFrame()) if ptab_data else pd.DataFrame()

    report = f"📊 <b>Advertiser KPI Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"

    if not daily_df.empty:
        report += generate_monthly_overview(monthly_df)
        fb_section = generate_facebook_ads_section(daily_df, report_date)
        if fb_section:
            report += fb_section
        else:
            report += "⚠️ No P-tab data for this date.\n"
    else:
        report += "⚠️ No P-tab data available.\n"

    # By Campaign section
    if not ad_accounts_df.empty:
        report += generate_by_campaign_section(ad_accounts_df, report_date)

    if send_to_telegram:
        try:
            reporter = TelegramReporter()
            result = reporter.send_message(report)
            print("[OK] Report sent to Telegram successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to send to Telegram: {e}")
            raise

    return report


def send_t1_report():
    """Send T+1 report (yesterday with 7-day avg comparison) using P-tab data"""
    print("Generating T+1 report...")

    # Load agent data (for creative/SMS sections)
    all_ads, all_creative, all_sms, all_content = load_all_agent_data()

    # Load P-tab data
    print("Loading P-tab data...")
    ptab_data = load_ptab_data()
    daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
    if not daily_df.empty:
        print(f"Loaded {len(daily_df)} rows of P-tab daily data")
    else:
        print("No P-tab daily data loaded")

    report = generate_t1_report(all_ads, all_creative, all_sms, all_content, daily_df)

    try:
        reporter = TelegramReporter()
        result = reporter.send_message(report)
        print("[OK] T+1 Report sent to Telegram successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to send to Telegram: {e}")
        raise

    return report


def send_weekly_report():
    """Send weekly report (last 7 days summary)"""
    print("Generating weekly report...")

    all_ads, all_creative, all_sms, all_content = load_all_agent_data()
    report = generate_weekly_report(all_ads, all_creative, all_sms, all_content)

    try:
        reporter = TelegramReporter()
        result = reporter.send_message(report)
        print("[OK] Weekly Report sent to Telegram successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to send to Telegram: {e}")
        raise

    return report


def preview_report(report_date=None):
    """Generate report preview without sending to Telegram"""
    return generate_daily_report(report_date=report_date, send_to_telegram=False)


if __name__ == "__main__":
    print("=" * 50)
    print("Advertiser KPI Report Generator")
    print("=" * 50)
    report = preview_report()
    print("\n" + report)
