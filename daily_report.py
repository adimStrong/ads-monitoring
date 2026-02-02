"""
Daily Report Generator for BINGO365 Monitoring
Generates and sends daily reports to Telegram
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import load_agent_performance_data, load_agent_content_data, load_indian_promotion_content, load_facebook_ads_data
from config import AGENTS
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


def classify_performance_tier(spend, ftd):
    """
    Classify a person into a performance tier based on spend and FTD.

    Tiers:
    - Top Performers: FTD >= 50 OR Spend >= $1,000
    - Mid Performers: FTD >= 20 OR Spend >= $400
    - Developing: Below mid tier thresholds
    """
    if ftd >= 50 or spend >= 1000:
        return 'top'
    elif ftd >= 20 or spend >= 400:
        return 'mid'
    else:
        return 'developing'


def generate_facebook_ads_section(fb_ads_df, target_date, compare_days=7):
    """
    Generate Facebook Ads performance section for the report.
    Uses Performance Tier Grouping (Top/Mid/Developing) instead of BM grouping.

    Args:
        fb_ads_df: DataFrame with Facebook Ads data
        target_date: The date to report on (T+1)
        compare_days: Number of days for average comparison

    Returns:
        str: Formatted Facebook Ads section
    """
    if fb_ads_df.empty:
        return ""

    # Filter for target date
    fb_ads_df['date_only'] = pd.to_datetime(fb_ads_df['date']).dt.date
    t1_data = fb_ads_df[fb_ads_df['date_only'] == target_date]

    # Get comparison period data
    week_ago = target_date - timedelta(days=compare_days-1)
    period_data = fb_ads_df[(fb_ads_df['date_only'] >= week_ago) & (fb_ads_df['date_only'] <= target_date)]

    if t1_data.empty:
        return ""

    # Aggregate T+1 totals
    t1_totals = {
        'spend': t1_data['spend'].sum(),
        'impressions': t1_data['impressions'].sum(),
        'clicks': t1_data['clicks'].sum(),
        'reach': t1_data['reach'].sum(),
        'register': t1_data['register'].sum(),
        'result_ftd': t1_data['result_ftd'].sum(),
    }

    # Calculate derived metrics for T+1
    t1_totals['ctr'] = (t1_totals['clicks'] / t1_totals['impressions'] * 100) if t1_totals['impressions'] > 0 else 0
    t1_totals['cpc'] = (t1_totals['spend'] / t1_totals['clicks']) if t1_totals['clicks'] > 0 else 0
    t1_totals['cpm'] = (t1_totals['spend'] / t1_totals['impressions'] * 1000) if t1_totals['impressions'] > 0 else 0
    t1_totals['cpr'] = (t1_totals['spend'] / t1_totals['register']) if t1_totals['register'] > 0 else 0
    t1_totals['cpftd'] = (t1_totals['spend'] / t1_totals['result_ftd']) if t1_totals['result_ftd'] > 0 else 0

    # Calculate 7-day averages
    avg_totals = {}
    if not period_data.empty:
        daily_agg = period_data.groupby('date_only').agg({
            'spend': 'sum',
            'impressions': 'sum',
            'clicks': 'sum',
            'reach': 'sum',
            'register': 'sum',
            'result_ftd': 'sum'
        }).reset_index()

        num_days = len(daily_agg)
        avg_totals = {
            'spend': daily_agg['spend'].sum() / num_days if num_days > 0 else 0,
            'impressions': daily_agg['impressions'].sum() / num_days if num_days > 0 else 0,
            'clicks': daily_agg['clicks'].sum() / num_days if num_days > 0 else 0,
            'reach': daily_agg['reach'].sum() / num_days if num_days > 0 else 0,
            'register': daily_agg['register'].sum() / num_days if num_days > 0 else 0,
            'result_ftd': daily_agg['result_ftd'].sum() / num_days if num_days > 0 else 0,
        }

    # Build report section
    report = "💰 <b>FACEBOOK ADS (T+1)</b>\n"
    report += "<pre>"
    report += f"{'Metric':<12}{'T+1':>12}{'7D Avg':>12}{'Diff':>10}\n"
    report += "-" * 46 + "\n"

    # Spend
    t1_spend = t1_totals['spend']
    avg_spend = avg_totals.get('spend', 0)
    diff_spend = t1_spend - avg_spend
    diff_str = f"+${diff_spend:,.0f}" if diff_spend >= 0 else f"-${abs(diff_spend):,.0f}"
    report += f"{'Spend':<12}${t1_spend:>10,.2f}${avg_spend:>10,.2f}{diff_str:>10}\n"

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

    # FTD (First Time Deposit / Results)
    t1_ftd = int(t1_totals['result_ftd'])
    avg_ftd = avg_totals.get('result_ftd', 0)
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

    # Group by person and calculate metrics
    if 'person_name' in t1_data.columns:
        person_data = t1_data.groupby('person_name').agg({
            'spend': 'sum',
            'register': 'sum',
            'result_ftd': 'sum',
            'impressions': 'sum',
            'clicks': 'sum'
        }).reset_index()

        # Calculate derived metrics and tier
        person_data['cpr'] = person_data.apply(
            lambda x: x['spend'] / x['register'] if x['register'] > 0 else 0, axis=1
        )
        person_data['cpftd'] = person_data.apply(
            lambda x: x['spend'] / x['result_ftd'] if x['result_ftd'] > 0 else 0, axis=1
        )
        person_data['tier'] = person_data.apply(
            lambda x: classify_performance_tier(x['spend'], x['result_ftd']), axis=1
        )

        # Define tier info
        tiers = [
            ('top', '🥇 TOP PERFORMERS', 'FTD >= 50 or Spend >= $1,000'),
            ('mid', '🥈 MID PERFORMERS', 'FTD >= 20 or Spend >= $400'),
            ('developing', '🥉 DEVELOPING', 'Below thresholds'),
        ]

        for tier_key, tier_name, tier_desc in tiers:
            tier_persons = person_data[person_data['tier'] == tier_key].sort_values('result_ftd', ascending=False)

            if not tier_persons.empty:
                report += f"<b>{tier_name}</b>\n"
                report += f"<i>{tier_desc}</i>\n<pre>"

                for _, row in tier_persons.iterrows():
                    person_name = row['person_name']
                    spend = row['spend']
                    reg = int(row['register'])
                    ftd = int(row['result_ftd'])
                    cpr = row['cpr']
                    cpftd = row['cpftd']
                    conv_rate = (ftd / reg * 100) if reg > 0 else 0

                    report += f"{person_name}\n"
                    report += f"  Spend: ${spend:,.2f} | Reg: {reg} | FTD: {ftd} | Conv: {conv_rate:.1f}%\n"
                    if cpr > 0:
                        report += f"  CPR: ${cpr:.2f}"
                    else:
                        report += f"  CPR: -"
                    if cpftd > 0:
                        report += f" | Cost/FTD: ${cpftd:.2f}\n"
                    else:
                        report += f" | Cost/FTD: -\n"

                # Tier subtotal
                tier_spend = tier_persons['spend'].sum()
                tier_reg = int(tier_persons['register'].sum())
                tier_ftd = int(tier_persons['result_ftd'].sum())
                tier_conv = (tier_ftd / tier_reg * 100) if tier_reg > 0 else 0

                report += "-" * 40 + "\n"
                report += f"Subtotal: ${tier_spend:,.2f} | Reg: {tier_reg} | FTD: {tier_ftd} | Conv: {tier_conv:.1f}%\n"
                report += "</pre>\n\n"
    else:
        report += "<pre>No person data available</pre>\n"

    # Grand total
    grand_conv = (t1_totals['result_ftd'] / t1_totals['register'] * 100) if t1_totals['register'] > 0 else 0
    report += "<b>GRAND TOTAL:</b>\n<pre>"
    report += f"Spend: ${t1_totals['spend']:,.2f} | Reg: {int(t1_totals['register'])} | FTD: {int(t1_totals['result_ftd'])} | Conv: {grand_conv:.1f}%\n"
    report += f"CPR: ${t1_totals['cpr']:.2f} | Cost/FTD: ${t1_totals['cpftd']:.2f}\n"
    report += "</pre>\n\n"

    return report


def generate_t1_report(all_ads, all_creative, all_sms, all_content, fb_ads_df=None):
    """
    Generate T+1 report (yesterday) with comparison to 7-day average

    Returns:
        str: Formatted T+1 report
    """
    yesterday = datetime.now().date() - timedelta(days=1)
    week_ago = yesterday - timedelta(days=6)  # 7 days including yesterday

    # Get yesterday's data (T+1)
    _, creative_t1, sms_t1, content_t1 = get_data_for_date_range(
        all_ads, all_creative, all_sms, all_content,
        yesterday, yesterday
    )

    # Get last 7 days data (for average)
    _, creative_7d, sms_7d, content_7d = get_data_for_date_range(
        all_ads, all_creative, all_sms, all_content,
        week_ago, yesterday
    )

    # Use T+1 filtered content
    content_df = content_t1

    # Calculate T+1 stats
    t1_stats = calculate_agent_stats(creative_t1, sms_t1, pd.DataFrame())

    # Calculate 7-day totals and averages - group by date first to avoid double-counting
    avg_stats = {}
    if not creative_7d.empty and 'agent_name' in creative_7d.columns:
        for agent in creative_7d['agent_name'].unique():
            if agent not in avg_stats:
                avg_stats[agent] = {'creative': 0, 'sms': 0}
            agent_data = creative_7d[creative_7d['agent_name'] == agent]
            if 'creative_total' in agent_data.columns and 'date' in agent_data.columns:
                # Group by date first, take first value per date, then sum
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['creative_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            avg_stats[agent]['creative'] = total / 7

    if not sms_7d.empty and 'agent_name' in sms_7d.columns:
        for agent in sms_7d['agent_name'].unique():
            if agent not in avg_stats:
                avg_stats[agent] = {'creative': 0, 'sms': 0}
            agent_data = sms_7d[sms_7d['agent_name'] == agent]
            if 'sms_total' in agent_data.columns and 'date' in agent_data.columns:
                # Group by date first, take first value per date, then sum
                daily_totals = agent_data.groupby(agent_data['date'].dt.date)['sms_total'].first()
                total = int(daily_totals.sum())
            else:
                total = len(agent_data)
            avg_stats[agent]['sms'] = total / 7

    # Build report - Facebook Ads only
    report = f"📊 <b>Advertiser KPI Report</b> - {yesterday.strftime('%b %d, %Y')}\n"
    report += f"<i>vs Last 7 Days Average</i>\n\n"

    # Facebook Ads Section only
    if fb_ads_df is not None and not fb_ads_df.empty:
        fb_section = generate_facebook_ads_section(fb_ads_df, yesterday)
        report += fb_section
    else:
        report += "⚠️ No Facebook Ads data available for this date.\n"

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


def generate_daily_report(report_date=None, send_to_telegram=True):
    """Generate and optionally send daily report - Facebook Ads only"""
    if report_date is None:
        report_date = datetime.now().date()

    print(f"Generating report for {report_date}...")

    # Load Facebook Ads data only
    fb_ads_df = load_facebook_ads_data()

    report = f"📊 <b>Advertiser KPI Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"

    if fb_ads_df is not None and not fb_ads_df.empty:
        fb_section = generate_facebook_ads_section(fb_ads_df, report_date)
        if fb_section:
            report += fb_section
        else:
            report += "⚠️ No Facebook Ads data for this date.\n"
    else:
        report += "⚠️ No Facebook Ads data available.\n"

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
    """Send T+1 report (yesterday with 7-day avg comparison)"""
    print("Generating T+1 report...")

    # Load agent data
    all_ads, all_creative, all_sms, all_content = load_all_agent_data()

    # Load Facebook Ads data
    print("Loading Facebook Ads data...")
    fb_ads_df = load_facebook_ads_data()
    if fb_ads_df is not None and not fb_ads_df.empty:
        print(f"Loaded {len(fb_ads_df)} rows of Facebook Ads data")
    else:
        print("No Facebook Ads data loaded")
        fb_ads_df = None

    report = generate_t1_report(all_ads, all_creative, all_sms, all_content, fb_ads_df)

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
