"""
Standalone script to send daily T+1 report to Telegram
Designed to be run by Windows Task Scheduler at 8am daily
"""
import sys
import os

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from data_loader import load_agent_performance_data, load_agent_content_data
from config import AGENTS
from daily_report import generate_t1_report

def send_report():
    """Load data, generate report, and send to Telegram"""
    print("Loading data...")
    all_ads, all_creative, all_sms, all_content = [], [], [], []

    for agent in AGENTS:
        running_ads, creative, sms = load_agent_performance_data(agent['name'], agent['sheet_performance'])
        content = load_agent_content_data(agent['name'], agent['sheet_content'])
        if running_ads is not None and not running_ads.empty: all_ads.append(running_ads)
        if creative is not None and not creative.empty: all_creative.append(creative)
        if sms is not None and not sms.empty: all_sms.append(sms)
        if content is not None and not content.empty: all_content.append(content)

    print("Generating T+1 report...")
    report = generate_t1_report(all_ads, all_creative, all_sms, all_content)
    report += '\n\n@xxxadsron @Adsbasty'

    # Telegram config
    bot_token = '8126268680:AAEXeyB0DSmLIhx34BOlUVkFYkfvv-PW5C8'
    chat_id = '-1003623286914'  # KPI Ads group

    print("Sending to Telegram...")
    response = requests.post(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        json={'chat_id': chat_id, 'text': report, 'parse_mode': 'HTML'},
        timeout=30
    )

    if response.json().get('ok'):
        print('[OK] Report sent to KPI Ads group!')
        return True
    else:
        print(f"[ERROR] {response.json().get('description')}")
        return False

if __name__ == "__main__":
    send_report()
