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


def check_running_ads(ads_list, target_date=None):
    """
    Check if there are running ads for the target date

    Args:
        ads_list: List of ads DataFrames
        target_date: Date to check (default: today)

    Returns:
        tuple: (has_running_ads, ads_df filtered for target_date)
    """
    if target_date is None:
        target_date = datetime.now().date()

    if not ads_list:
        return False, pd.DataFrame()

    ads_df = pd.concat(ads_list, ignore_index=True)

    # Filter for target date
    if 'date' in ads_df.columns:
        # Convert date column to date objects for comparison
        ads_df['date_only'] = pd.to_datetime(ads_df['date']).dt.date
        target_ads = ads_df[ads_df['date_only'] == target_date]

        # Check if any ads are running (total_ad > 0)
        if 'total_ad' in target_ads.columns:
            total_ads = target_ads['total_ad'].sum()
            return total_ads > 0, target_ads

    return False, pd.DataFrame()


def generate_ads_report(ads_df, report_date):
    """
    Generate report when ads are running

    Args:
        ads_df: DataFrame with today's ads data
        report_date: Date for the report

    Returns:
        str: Formatted report message
    """
    report = f"📊 <b>BINGO365 Daily Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
    report += "🎯 <b>RUNNING ADS SUMMARY</b>\n"
    report += "<pre>"
    report += f"{'Agent':<10}{'Ads':>6}{'Impr':>10}{'Clicks':>8}{'CTR%':>7}\n"
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
    """
    Generate report when no ads are running (show creative, SMS, content)

    Args:
        creative_list: List of creative DataFrames
        sms_list: List of SMS DataFrames
        content_list: List of content DataFrames
        report_date: Date for the report

    Returns:
        str: Formatted report message
    """
    report = f"📊 <b>BINGO365 Daily Report</b> - {report_date.strftime('%b %d, %Y')}\n\n"
    report += "⚠️ <b>No Running Ads Today</b>\n\n"

    # Creative Summary
    if creative_list:
        creative_df = pd.concat(creative_list, ignore_index=True)
        report += "🎨 <b>CREATIVE WORK</b>\n<pre>"
        report += f"{'Agent':<10}{'Total':>6}  {'Types'}\n"
        report += "-" * 35 + "\n"

        total_creative = 0
        for agent in sorted(creative_df['agent_name'].unique()):
            agent_data = creative_df[creative_df['agent_name'] == agent]
            total = int(agent_data['creative_total'].sum()) if 'creative_total' in agent_data.columns else len(agent_data)
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
        report += "📱 <b>SMS SUMMARY</b>\n<pre>"
        report += f"{'Agent':<10}{'Total':>6}  {'Top Type'}\n"
        report += "-" * 40 + "\n"

        total_sms = 0
        for agent in sorted(sms_df['agent_name'].unique()):
            agent_data = sms_df[sms_df['agent_name'] == agent]
            total = int(agent_data['sms_total'].sum()) if 'sms_total' in agent_data.columns else len(agent_data)
            total_sms += total

            # Get most common SMS type
            if 'sms_type' in agent_data.columns:
                top_type = agent_data['sms_type'].mode().iloc[0] if len(agent_data['sms_type'].mode()) > 0 else ''
                top_type = str(top_type)[:20] + '...' if len(str(top_type)) > 20 else str(top_type)
            else:
                top_type = ''

            report += f"{agent:<10}{total:>6}  {top_type}\n"

        report += "-" * 40 + "\n"
        report += f"{'TOTAL':<10}{total_sms:>6}\n"
        report += "</pre>\n\n"

    # Content Summary
    if content_list:
        content_df = pd.concat(content_list, ignore_index=True)
        total_content = len(content_df)

        primary_count = len(content_df[content_df['content_type'] == 'Primary Text']) if 'content_type' in content_df.columns else 0
        headline_count = len(content_df[content_df['content_type'] == 'Headline']) if 'content_type' in content_df.columns else 0

        report += "📝 <b>CONTENT SUMMARY</b>\n"
        report += f"Total Posts: <b>{total_content}</b>\n"
        report += f"• Primary Text: {primary_count}\n"
        report += f"• Headlines: {headline_count}\n\n"

        # Content per agent
        report += "<pre>"
        report += f"{'Agent':<10}{'Posts':>6}\n"
        report += "-" * 16 + "\n"
        for agent in sorted(content_df['agent_name'].unique()):
            agent_count = len(content_df[content_df['agent_name'] == agent])
            report += f"{agent:<10}{agent_count:>6}\n"
        report += "</pre>"

    return report


def generate_daily_report(report_date=None, send_to_telegram=True):
    """
    Generate and optionally send daily report

    Args:
        report_date: Date for the report (default: today)
        send_to_telegram: Whether to send to Telegram (default: True)

    Returns:
        str: The generated report message
    """
    if report_date is None:
        report_date = datetime.now().date()

    print(f"Generating report for {report_date}...")

    # Load all data
    all_ads, all_creative, all_sms, all_content = load_all_agent_data()

    # Check if ads are running today
    has_running_ads, today_ads = check_running_ads(all_ads, report_date)

    # Generate appropriate report
    if has_running_ads:
        print("[OK] Running ads found - generating ads report")
        report = generate_ads_report(today_ads, report_date)
    else:
        print("[!] No running ads - generating creative/SMS/content report")
        report = generate_no_ads_report(all_creative, all_sms, all_content, report_date)

    # Send to Telegram if requested
    if send_to_telegram:
        try:
            reporter = TelegramReporter()
            result = reporter.send_message(report)
            print("[OK] Report sent to Telegram successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to send to Telegram: {e}")
            raise

    return report


def preview_report(report_date=None):
    """
    Generate report preview without sending to Telegram

    Args:
        report_date: Date for the report (default: today)

    Returns:
        str: The generated report message
    """
    return generate_daily_report(report_date=report_date, send_to_telegram=False)


if __name__ == "__main__":
    # Test report generation
    print("=" * 50)
    print("BINGO365 Daily Report Generator")
    print("=" * 50)

    # Preview report without sending
    report = preview_report()
    print("\n" + report)
