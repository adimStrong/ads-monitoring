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

import requests as http_requests

from channel_data_loader import (
    load_agent_performance_data as load_ptab_data,
    load_ab_testing_data, load_created_assets_data,
)
from daily_report import (
    generate_facebook_ads_section,
    generate_by_campaign_section,
    generate_ab_testing_section, generate_account_dev_section,
)
from config import (
    DAILY_REPORT_ENABLED,
    DAILY_REPORT_SEND_TIME,
    DAILY_REPORT_REMINDERS,
    TELEGRAM_MENTIONS,
)
from telegram_reporter import TelegramReporter
from realtime_reporter import generate_dashboard_screenshot

# Lock file to prevent duplicate scheduler instances
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.daily_report.lock')

# Chat Listener API for reporting accuracy
CHAT_API_URL = os.getenv("CHAT_API_URL", "https://humble-illumination-production-713f.up.railway.app")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "juan365chat")

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


def send_long_message(reporter, text, max_len=4000):
    """Split and send a long message in chunks, breaking at newlines.
    Ensures <pre> tags are properly closed/reopened across chunks."""
    if len(text) <= max_len:
        reporter.send_message(text)
        return

    parts = []
    current = ""
    for line in text.split('\n'):
        # +1 for the newline character
        if len(current) + len(line) + 1 > max_len:
            parts.append(current)
            current = line
        else:
            current = current + '\n' + line if current else line
    if current:
        parts.append(current)

    # Fix split <pre> tags: if a chunk has an unclosed <pre>, close it and reopen in next chunk
    for i in range(len(parts)):
        open_count = parts[i].count('<pre>') + parts[i].count('<pre ')
        close_count = parts[i].count('</pre>')
        if open_count > close_count:
            parts[i] += '</pre>'
            if i + 1 < len(parts):
                parts[i + 1] = '<pre>' + parts[i + 1]

    for i, part in enumerate(parts):
        reporter.send_message(part)
        logger.info(f"Sent message part {i+1}/{len(parts)} ({len(part)} chars)")


