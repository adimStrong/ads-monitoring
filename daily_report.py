"""
Daily Report Generator for BINGO365 Monitoring
Generates and sends daily reports to Telegram
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import load_agent_performance_data, load_agent_content_data
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


def generate_t1_report(all_ads, all_creative, all_sms, all_content):
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

    # Build report
    report = f"📊 <b>BINGO365 T+1 Report</b> - {yesterday.strftime('%b %d, %Y')}\n"
    report += f"<i>vs Last 7 Days Average</i>\n\n"

    # Creative Section
    report += "🎨 <b>CREATIVE</b>\n<pre>"
    report += f"{'Name':<10}{'T+1':>6}{'7D Avg':>8}{'Diff':>8}\n"
    report += "-" * 32 + "\n"

    all_agents = set(list(t1_stats.keys()) + list(avg_stats.keys()))
    total_t1_creative = 0
    total_avg_creative = 0

    for agent in sorted(all_agents):
        t1_val = t1_stats.get(agent, {}).get('creative', 0)
        avg_val = avg_stats.get(agent, {}).get('creative', 0)
        diff = t1_val - avg_val
        diff_str = f"+{diff:.0f}" if diff >= 0 else f"{diff:.0f}"

        total_t1_creative += t1_val
        total_avg_creative += avg_val

        report += f"{agent:<10}{t1_val:>6}{avg_val:>8.1f}{diff_str:>8}\n"

    report += "-" * 32 + "\n"
    total_diff = total_t1_creative - total_avg_creative
    diff_str = f"+{total_diff:.0f}" if total_diff >= 0 else f"{total_diff:.0f}"
    report += f"{'TOTAL':<10}{total_t1_creative:>6}{total_avg_creative:>8.1f}{diff_str:>8}\n"
    report += "</pre>\n\n"

    # SMS Section
    report += "📱 <b>SMS</b>\n<pre>"
    report += f"{'Name':<10}{'T+1':>6}{'7D Avg':>8}{'Diff':>8}\n"
    report += "-" * 32 + "\n"

    total_t1_sms = 0
    total_avg_sms = 0

    for agent in sorted(all_agents):
        t1_val = t1_stats.get(agent, {}).get('sms', 0)
        avg_val = avg_stats.get(agent, {}).get('sms', 0)
        diff = t1_val - avg_val
        diff_str = f"+{diff:.0f}" if diff >= 0 else f"{diff:.0f}"

        total_t1_sms += t1_val
        total_avg_sms += avg_val

        report += f"{agent:<10}{t1_val:>6}{avg_val:>8.1f}{diff_str:>8}\n"

    report += "-" * 32 + "\n"
    total_diff = total_t1_sms - total_avg_sms
    diff_str = f"+{total_diff:.0f}" if total_diff >= 0 else f"{total_diff:.0f}"
    report += f"{'TOTAL':<10}{total_t1_sms:>6}{total_avg_sms:>8.1f}{diff_str:>8}\n"
    report += "</pre>\n\n"

    # Copywriting Summary - only Primary Text entries (T+1 date filtered)
    if not content_df.empty:
        # Filter for Primary Text only
        if 'content_type' in content_df.columns:
            primary_df = content_df[content_df['content_type'] == 'Primary Text']
        else:
            primary_df = content_df

        if not primary_df.empty:
            report += "📝 <b>COPYWRITING (T+1)</b>\n<pre>"
            report += f"{'Name':<10}{'Posts':>6}\n"
            report += "-" * 16 + "\n"

            total_copy = 0
            for agent in sorted(primary_df['agent_name'].unique()):
                count = len(primary_df[primary_df['agent_name'] == agent])
                total_copy += count
                report += f"{agent:<10}{count:>6}\n"

            report += "-" * 16 + "\n"
            report += f"{'TOTAL':<10}{total_copy:>6}\n"
            report += "</pre>"

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

    report = f"📊 <b>BINGO365 Weekly Report</b>\n"
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
    report = f"📊 <b>BINGO365 Daily Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
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
    report = f"📊 <b>BINGO365 Daily Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
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
    """Generate and optionally send daily report"""
    if report_date is None:
        report_date = datetime.now().date()

    print(f"Generating report for {report_date}...")

    all_ads, all_creative, all_sms, all_content = load_all_agent_data()
    has_running_ads, today_ads = check_running_ads(all_ads, report_date)

    if has_running_ads:
        print("[OK] Running ads found - generating ads report")
        report = generate_ads_report(today_ads, report_date)
    else:
        print("[!] No running ads - generating creative/SMS/copywriting report")
        report = generate_no_ads_report(all_creative, all_sms, all_content, report_date)

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

    all_ads, all_creative, all_sms, all_content = load_all_agent_data()
    report = generate_t1_report(all_ads, all_creative, all_sms, all_content)

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
    print("BINGO365 Daily Report Generator")
    print("=" * 50)
    report = preview_report()
    print("\n" + report)
