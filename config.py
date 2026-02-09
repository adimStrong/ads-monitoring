"""
Configuration settings for BINGO365 Monitoring Dashboard
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Try to use Streamlit secrets (for Streamlit Cloud), fall back to env vars
def get_secret(section, key, default=None):
    """Get secret from Streamlit secrets or environment variable"""
    try:
        import streamlit as st
        return st.secrets.get(section, {}).get(key, default)
    except:
        return default

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    get_secret("database", "url", "postgresql://postgres:password@localhost:5432/bingo365_monitoring")
)

# Google Sheets Configuration
GOOGLE_SHEETS_ID = os.getenv(
    "GOOGLE_SHEETS_ID",
    get_secret("google_sheets", "sheet_id", "1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ")
)

# Indian Promotion Sheet (separate spreadsheet with copywriting data)
INDIAN_PROMOTION_SHEET_ID = "1R505heWwSum89jzRNEfeLy9eNhXfYNMXziSFEj8jtsk"
INDIAN_PROMOTION_GID = "204961561"

# Indian Promotion agent column positions (each agent has: DATE, TYPE, PRIMARY CONTENT, CONDITION, STATUS)
# SHEENA removed - resigned
INDIAN_PROMOTION_AGENTS = {
    'ADRIAN': {'date': 0, 'type': 1, 'content': 2, 'condition': 3, 'status': 4},
    'JOMAR': {'date': 6, 'type': 7, 'content': 8, 'condition': 9, 'status': 10},
    'SHILA': {'date': 12, 'type': 13, 'content': 14, 'condition': 15, 'status': 16},
    'KRISSA': {'date': 18, 'type': 19, 'content': 20, 'condition': 21, 'status': 22},
    'MIKA': {'date': 30, 'type': 31, 'content': 32, 'condition': 33, 'status': 34},
}

# Agent Configuration (SHEENA removed - resigned, JD excluded - boss)
# RON only appears in Facebook Ads data, not in main sheets
AGENTS = [
    {"name": "MIKA", "sheet_performance": "MIKA", "sheet_content": "Mika content"},
    {"name": "ADRIAN", "sheet_performance": "ADRIAN", "sheet_content": "Adrian content"},
    {"name": "JOMAR", "sheet_performance": "JOMAR", "sheet_content": "Jomar content"},
    {"name": "SHILA", "sheet_performance": "SHILA", "sheet_content": "Shila content"},
    {"name": "KRISSA", "sheet_performance": "KRISSA", "sheet_content": "Krissa content"},
]

# Excluded from reports (boss accounts)
# Note: JD is not in INDIVIDUAL KPI sheet, so no filtering needed
EXCLUDED_PERSONS = ["JD"]

# ============================================================
# SECTION 1: WITH RUNNING ADS (Columns A-N)
# ============================================================
RUNNING_ADS_COLUMNS = {
    "DATE": "date",                      # A (index 0)
    "AMOUNT SPENT": "amount_spent",      # B (index 1) - NEW
    "TOTAL AD": "total_ad",              # C (index 2)
    "CAMPAIGN": "campaign",              # D (index 3)
    "IMPRESSION": "impressions",         # E (index 4)
    "CLICKS": "clicks",                  # F (index 5)
    "CTR %": "ctr_percent",              # G (index 6)
    "CPC": "cpc",                        # H (index 7)
    "CPR": "cpr",                        # I (index 8) - NEW (Cost Per Result)
    "CONVERSION RATE": "conversion_rate",# J (index 9)
    "REJECTED COUNT": "rejected_count",  # K (index 10)
    "DELETED COUNT": "deleted_count",    # L (index 11)
    "ACTIVE COUNT": "active_count",      # M (index 12)
    "REMARKS": "ad_remarks",             # N (index 13)
}

# ============================================================
# SECTION 2: WITHOUT (Content/Creative Work) (Columns O-T)
# ============================================================
CREATIVE_WORK_COLUMNS = {
    "CREATIVE FOLDER": "creative_folder", # O (index 14)
    "TYPE": "creative_type",              # P (index 15)
    "TOTAL": "creative_total",            # Q (index 16) - NEW
    "CONTENT": "creative_content",        # R (index 17)
    "CAPTION": "caption",                 # S (index 18)
    "REMARKS": "creative_remarks",        # T (index 19)
}

# ============================================================
# SECTION 3: SMS (Columns U-W)
# ============================================================
SMS_COLUMNS = {
    "TYPE": "sms_type",                   # U (index 20)
    "TOTAL": "sms_total",                 # V (index 21)
    "REMARKS": "sms_remarks",             # W (index 22)
}

# ============================================================
# CONTENT TAB COLUMNS (Primary Content Analysis)
# ============================================================
CONTENT_COLUMNS = {
    "DATE": "date",                        # A
    "TYPE": "content_type",                # B (Primary Text / Headline)
    "PRIMARY CONTENT": "primary_content",  # C
    "CONDITION": "condition",              # D
    "STATUS": "status",                    # E
    "PRIMARY ADJUSTMENT": "primary_adjustment", # F
    "REMARK/S": "remarks",                 # G
}

# Combined performance columns (for backward compatibility)
PERFORMANCE_COLUMNS = {
    **RUNNING_ADS_COLUMNS,
    **CREATIVE_WORK_COLUMNS,
    **SMS_COLUMNS,
}

# Similarity thresholds
SIMILARITY_HIGH = 0.85  # Flag as duplicate
SIMILARITY_MEDIUM = 0.70  # Similar content
SIMILARITY_LOW = 0.50  # Some overlap

# Dashboard settings
PAGE_TITLE = "BINGO365 Daily Monitoring"
PAGE_ICON = "🎰"

# Data refresh interval (in minutes) for Facebook Ads data
DATA_REFRESH_INTERVAL_MINUTES = 10

# Content types
CONTENT_TYPES = ["Primary Text", "Headline"]

# SMS types (from actual data)
SMS_TYPES = [
    "36.5 sign up bonus",
    "Affiliate earn up to 50.00",
    "All in sa sayawan 10 17 iphone pro and 1m",
    "Get up to 100,000 daily promo code",
    "Christmas angpao rain",
    "Spin and get 500 invite friends to cashout faster",
    "Get up to 1.5 rebates on every bet",
    "Get up to 150% deposit bonus everyday",
    "Download the APP and get up 500",
    "Weekly cashback up to 8%",
]

# ============================================================
# FACEBOOK ADS CONFIGURATION (New Ads Data Source)
# ============================================================
FACEBOOK_ADS_SHEET_ID = "13oDZjGctd8mkVik2_kUxSPpIQQUyC_iIuIHplIFWeUM"
FACEBOOK_ADS_CREDENTIALS_FILE = "credentials.json"

# Sheets to load - Now using INDIVIDUAL KPI sheet (single source of truth)
# This replaces the previous dual BM sheets (BM: XSKG CS, BM: Juanzone365)
FACEBOOK_ADS_SHEETS = [
    {"name": "INDIVIDUAL KPI", "gid": 2103624741},
]

# Each person has 10 columns with these starting positions:
# JASON=17, RON=27, SHILA=37, ADRIAN=47, JOMAR=57, KRISSA=67, MIKA=77, DER=87
# Column offsets per person (10-column blocks):
#   +0: Date, +1: Type, +2: Spend(USD), +3: Cost(PHP), +4: FTD
#   +5: Register, +6: People Reach, +7: Impressions, +8: Clicks
FACEBOOK_ADS_ACCOUNT_START_COLS = [17, 27, 37, 47, 57, 67, 77, 87]

FACEBOOK_ADS_COLUMN_OFFSETS = {
    'date': 0,
    'type': 1,
    'spend': 2,
    'cost_php': 3,
    'result_ftd': 4,
    'register': 5,
    'reach': 6,
    'impressions': 7,
    'clicks': 8,
}

# Summary columns (aggregated totals) - columns 3-15
FACEBOOK_ADS_SUMMARY_COLS = {
    'spend': 3,
    'reach': 5,
    'impressions': 6,
    'clicks': 7,
    'register': 8,
    'first_deposit': 9,
    'ftd_recharge': 10,
    'conversion_rate': 11,
    'cost_per_register': 12,
    'cost_per_ftd': 13,
    'cpm': 14,
    'ctr': 15,
}

# Data starts at row 5 (0-indexed: row 4)
FACEBOOK_ADS_DATA_START_ROW = 4

# Row where person names are located (0-indexed: row 1 = Row 2)
# INDIVIDUAL KPI sheet has names in Row 2 (index 1)
FACEBOOK_ADS_NAMES_ROW = 1

# ============================================================
# REAL-TIME REPORT CONFIGURATION
# ============================================================
REALTIME_REPORT_ENABLED = False  # Disabled - Individual KPI sending stopped
DAILY_REPORT_ENABLED = False  # Disabled - Individual KPI daily sending stopped

# Send times for real-time reports (7 times daily)
REALTIME_SEND_TIMES = [
    {"hour": 6, "minute": 0, "label": "6:00 AM"},
    {"hour": 9, "minute": 0, "label": "9:00 AM"},
    {"hour": 13, "minute": 0, "label": "1:00 PM"},
    {"hour": 17, "minute": 0, "label": "5:00 PM"},
    {"hour": 20, "minute": 30, "label": "8:30 PM"},
    {"hour": 23, "minute": 0, "label": "11:00 PM"},
    {"hour": 3, "minute": 0, "label": "3:00 AM"},
]

# Alert thresholds
LOW_SPEND_THRESHOLD_USD = 100  # Alert if daily spend < $100
NO_CHANGE_ALERT = True  # Alert if no change between periods

# Screenshot settings
DASHBOARD_URL = "http://localhost:8501/Report_Dashboard"
SCREENSHOT_DIR = "reports/screenshots"

# Last report data file (for change detection)
LAST_REPORT_DATA_FILE = "last_report_data.json"

# Facebook Ads persons for reports
FACEBOOK_ADS_PERSONS = ["JASON", "RON", "SHILA", "ADRIAN", "JOMAR", "KRISSA", "MIKA", "DER"]

# Telegram mentions for alerts (username without @)
TELEGRAM_MENTIONS = {
    "JASON": "xxxadsron",
    "RON": "Adsbasty",
    "DER": "Derr_Juan365",
    "SHILA": "yakis0va",
    "ADRIAN": "cutie0717",
    "KRISSA": "Ads_Krissa",
    "MIKA": "CrWn365",
    "JOMAR": "HappyAllDaze",
}

# ============================================================
# CHANNEL ROI DASHBOARD CONFIGURATION
# ============================================================
CHANNEL_ROI_ENABLED = True
CHANNEL_ROI_SHEET_ID = "1P6GoOQUa7FdiGKPLJiytMzYvkRJwt7jPmqqHo0p0p0c"
CHANNEL_ROI_SERVICE_ACCOUNT = "juan365-reporter@juan365-reporter.iam.gserviceaccount.com"

# Sheet names and GIDs
CHANNEL_FB_SHEET = {"name": "FB Summary", "gid": 1984146178}
CHANNEL_GOOGLE_SHEET = {"name": "Google Summary", "gid": 667960594}

# Date format in sheets (e.g., 9/21/2025)
CHANNEL_DATE_FORMAT = "%m/%d/%Y"

# Google report section headers (for parsing multi-section sheet)
GOOGLE_REPORT_SECTIONS = [
    "GOOGLE CHANNEL REPORT (DAILY ROI)",
    "GOOGLE CHANNEL REPORT (ROLL BACK)",
    "GOOGLE CHANNEL REPORT (VIOLET)",
]

# Column mapping for FB Summary sheet - 3 sections in different columns
# Row 3 has headers, data starts at row 5
CHANNEL_FB_HEADER_ROW = 3   # Row index (1-based) where headers are
CHANNEL_FB_DATA_START_ROW = 5  # Row index (1-based) where data starts

# FB DAILY ROI: Columns B-L (index 1-11)
CHANNEL_FB_DAILY_ROI_COLUMNS = {
    'date': 1,              # B - DATE
    'cost': 2,              # C - COST (USD)
    'register': 3,          # D - REGISTER
    'ftd': 4,               # E - FIRST DEPOSIT
    'ftd_recharge': 5,      # F - FTD RECHARGE (PHP)
    'avg_recharge': 6,      # G - AVG RECHARGE
    'conversion_ratio': 7,  # H - Conversion Ratio %
    'cpr': 8,               # I - COST PER REGISTER
    'cpftd': 9,             # J - COST PER FTD
    'roas': 10,             # K - ROAS
    'cpm': 11,              # L - COST CPM
}

# FB ROLL BACK: Columns N-X (index 13-23)
CHANNEL_FB_ROLL_BACK_COLUMNS = {
    'date': 13,             # N - DATE
    'cost': 14,             # O - COST (USD)
    'register': 15,         # P - REGISTER
    'ftd': 16,              # Q - FIRST DEPOSIT
    'ftd_recharge': 17,     # R - FTD RECHARGE (PHP)
    'avg_recharge': 18,     # S - AVG RECHARGE
    'conversion_ratio': 19, # T - Conversion Ratio
    'cpr': 20,              # U - COST PER REGISTER
    'cpftd': 21,            # V - COST PER FTD
    'roas': 22,             # W - ROAS
    'cpm': 23,              # X - COST CPM
}

# FB VIOLET: Columns Z-AF (index 25-31)
CHANNEL_FB_VIOLET_COLUMNS = {
    'date': 25,             # Z - DATE
    'ftd': 26,              # AA - FIRST RECHARGE
    'ftd_recharge': 27,     # AB - RECHARGE AMOUNT
    'avg_recharge': 28,     # AC - ARPPU
    'cost': 29,             # AD - COST
    'cpr': 30,              # AE - COST PER RECHARGE
    'roas': 31,             # AF - ROAS
}

# Legacy alias for backward compatibility
CHANNEL_FB_COLUMNS = CHANNEL_FB_DAILY_ROI_COLUMNS

# Column mapping for Google Summary sheet - 3 sections in different columns
# DAILY ROI: Columns B-L (index 1-11)
CHANNEL_GOOGLE_DAILY_ROI_COLUMNS = {
    'date': 1,              # B - DATE
    'cost': 2,              # C - COST (USD)
    'register': 3,          # D - REGISTER
    'ftd': 4,               # E - FIRST DEPOSIT
    'ftd_recharge': 5,      # F - FTD RECHARGE (PHP)
    'avg_recharge': 6,      # G - AVG RECHARGE
    'conversion_ratio': 7,  # H - Conversion Ratio %
    'cpr': 8,               # I - COST PER REGISTER
    'cpftd': 9,             # J - COST PER FTD
    'roas': 10,             # K - ROAS
    'cpm': 11,              # L - COST CPM
}

# ROLL BACK: Columns N-W (index 13-22)
CHANNEL_GOOGLE_ROLL_BACK_COLUMNS = {
    'date': 13,             # N - DATE
    'cost': 14,             # O - COST (USD)
    'register': 15,         # P - REGISTER
    'ftd': 16,              # Q - FIRST DEPOSIT
    'ftd_recharge': 17,     # R - FTD RECHARGE (PHP)
    'avg_recharge': 18,     # S - AVG RECHARGE
    'cpr': 19,              # T - COST PER REGISTER
    'cpftd': 20,            # U - COST PER FTD
    'roas': 21,             # V - ROAS
    'cpm': 22,              # W - COST CPM
}

# VIOLET: Columns Y-AE (index 24-30) - Different structure!
CHANNEL_GOOGLE_VIOLET_COLUMNS = {
    'date': 24,             # Y - DATE
    'ftd': 25,              # Z - FIRST RECHARGE (using as FTD)
    'ftd_recharge': 26,     # AA - RECHARGE AMOUNT
    'avg_recharge': 27,     # AB - ARPPU
    'cost': 28,             # AC - COST
    'cpr': 29,              # AD - COST PER RECHARGE
    'roas': 30,             # AE - ROAS
}

# Legacy alias for backward compatibility
CHANNEL_GOOGLE_COLUMNS = CHANNEL_GOOGLE_DAILY_ROI_COLUMNS

# ============================================================
# COUNTERPART PERFORMANCE CONFIGURATION
# ============================================================
COUNTERPART_SHEET = {"name": "Counterpart Performance", "gid": 1424265282}

# Header row and data start
COUNTERPART_HEADER_ROW = 2  # Row where headers are
COUNTERPART_DATA_START_ROW = 3  # Where daily data starts

# Facebook Section: Columns B-H (index 1-7) - Column A is empty
COUNTERPART_FB_COLUMNS = {
    'channel_source': 1,      # B - Channel Source (渠道来源)
    'first_recharge': 2,      # C - First Recharge Count (首充人数)
    'total_amount': 3,        # D - Total Recharge Amount (总充值金额)
    'arppu': 4,               # E - Avg ARPPU
    'spending': 5,            # F - Spending/Cost (消耗)
    'cost_per_recharge': 6,   # G - Cost per Recharge (首充成本)
    'roas': 7,                # H - ROAS
}

# Google Section: Columns J-P (index 9-15)
COUNTERPART_GOOGLE_COLUMNS = {
    'channel_source': 9,      # J - Channel Source
    'first_recharge': 10,     # K - First Recharge Count
    'total_amount': 11,       # L - Total Recharge Amount
    'arppu': 12,              # M - Avg ARPPU
    'spending': 13,           # N - Spending/Cost
    'cost_per_recharge': 14,  # O - Cost per Recharge
    'roas': 15,               # P - ROAS
}

# ============================================================
# TEAM CHANNEL CONFIGURATION
# ============================================================
TEAM_CHANNEL_SHEET = {"name": "Team Channel", "gid": 1810393673}

# Data starts after headers (verify from sheet)
TEAM_CHANNEL_DATA_START_ROW = 4

# Columns B-H (index 1-7)
# Team name is in column B (index 1) for overall section
TEAM_CHANNEL_COLUMNS = {
    'team_name': 1,           # B - Team Name (overall section)
    'channel_source': 2,      # C - Channel Source (渠道来源)
    'cost': 3,                # D - Cost (USD)
    'registrations': 4,       # E - Registrations
    'first_recharge': 5,      # F - First Recharge Count
    'total_amount': 6,        # G - Total Recharge Amount (PHP)
    'arppu': 7,               # H - ARPPU Per Person (PHP)
}

# Known channel sources (DEERPROMO01 through DEERPROMO13)
TEAM_CHANNEL_SOURCES = [
    f"FB-FB-FB-DEERPROMO{str(i).zfill(2)}" for i in range(1, 14)
]
