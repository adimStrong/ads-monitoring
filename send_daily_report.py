"""
Daily T+1 Report Scheduler for BINGO365 Monitoring
Sends reminder notifications before the report, then sends the actual report.
Schedule: Reminders at 1:00 PM, 1:30 PM, 1:45 PM → Report at 2:00 PM (Asia/Manila)
"""
import sys
import os
import signal
import logging

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from channel_data_loader import load_individual_kpi_data, load_agent_performance_data as load_ptab_data
from daily_report import generate_facebook_ads_section, generate_monthly_overview, generate_by_campaign_section
from config import (
    DAILY_REPORT_ENABLED,
    DAILY_REPORT_SEND_TIME,
    DAILY_REPORT_REMINDERS,
    TELEGRAM_MENTIONS,
)
from telegram_reporter import TelegramReporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'daily_report.log'))
    ]
)
logger = logging.getLogger(__name__)


def send_reminder(minutes_before, label):
    """Send a reminder notification to Telegram before the report."""
    try:
        send_time = DAILY_REPORT_SEND_TIME['label']
        mentions = ' '.join(f"@{v}" for v in TELEGRAM_MENTIONS.values())

        msg = (
            f"⏰ <b>REMINDER: T+1 Report in {label}</b>\n\n"
            f"📊 Daily report will be sent at <b>{send_time}</b>\n"
            f"📝 Please update your data in the sheet before then.\n\n"
            f"{mentions}"
        )

        reporter = TelegramReporter()
        reporter.send_message(msg)
        logger.info(f"Reminder sent: {label} before report")
        return True
    except Exception as e:
        logger.error(f"Failed to send reminder ({label}): {e}")
        return False


def send_report():
    """Load data from INDIVIDUAL KPI sheet + P-tabs, generate report, and send to Telegram."""
    if not DAILY_REPORT_ENABLED:
        logger.warning("Daily report sending is disabled in config.py")
        return False

    logger.info("Loading INDIVIDUAL KPI data...")
    kpi_df = load_individual_kpi_data()

    logger.info("Loading P-tab data for By Campaign...")
    ptab_data = load_ptab_data()

    if (kpi_df is None or kpi_df.empty):
        logger.error("No INDIVIDUAL KPI data loaded!")
        return False

    # T+1 reporting: yesterday's data
    yesterday = (datetime.now() - timedelta(days=1)).date()

    logger.info(f"Generating T+1 report for {yesterday}...")
    report = f"📊 <b>BINGO365 T+1 Report</b> - {yesterday.strftime('%b %d, %Y')}\n"
    report += f"<i>vs Last 7 Days Average</i>\n\n"

    # Monthly overview
    report += generate_monthly_overview(kpi_df)

    # Daily T+1 performance
    report += generate_facebook_ads_section(kpi_df, yesterday)

    # By Campaign section
    import pandas as pd
    ad_accounts_df = ptab_data.get('ad_accounts', pd.DataFrame()) if ptab_data else pd.DataFrame()
    if not ad_accounts_df.empty:
        report += generate_by_campaign_section(ad_accounts_df, yesterday)

    report += '\n@xxxadsron @Adsbasty'

    logger.info("Sending to Telegram...")
    try:
        reporter = TelegramReporter()
        reporter.send_message(report)
        logger.info("Report sent to KPI Ads group!")
        return True
    except Exception as e:
        logger.error(f"Failed to send report: {e}")
        return False


def job_listener(event):
    """Listen for job execution events."""
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} executed successfully")


def setup_scheduler():
    """Set up APScheduler with reminder jobs + report job."""
    scheduler = BlockingScheduler(
        timezone='Asia/Manila',
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300,
        }
    )

    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Schedule reminder jobs
    send_hour = DAILY_REPORT_SEND_TIME['hour']
    send_minute = DAILY_REPORT_SEND_TIME['minute']
    send_dt = datetime.now().replace(hour=send_hour, minute=send_minute, second=0)

    for reminder in DAILY_REPORT_REMINDERS:
        mins = reminder['minutes_before']
        label = reminder['label']
        reminder_dt = send_dt - timedelta(minutes=mins)
        r_hour = reminder_dt.hour
        r_minute = reminder_dt.minute

        scheduler.add_job(
            send_reminder,
            CronTrigger(hour=r_hour, minute=r_minute),
            args=[mins, label],
            id=f'reminder_{mins}min',
            name=f'Reminder: {label} before report',
            replace_existing=True
        )
        logger.info(f"Scheduled reminder: {label} before → {r_hour:02d}:{r_minute:02d}")

    # Schedule the actual report
    scheduler.add_job(
        send_report,
        CronTrigger(hour=send_hour, minute=send_minute),
        id='daily_t1_report',
        name=f'Daily T+1 Report at {DAILY_REPORT_SEND_TIME["label"]}',
        replace_existing=True
    )
    logger.info(f"Scheduled report at {send_hour:02d}:{send_minute:02d}")

    return scheduler


def print_schedule():
    """Print the daily report schedule."""
    send_time = DAILY_REPORT_SEND_TIME
    print("\n" + "=" * 50)
    print("Daily T+1 Report Schedule (Asia/Manila)")
    print("=" * 50)

    send_hour = send_time['hour']
    send_minute = send_time['minute']
    send_dt = datetime.now().replace(hour=send_hour, minute=send_minute, second=0)

    for reminder in DAILY_REPORT_REMINDERS:
        r_dt = send_dt - timedelta(minutes=reminder['minutes_before'])
        print(f"  ⏰ {r_dt.strftime('%I:%M %p'):>10}  Reminder: {reminder['label']} left")

    print(f"  📊 {send_time['label']:>10}  T+1 Report Sent")
    print("=" * 50 + "\n")


def graceful_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal, stopping scheduler...")
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Daily T+1 Report Scheduler')
    parser.add_argument('--run-now', action='store_true', help='Send report immediately and exit')
    parser.add_argument('--reminder-now', action='store_true', help='Send a test reminder and exit')
    parser.add_argument('--show-schedule', action='store_true', help='Show schedule and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (start scheduler)')

    args = parser.parse_args()

    if args.show_schedule:
        print_schedule()
        return

    if args.reminder_now:
        send_reminder(0, "NOW (test)")
        return

    if args.run_now:
        send_report()
        return

    # Check if enabled
    if not DAILY_REPORT_ENABLED:
        logger.warning("Daily reporting is disabled. Set DAILY_REPORT_ENABLED = True in config.py")
        return

    # Start scheduler
    print_schedule()
    logger.info("Starting Daily Report Scheduler...")

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    scheduler = setup_scheduler()

    try:
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
