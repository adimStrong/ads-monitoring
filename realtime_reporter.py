"""
Real-Time Reporter Module for BINGO365 Monitoring
Handles real-time data fetching, change detection, and dashboard screenshots
Uses P-tab data from Channel ROI sheet.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from channel_data_loader import load_agent_performance_data
from telegram_reporter import TelegramReporter
from config import (
    LOW_SPEND_THRESHOLD_USD, NO_CHANGE_ALERT, LAST_REPORT_DATA_FILE,
    DASHBOARD_URL, SCREENSHOT_DIR, TELEGRAM_MENTIONS, EXCLUDED_PERSONS
)


def get_project_dir():
    """Get the project directory path"""
    return os.path.dirname(os.path.abspath(__file__))


def get_latest_date_data():
    """
    Fetch data for the latest available date from P-tab data.

    Returns:
        tuple: (df, latest_date) - DataFrame filtered for latest date and the date itself
    """
    try:
        ptab_data = load_agent_performance_data()

        if ptab_data is None:
            print("[WARNING] No P-tab data available")
            return None, None

        daily_df = ptab_data.get('daily', pd.DataFrame())

        if daily_df is None or daily_df.empty:
            print("[WARNING] No P-tab daily data available")
            return None, None

        # Get latest date
        daily_df = daily_df.copy()
        daily_df['date_only'] = pd.to_datetime(daily_df['date']).dt.date
        latest_date = daily_df['date_only'].max()

        # Filter for latest date
        latest_data = daily_df[daily_df['date_only'] == latest_date]

        # Exclude boss accounts
        if EXCLUDED_PERSONS:
            excluded_upper = [p.upper() for p in EXCLUDED_PERSONS]
            latest_data = latest_data[~latest_data['agent'].str.upper().isin(excluded_upper)]

        print(f"[OK] Loaded P-tab data for {latest_date}: {len(latest_data)} rows")
        return latest_data, latest_date

    except Exception as e:
        print(f"[ERROR] Error loading latest date data: {e}")
        return None, None


def get_last_report_file_path():
    """Get the path to the last report data file"""
    return os.path.join(get_project_dir(), LAST_REPORT_DATA_FILE)


def load_previous_report():
    """
    Load the previous report data from JSON file.

    Returns:
        dict: Previous report data or None if no previous report exists
    """
    try:
        file_path = get_last_report_file_path()
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"[OK] Loaded previous report from {data.get('timestamp', 'unknown')}")
                return data
    except Exception as e:
        print(f"[WARNING] Could not load previous report: {e}")
    return None


def save_current_report(report_data):
    """
    Save current report data for future comparison.

    Args:
        report_data: Dictionary containing current report data
    """
    try:
        file_path = get_last_report_file_path()
        report_data['timestamp'] = datetime.now().isoformat()

        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"[OK] Saved current report data to {file_path}")
    except Exception as e:
        print(f"[ERROR] Could not save report data: {e}")


def compare_with_previous(current_data, previous_data, current_date=None):
    """
    Compare current data with previous period data.
    Only compares if the date is the same (within same day tracking).
    If date changed, returns None to indicate fresh start.

    Args:
        current_data: DataFrame with current period data (P-tab columns)
        previous_data: Dictionary with previous period data
        current_date: Current data date for comparison

    Returns:
        dict: Changes per agent, or None if date changed (fresh day)
    """
    if previous_data is None:
        return None

    # Check if date changed - if so, don't compare (fresh day)
    prev_date = previous_data.get('date', None)
    if current_date and prev_date:
        if str(current_date) != str(prev_date):
            print(f"[INFO] Date changed from {prev_date} to {current_date} - starting fresh comparison")
            return None

    changes = {}
    prev_agents = previous_data.get('agents', {})

    # Aggregate current data by agent (P-tab columns: cost, register, ftd)
    current_by_agent = current_data.groupby('agent').agg({
        'cost': 'sum',
        'register': 'sum',
        'ftd': 'sum',
    }).to_dict('index')

    for agent_name, current_stats in current_by_agent.items():
        prev_stats = prev_agents.get(agent_name, {})

        spend_diff = current_stats['cost'] - prev_stats.get('spend', 0)
        reg_diff = current_stats['register'] - prev_stats.get('register', 0)
        ftd_diff = current_stats['ftd'] - prev_stats.get('ftd', 0)

        has_change = (spend_diff != 0 or reg_diff != 0 or ftd_diff != 0)

        changes[agent_name] = {
            'spend_diff': spend_diff,
            'reg_diff': reg_diff,
            'ftd_diff': ftd_diff,
            'has_change': has_change,
            'current': current_stats,
            'previous': prev_stats,
        }

    return changes


def detect_no_change_agents(changes):
    """
    Detect agents with no changes since last report.

    Args:
        changes: Dictionary of changes per agent

    Returns:
        list: List of agent names with no changes
    """
    if changes is None:
        return []

    no_change_agents = []
    for agent_name, change_info in changes.items():
        if not change_info['has_change']:
            no_change_agents.append(agent_name)

    return no_change_agents


def check_low_spend(current_data):
    """
    Check for agents with low daily spend.

    Args:
        current_data: DataFrame with current period data (P-tab columns)

    Returns:
        list: List of tuples (agent_name, spend) for agents with low spend
    """
    low_spend_agents = []

    # Aggregate by agent (P-tab uses 'cost' and 'agent')
    agent_spend = current_data.groupby('agent')['cost'].sum()

    for agent_name, spend in agent_spend.items():
        if spend < LOW_SPEND_THRESHOLD_USD:
            low_spend_agents.append((agent_name, spend))

    return low_spend_agents


def generate_dashboard_screenshot(output_path=None):
    """
    Capture a screenshot of the dashboard using Playwright.

    Args:
        output_path: Optional path for the screenshot. If None, auto-generated.

    Returns:
        str: Path to the saved screenshot or None if failed
    """
    try:
        from playwright.sync_api import sync_playwright

        # Ensure screenshot directory exists
        screenshot_dir = os.path.join(get_project_dir(), SCREENSHOT_DIR)
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)

        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(screenshot_dir, f"dashboard_{timestamp}.png")

        print(f"[INFO] Capturing dashboard screenshot...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use tall viewport to capture full page without scrolling
            page = browser.new_page(viewport={'width': 1400, 'height': 3000})

            # Navigate to dashboard
            page.goto(DASHBOARD_URL, wait_until='networkidle', timeout=60000)

            # Wait for content to load
            page.wait_for_timeout(4000)

            # Hide Streamlit sidebar and UI elements using CSS injection
            page.add_style_tag(content="""
                /* Hide sidebar completely */
                [data-testid="stSidebar"] { display: none !important; }
                [data-testid="collapsedControl"] { display: none !important; }

                /* Hide header/toolbar */
                header { display: none !important; }
                [data-testid="stToolbar"] { display: none !important; }
                [data-testid="stDecoration"] { display: none !important; }

                /* Hide menu button */
                #MainMenu { display: none !important; }
                button[kind="header"] { display: none !important; }

                /* Expand main content to full width */
                [data-testid="stAppViewContainer"] {
                    margin-left: 0 !important;
                }

                .main .block-container {
                    max-width: 100% !important;
                    padding: 1rem 3rem !important;
                }

                section[data-testid="stSidebar"] { display: none !important; }
            """)

            # Wait for CSS changes to apply
            page.wait_for_timeout(1000)

            # Scroll to load all lazy content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Get actual page dimensions
            dimensions = page.evaluate("""() => {
                return {
                    width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
                    height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
                }
            }""")
            print(f"[INFO] Page dimensions: {dimensions['width']}x{dimensions['height']}px")

            # Take full page screenshot
            page.screenshot(path=output_path, full_page=True, type='png')

            browser.close()

        print(f"[OK] Screenshot saved: {output_path}")
        return output_path

    except Exception as e:
        print(f"[ERROR] Failed to capture screenshot: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_text_summary(current_data, latest_date, changes=None, low_spend_agents=None, no_change_agents=None):
    """
    Generate a text summary with alerts for Telegram.
    Uses P-tab columns: agent, cost, register, ftd, impressions, clicks.

    Args:
        current_data: DataFrame with current period data (P-tab columns)
        latest_date: The date of the data
        changes: Dictionary of changes per agent
        low_spend_agents: List of agents with low spend
        no_change_agents: List of agents with no changes

    Returns:
        str: Formatted text summary
    """
    now = datetime.now()
    time_label = now.strftime("%I:%M %p")
    date_label = latest_date.strftime("%b %d, %Y") if latest_date else now.strftime("%b %d, %Y")

    # Calculate team totals (P-tab columns)
    team_totals = {
        'cost': current_data['cost'].sum(),
        'register': int(current_data['register'].sum()),
        'ftd': int(current_data['ftd'].sum()),
        'impressions': int(current_data['impressions'].sum()) if 'impressions' in current_data.columns else 0,
        'clicks': int(current_data['clicks'].sum()) if 'clicks' in current_data.columns else 0,
    }

    # Derived metrics
    cpr = team_totals['cost'] / team_totals['register'] if team_totals['register'] > 0 else 0
    cpftd = team_totals['cost'] / team_totals['ftd'] if team_totals['ftd'] > 0 else 0
    conv_rate = (team_totals['ftd'] / team_totals['register'] * 100) if team_totals['register'] > 0 else 0
    ctr = (team_totals['clicks'] / team_totals['impressions'] * 100) if team_totals['impressions'] > 0 else 0

    # Build report
    report = f"\U0001f4ca <b>ADVERTISER KPI REPORT</b>\n"
    report += f"\U0001f4c5 {date_label} | {time_label}\n\n"

    # Team Totals
    report += "\U0001f4b0 <b>TEAM TOTALS</b>\n"
    report += f"\u251c Spend: <b>${team_totals['cost']:,.2f}</b>\n"
    report += f"\u251c Register: <b>{team_totals['register']:,}</b>\n"
    report += f"\u251c FTD: <b>{team_totals['ftd']:,}</b>\n"
    report += f"\u251c Conv Rate: <b>{conv_rate:.1f}%</b>\n"
    report += f"\u251c CPR: <b>${cpr:.2f}</b>\n"
    report += f"\u251c Cost/FTD: <b>${cpftd:.2f}</b>\n"
    report += f"\u2514 CTR: <b>{ctr:.2f}%</b>\n\n"

    # Agent Summary Table
    report += "\U0001f465 <b>AGENT SUMMARY</b>\n"
    report += "<pre>"
    report += f"{'Agent':<8}{'Spend':>10}{'Reg':>6}{'FTD':>6}{'Conv':>6}\n"
    report += "-" * 36 + "\n"

    # Get agent data sorted by cost (P-tab columns)
    agent_data = current_data.groupby('agent').agg({
        'cost': 'sum',
        'register': 'sum',
        'ftd': 'sum',
    }).sort_values('cost', ascending=False)

    for agent_name, row in agent_data.iterrows():
        spend = row['cost']
        reg = int(row['register'])
        ftd = int(row['ftd'])
        agent_conv = (ftd / reg * 100) if reg > 0 else 0

        # Change indicators with actual amounts
        if changes and agent_name in changes:
            spend_diff = changes[agent_name]['spend_diff']
            reg_diff = changes[agent_name]['reg_diff']
            ftd_diff = changes[agent_name]['ftd_diff']

            # Format spend with change
            if spend_diff > 0:
                spend_str = f"${spend:,.0f}+{spend_diff:.0f}"
            elif spend_diff < 0:
                spend_str = f"${spend:,.0f}{spend_diff:.0f}"
            else:
                spend_str = f"${spend:,.0f}"

            # Format reg with change
            if reg_diff > 0:
                reg_str = f"{reg}+{reg_diff}"
            elif reg_diff < 0:
                reg_str = f"{reg}{reg_diff}"
            else:
                reg_str = f"{reg}"

            # Format ftd with change
            if ftd_diff > 0:
                ftd_str = f"{ftd}+{ftd_diff}"
            elif ftd_diff < 0:
                ftd_str = f"{ftd}{ftd_diff}"
            else:
                ftd_str = f"{ftd}"
        else:
            spend_str = f"${spend:,.0f}"
            reg_str = f"{reg}"
            ftd_str = f"{ftd}"

        report += f"{agent_name:<8}{spend_str:>10}{reg_str:>6}{ftd_str:>6}{agent_conv:>5.1f}%\n"

    report += "</pre>\n\n"

    # Alerts Section
    has_alerts = (low_spend_agents and len(low_spend_agents) > 0) or (no_change_agents and len(no_change_agents) > 0)

    if has_alerts:
        report += "\u26a0\ufe0f <b>ALERTS</b>\n"

        if low_spend_agents:
            for agent_name, spend in low_spend_agents:
                report += f"\u2022 <b>{agent_name}</b>: Low spend (${spend:.2f}) - Focus and work hard!\n"

        if NO_CHANGE_ALERT and no_change_agents:
            for agent_name in no_change_agents:
                report += f"\u2022 <b>{agent_name}</b>: No change since last report\n"

        report += "\n"

    # Telegram mentions
    mentions = []
    for person, username in TELEGRAM_MENTIONS.items():
        mentions.append(f"@{username}")

    if mentions:
        report += " ".join(mentions)

    return report


def prepare_report_data(current_data, latest_date):
    """
    Prepare report data for saving and comparison.
    Uses P-tab columns: agent, cost, register, ftd.

    Args:
        current_data: DataFrame with current period data
        latest_date: The date of the data

    Returns:
        dict: Report data structure
    """
    # Aggregate by agent (P-tab columns)
    agent_data = current_data.groupby('agent').agg({
        'cost': 'sum',
        'register': 'sum',
        'ftd': 'sum',
    }).to_dict('index')

    # Convert to serializable format
    agents = {}
    for agent_name, stats in agent_data.items():
        agents[agent_name] = {
            'spend': float(stats['cost']),
            'register': int(stats['register']),
            'ftd': int(stats['ftd']),
        }

    # Team totals
    team_totals = {
        'spend': float(current_data['cost'].sum()),
        'register': int(current_data['register'].sum()),
        'ftd': int(current_data['ftd'].sum()),
    }

    return {
        'date': str(latest_date),
        'team_totals': team_totals,
        'agents': agents,
    }


def send_realtime_report(send_screenshot=True, send_text=True, combined=True):
    """
    Main function to generate and send the real-time report.

    Args:
        send_screenshot: Whether to send dashboard screenshot
        send_text: Whether to send text summary
        combined: If True, send screenshot with text as caption (single message)

    Returns:
        bool: True if successful, False otherwise
    """
    print("=" * 50)
    print(f"Real-Time Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        # 1. Load latest data
        current_data, latest_date = get_latest_date_data()

        if current_data is None or current_data.empty:
            print("[ERROR] No data available for report")
            return False

        # 2. Load previous report for comparison
        previous_data = load_previous_report()

        # 3. Compare with previous (only if same date)
        changes = compare_with_previous(current_data, previous_data, latest_date)

        # 4. Detect alerts
        low_spend_agents = check_low_spend(current_data)
        no_change_agents = detect_no_change_agents(changes) if NO_CHANGE_ALERT else []

        print(f"[INFO] Low spend agents: {[a[0] for a in low_spend_agents]}")
        print(f"[INFO] No change agents: {no_change_agents}")

        # 5. Generate text summary
        text_summary = generate_text_summary(
            current_data, latest_date, changes, low_spend_agents, no_change_agents
        )

        # 6. Initialize Telegram reporter
        reporter = TelegramReporter()

        # 7. Capture and send screenshot (if enabled)
        screenshot_path = None
        if send_screenshot:
            screenshot_path = generate_dashboard_screenshot()

        # 8. Send report (combined or separate)
        if combined and screenshot_path:
            # Send single message: photo with text as caption
            # Telegram caption limit is 1024 chars, so use full text
            reporter.send_photo(screenshot_path, caption=text_summary)
            print("[OK] Dashboard + summary sent to Telegram (combined)")
        else:
            # Send separately
            if screenshot_path:
                reporter.send_photo(screenshot_path, caption=f"\U0001f4ca Dashboard - {latest_date}")
                print("[OK] Screenshot sent to Telegram")
            elif send_screenshot:
                print("[WARNING] Screenshot capture failed, sending text only")

            if send_text:
                reporter.send_message(text_summary)
                print("[OK] Text summary sent to Telegram")

        # 9. Save current report for next comparison
        report_data = prepare_report_data(current_data, latest_date)
        save_current_report(report_data)

        print("[OK] Real-time report completed successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to send real-time report: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_text_only_report():
    """Send report without screenshot (for quick updates)"""
    return send_realtime_report(send_screenshot=False, send_text=True)


def test_screenshot():
    """Test screenshot capture only"""
    path = generate_dashboard_screenshot()
    if path:
        print(f"[OK] Test screenshot saved: {path}")
    else:
        print("[ERROR] Test screenshot failed")
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Real-Time KPI Reporter')
    parser.add_argument('--text-only', action='store_true', help='Send text report only (no screenshot)')
    parser.add_argument('--screenshot-test', action='store_true', help='Test screenshot capture only')
    parser.add_argument('--preview', action='store_true', help='Preview report without sending')

    args = parser.parse_args()

    if args.screenshot_test:
        test_screenshot()
    elif args.text_only:
        send_text_only_report()
    elif args.preview:
        current_data, latest_date = get_latest_date_data()
        if current_data is not None:
            previous_data = load_previous_report()
            changes = compare_with_previous(current_data, previous_data, latest_date)
            low_spend = check_low_spend(current_data)
            no_change = detect_no_change_agents(changes)

            text = generate_text_summary(current_data, latest_date, changes, low_spend, no_change)
            print("\n" + "=" * 50)
            print("PREVIEW (not sent)")
            print("=" * 50)
            print(text)
    else:
        send_realtime_report()