def build_reporting_summary():
    """Fetch reporting accuracy from Chat Listener API and build summary message."""
    try:
        resp = http_requests.get(
            f"{CHAT_API_URL}/api/reporting",
            params={'key': CHAT_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data:
            return None

        # Sort by avg_minute ascending (best first)
        agents = sorted(data.items(), key=lambda x: x[1].get('avg_minute', 99))

        msg = '📊 <b>Reporting Accuracy Summary</b>\n'
        msg += '<i>Auto-scored from Telegram chat reports</i>\n\n'
        msg += '<pre>\n'
        msg += f'{"Agent":<10} {"Reports":>7}  {"Avg Min":>7}  {"Score":>5}\n'
        msg += '─' * 38 + '\n'
        for agent, info in agents:
            count = info.get('report_count', 0)
            avg = info.get('avg_minute', 0)
            score = info.get('score', 0)
            msg += f'{agent:<10} {count:>7}  {avg:>5.1f}m  {score:>3}/4\n'
        msg += '</pre>\n\n'
        msg += '<b>Rubric:</b> 4: &lt;15min | 3: 15-24min | 2: 25-34min | 1: 35+min'

        return msg
    except Exception as e:
        logger.error(f"Failed to fetch reporting accuracy: {e}")
        return None


def build_ab_testing_summary():
    """Load A/B Testing data and build summary message."""
    try:
        ab_data = load_ab_testing_data()
        if not ab_data:
            return None
        return generate_ab_testing_section(ab_data)
    except Exception as e:
        logger.error(f"Failed to build A/B Testing summary: {e}")
        return None


def build_account_dev_summary():
    """Load Created Assets data and build Account Dev summary message."""
    try:
        assets_df = load_created_assets_data()
        if assets_df is None or assets_df.empty:
            return None
        return generate_account_dev_section(assets_df)
    except Exception as e:
        logger.error(f"Failed to build Account Dev summary: {e}")
        return None


def send_report():
    """Load P-tab data, generate report, and send to Telegram."""
    if not DAILY_REPORT_ENABLED:
        logger.warning("Daily report sending is disabled in config.py")
        return False

    import pandas as pd
    import time

    # Retry loading P-tab data (Google Sheets API can be flaky under concurrent access)
    ptab_data = None
    for attempt in range(3):
        logger.info(f"Loading P-tab data... (attempt {attempt + 1}/3)")
        ptab_data = load_ptab_data()
        daily_df = ptab_data.get('daily', pd.DataFrame()) if ptab_data else pd.DataFrame()
        ad_accounts_df = ptab_data.get('ad_accounts', pd.DataFrame()) if ptab_data else pd.DataFrame()

        if not daily_df.empty or not ad_accounts_df.empty:
            break
        logger.warning(f"Attempt {attempt + 1}: No P-tab data loaded, retrying in 10s...")
        time.sleep(10)

    if daily_df.empty and ad_accounts_df.empty:
        logger.error("No P-tab data loaded after 3 attempts!")
        return False

    # T+1 reporting: yesterday's data
    yesterday = (datetime.now() - timedelta(days=1)).date()

    logger.info(f"Generating T+1 report for {yesterday}...")
    report = f"📊 <b>BINGO365 T+1 Report</b> - {yesterday.strftime('%b %d, %Y')}\n\n"

    # Facebook Ads overview section (from daily data)
    if not daily_df.empty:
        fb_section = generate_facebook_ads_section(daily_df, yesterday)
        if fb_section:
            report += fb_section

    # By Campaign section (from ad accounts data)
    if not ad_accounts_df.empty:
        report += generate_by_campaign_section(ad_accounts_df, yesterday)

    report += '\n@xxxadsron @Adsbasty'

    logger.info("Sending to Telegram...")
    try:
        reporter = TelegramReporter()

        # Capture and send dashboard screenshot (split into 2 parts)
        logger.info("Capturing dashboard screenshot...")
        screenshot_parts = generate_dashboard_screenshot(split=True)
        if screenshot_parts and isinstance(screenshot_parts, list):
            for i, part_path in enumerate(screenshot_parts):
                caption = f"📊 <b>BINGO365 T+1 Report</b> - {yesterday.strftime('%b %d, %Y')} (Part {i+1}/{len(screenshot_parts)})"
                reporter.send_photo(part_path, caption=caption)
            logger.info(f"Dashboard screenshot sent ({len(screenshot_parts)} parts)!")
        elif screenshot_parts:
            reporter.send_photo(
                screenshot_parts,
                caption=f"📊 <b>BINGO365 T+1 Report</b> - {yesterday.strftime('%b %d, %Y')}"
            )
            logger.info("Dashboard screenshot sent!")
        else:
            logger.warning("Screenshot capture failed, continuing with text report")

        send_long_message(reporter, report)
        logger.info("By Campaign report sent!")

        # Send Reporting Accuracy Summary
        logger.info("Fetching reporting accuracy summary...")
        summary = build_reporting_summary()
        if summary:
            reporter.send_message(summary)
            logger.info("Reporting accuracy summary sent!")
        else:
            logger.warning("No reporting accuracy data available")

        # Send A/B Testing Progress
        logger.info("Building A/B Testing summary...")
        ab_summary = build_ab_testing_summary()
        if ab_summary:
            reporter.send_message(ab_summary)
            logger.info("A/B Testing summary sent!")
        else:
            logger.warning("No A/B Testing data available")

        # Send Account Dev Progress
        logger.info("Building Account Dev summary...")
        acct_summary = build_account_dev_summary()
        if acct_summary:
            reporter.send_message(acct_summary)
            logger.info("Account Dev summary sent!")
        else:
            logger.warning("No Account Dev data available")

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
            'misfire_grace_time': 3600,  # 1 hour grace period to catch misfires
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


def acquire_lock():
    """Acquire a lock file to prevent duplicate scheduler instances. Returns True if acquired."""
    try:
        if os.path.exists(LOCK_FILE):
            # Check if the PID in the lock file is still running
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if process is still alive
            try:
                os.kill(old_pid, 0)  # signal 0 = check if alive
                return False  # Process still running
            except (OSError, ProcessLookupError):
                logger.warning(f"Stale lock file (PID {old_pid} dead), removing...")
                os.remove(LOCK_FILE)
        # Write our PID
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.error(f"Lock file error: {e}")
        return True  # Proceed anyway on error


def release_lock():
    """Release the lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def graceful_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Received shutdown signal, stopping scheduler...")
    release_lock()
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

    # Prevent duplicate scheduler instances
    if not acquire_lock():
        logger.error("Another daily report scheduler is already running! Exiting.")
        return

    # Start scheduler
    print_schedule()
    logger.info("Starting Daily Report Scheduler...")

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Check if we started at or near report time — send immediately
    try:
        from pytz import timezone as pytz_tz
        now_ph = datetime.now(pytz_tz('Asia/Manila'))
    except ImportError:
        now_ph = datetime.now()
    send_hour = DAILY_REPORT_SEND_TIME['hour']
    send_minute = DAILY_REPORT_SEND_TIME['minute']
    if now_ph.hour == send_hour and now_ph.minute <= send_minute + 5:
        # Started within 5 min of report time — send report immediately
        logger.info("Scheduler started at report time - sending report now!")
        send_report()
    elif now_ph.hour > send_hour or (now_ph.hour == send_hour and now_ph.minute > send_minute + 5):
        logger.warning(f"Scheduler started after {send_hour}:{send_minute:02d} - report may have been missed today")

    scheduler = setup_scheduler()

    try:
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        release_lock()


if __name__ == "__main__":
    main()
