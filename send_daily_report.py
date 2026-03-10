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
    generate_executive_summary, generate_operations_summary,
)
from config import (
    DAILY_REPORT_ENABLED,
    DAILY_REPORT_SEND_TIME,
    DAILY_REPORT_REMINDERS,
    TELEGRAM_MENTIONS,
    EXCLUDED_FROM_DAILY_MENTIONS,
)
from telegram_reporter import TelegramReporter
from realtime_reporter import generate_dashboard_screenshot, generate_dashboard_screenshots_3part

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
        mentions = ' '.join(f"@{v}" for k, v in TELEGRAM_MENTIONS.items() if k not in EXCLUDED_FROM_DAILY_MENTIONS)

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


def build_album_caption(daily_df, target_date):
    """Build a concise VIP/Booster-style caption for the Daily Analysis album.
    Today-only key metrics with DoD delta, weekly/monthly avg comparison,
    top agent, 3-day trend, and dashboard link. Max 1024 chars."""
    import pandas as pd
    from config import AGENT_PERFORMANCE_TABS, KPI_PHP_USD_RATE

    df = daily_df.copy()
    df['date_only'] = pd.to_datetime(df['date']).dt.date
    t1 = df[df['date_only'] == target_date]

    if t1.empty:
        return f"<b>Advertiser Daily Analysis</b> — {target_date.strftime('%b %d, %Y')}"

    prev_date = target_date - timedelta(days=1)
    prev = df[df['date_only'] == prev_date]

    # Current totals
    cost = t1['cost'].sum()
    reg = int(t1['register'].sum())
    ftd = int(t1['ftd'].sum())
    conv = (ftd / reg * 100) if reg > 0 else 0
    cpa = cost / ftd if ftd > 0 else 0
    cpr = cost / reg if reg > 0 else 0
    # ARPPU + ROAS
    arppu_vals = pd.to_numeric(t1['arppu'], errors='coerce').fillna(0)
    arppu = arppu_vals[arppu_vals > 0].mean() if (arppu_vals > 0).any() else 0
    roas = (arppu / KPI_PHP_USD_RATE / cpa) if cpa > 0 else 0

    def _delta(val, prev_val):
        if prev_val is None or prev_val == 0:
            return ""
        pct = (val - prev_val) / abs(prev_val) * 100
        if abs(pct) < 0.5:
            return ""
        sign = "+" if pct > 0 else ""
        return f" ({sign}{pct:.0f}%)"

    # Previous totals
    p_cost = prev['cost'].sum() if not prev.empty else 0
    p_ftd = int(prev['ftd'].sum()) if not prev.empty else 0
    p_reg = int(prev['register'].sum()) if not prev.empty else 0
    p_cpa = p_cost / p_ftd if p_ftd > 0 else 0

    # Weekly avg (Mon-Sun of target week)
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    wk_data = df[(df['date_only'] >= monday) & (df['date_only'] <= sunday)]
    wk_days = wk_data['date_only'].nunique() or 1
    wk_ftd = wk_data['ftd'].sum() / wk_days

    # Monthly avg
    month_start = target_date.replace(day=1)
    next_m = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_m - timedelta(days=1)
    mo_data = df[(df['date_only'] >= month_start) & (df['date_only'] <= month_end)]
    mo_days = mo_data['date_only'].nunique() or 1
    mo_ftd = mo_data['ftd'].sum() / mo_days

    # ABOVE/BELOW tags (same as Booster)
    def _tag(val, avg):
        if avg == 0:
            return ""
        pct = round((val - avg) / abs(avg) * 100, 1)
        tag = "ABOVE" if pct > 0 else "BELOW" if pct < 0 else "AT"
        return f"<b>{abs(pct)}% {tag}</b>"

    ftd_wk_tag = _tag(ftd, wk_ftd)
    ftd_mo_tag = _tag(ftd, mo_ftd)

    # Top performer by FTD + best CPA
    agent_agg = t1.groupby('agent').agg(ftd=('ftd', 'sum'), cost=('cost', 'sum')).reset_index()
    agent_agg['cpa'] = agent_agg.apply(lambda r: r['cost'] / r['ftd'] if r['ftd'] > 0 else 0, axis=1)
    top_ftd = agent_agg.sort_values('ftd', ascending=False).iloc[0] if len(agent_agg) > 0 else None
    best_cpa = agent_agg[agent_agg['cpa'] > 0].sort_values('cpa').iloc[0] if (agent_agg['cpa'] > 0).any() else None

    # No data agents
    expected = {t['agent'] for t in AGENT_PERFORMANCE_TABS}
    actual = set(t1['agent'].unique())
    no_data = expected - actual
    no_data_str = ", ".join(sorted(no_data)) if no_data else "none"

    # 3-Day Trend
    available = sorted(df['date_only'].unique(), reverse=True)
    trend_line = ""
    if len(available) >= 3:
        last3 = available[:3]
        last3_ftd = []
        for d in reversed(last3):
            day_ftd = int(df[df['date_only'] == d]['ftd'].sum())
            last3_ftd.append((d.strftime("%b %d"), day_ftd))
        trend_diff = last3_ftd[-1][1] - last3_ftd[0][1]
        trend_word = "Upward" if trend_diff > 0 else "Downward" if trend_diff < 0 else "Flat"
        trend_line = f"\u2022 Trend: <b>{trend_word}</b> ({'+' if trend_diff > 0 else ''}{trend_diff:,} FTD over 3 days)"

    lines = [
        f"<b>Advertiser Daily Analysis — {target_date.strftime('%b %d, %Y')}</b>",
        "",
        f"\u2022 Cost: <b>${cost:,.0f}</b>{_delta(cost, p_cost)} | FTD: <b>{ftd:,}</b>{_delta(ftd, p_ftd)}",
        f"\u2022 Reg: <b>{reg:,}</b>{_delta(reg, p_reg)} | Conv: <b>{conv:.1f}%</b>",
        f"\u2022 CPA: <b>${cpa:,.2f}</b>{_delta(cpa, p_cpa)} | ROAS: <b>{roas:.4f}x</b>",
        f"\u2022 {ftd_wk_tag} wk avg | {ftd_mo_tag} mo avg",
    ]

    if top_ftd is not None:
        lines.append(f"\u2022 Top FTD: <b>{top_ftd['agent']}</b> ({int(top_ftd['ftd'])})")
    if best_cpa is not None and top_ftd is not None and best_cpa['agent'] != top_ftd['agent']:
        lines.append(f"\u2022 Best CPA: <b>{best_cpa['agent']}</b> (${best_cpa['cpa']:,.2f})")
    if no_data_str != "none":
        lines.append(f"\u2022 No data: {no_data_str}")
    if trend_line:
        lines.append(trend_line)

    lines.append(f'\n<a href="https://ads-monitoring.streamlit.app/Daily_Analysis">View Dashboard</a>')
    lines.append("\n@xxxadsron @Zzzzz103 @Adsbasty")

    return "\n".join(lines)


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
    """Load P-tab data, generate clean 2-message report, and send to Telegram."""
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

    reporter = TelegramReporter()
    mentions = ' '.join(f"@{v}" for k, v in TELEGRAM_MENTIONS.items() if k not in EXCLUDED_FROM_DAILY_MENTIONS)

    try:
        # ── Screenshot Album: 4-part dashboard capture ──
        logger.info("Capturing 4-part dashboard screenshots...")
        screenshot_paths = None
        try:
            screenshot_paths = generate_dashboard_screenshots_3part()
            if screenshot_paths and len(screenshot_paths) == 4:
                caption = build_album_caption(daily_df, yesterday)
                reporter.send_album(screenshot_paths, caption=caption)
                logger.info("Screenshot album sent! (4 photos)")
            else:
                # Fallback to old 2-split approach
                logger.warning("3-part failed, falling back to 2-split...")
                screenshot_parts = generate_dashboard_screenshot(split=True)
                if isinstance(screenshot_parts, str):
                    screenshot_parts = [screenshot_parts]
                if screenshot_parts:
                    for i, part_path in enumerate(screenshot_parts):
                        cap = f"📊 <b>Advertiser KPI Report</b> — {yesterday.strftime('%b %d, %Y')}" if i == 0 else None
                        reporter.send_photo(part_path, caption=cap)
                    logger.info(f"Fallback screenshot sent! ({len(screenshot_parts)} parts)")
        except Exception as e:
            logger.warning(f"Screenshot failed (continuing with text): {e}")
        finally:
            # Clean up temp screenshot files
            if screenshot_paths:
                for p in screenshot_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass

        logger.info("Daily report complete! (album only, 4 photos)")
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
