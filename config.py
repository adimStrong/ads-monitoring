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
# JD's sheet name is "DER"
EXCLUDED_PERSONS = ["DER", "JD"]

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
REALTIME_REPORT_ENABLED = True
DAILY_REPORT_ENABLED = True

# Daily T+1 report schedule (Asia/Manila)
DAILY_REPORT_SEND_TIME = {"hour": 14, "minute": 0, "label": "2:00 PM"}
DAILY_REPORT_REMINDERS = [
    {"minutes_before": 60, "label": "1 hour"},
    {"minutes_before": 30, "label": "30 minutes"},
    {"minutes_before": 15, "label": "15 minutes"},
]

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
DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL",
    "https://ads-monitoring.streamlit.app/Report_Dashboard"
)
SCREENSHOT_DIR = "reports/screenshots"

# Last report data file (for change detection)
LAST_REPORT_DATA_FILE = "last_report_data.json"

# Facebook Ads persons for reports
FACEBOOK_ADS_PERSONS = ["JASON", "RON", "SHILA", "ADRIAN", "JOMAR", "KRISSA", "MIKA", "DER"]

# Telegram mentions for alerts (username without @)
TELEGRAM_MENTIONS = {
    "JASON": "Adsbasty",
    "RON": "xxxadsron",
    "DER": "Derr_Juan365",
    "SHILA": "cutie0717",
    "ADRIAN": "CrWn365",
    "KRISSA": "Ads_Krissa",
    "MIKA": "yakis0va",
    "JOMAR": "HappyAllDaze",
}

# Alternate TG usernames (agents with multiple accounts)
TELEGRAM_ALT_USERNAMES = {
    "JASON": ["Dyazon"],
    "RON": ["xxxghstt"],
    "SHILA": ["Layy_071710"],
    "ADRIAN": ["ecrwn365"],
    "MIKA": ["cocomew0n", "yakisOva"],
    "JOMAR": ["Jomarskii", "HappyA11Daze"],
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

# Columns B-I (index 1-8)
# Team name is in column B (index 1) for overall section
# Column C (index 2) has secondary team info or is empty
# Channel source starts at column D (index 3)
TEAM_CHANNEL_COLUMNS = {
    'team_name': 1,           # B - Team Name (overall section)
    'channel_source': 3,      # D - Channel Source (FB-FB-FB-DEERPROMO*)
    'cost': 4,                # E - Cost (USD)
    'registrations': 5,       # F - Registrations
    'first_recharge': 6,      # G - First Recharge Count
    'total_amount': 7,        # H - Total Recharge Amount (PHP)
    'arppu': 8,               # I - ARPPU Per Person (PHP)
}

# Known channel sources (DEERPROMO01 through DEERPROMO13)
TEAM_CHANNEL_SOURCES = [
    f"FB-FB-FB-DEERPROMO{str(i).zfill(2)}" for i in range(1, 14)
]

# ============================================================
# CREATED ASSETS CONFIGURATION (Channel ROI sheet)
# ============================================================
CREATED_ASSETS_TAB = {"name": "Created Assets", "gid": 820171568}
CREATED_ASSETS_HEADER_ROW = 2   # 0-indexed row with column headers
CREATED_ASSETS_DATA_START = 3   # 0-indexed first data row

# Column mapping for left section (cols B-N, index 1-13)
CREATED_ASSETS_COLUMNS = {
    'date': 1,           # B - DATE
    'creator': 2,        # C - CREATOR
    'gmail': 3,          # D - GMAIL / OUTLOOK
    'fb_username': 4,    # E - FB USERNAME
    'fb_password': 5,    # F - FB PASSWORD
    'fb_condition': 6,   # G - CONDITION (for FB account)
    'fb_page': 7,        # H - FB PAGE
    'page_condition': 8, # I - CONDITION (for page)
    'bm_name': 9,        # J - BM NAME
    'bm_condition': 10,  # K - CONDITION (for BM)
    'bm_id': 11,         # L - BM ID
    'pixel': 12,         # M - PIXEL
    'pixel_condition': 13, # N - CONDITION (for pixel)
}

# Row in KPI sheet for Account Dev write-back (0-indexed)
ACCOUNT_DEV_ROW = 16

# ============================================================
# A/B TESTING CONFIGURATION (Channel ROI sheet)
# ============================================================
AB_TESTING_TAB = {"name": "Text/AbTest", "gid": 21055881}
AB_TESTING_ROW = 13  # 0-indexed row in KPI sheet for A/B Testing write-back (row 14 in 1-indexed)
REPORTING_ROW = 14   # 0-indexed row in KPI sheet for Reporting Accuracy write-back (row 15 in 1-indexed)

# ============================================================
# UPDATED ACCOUNTS CONFIGURATION
# ============================================================
# Separate spreadsheet with 3 tabs: FB accounts, BM, Pages
UPDATED_ACCOUNTS_SHEET_ID = "1qleF_WSSq7IIcloTfSrYa-DzHlCOvwJzObeqO0UefLo"

UPDATED_ACCOUNTS_FB_TAB = {"name": "FB accounts", "gid": 0}
UPDATED_ACCOUNTS_BM_TAB = {"name": "BM", "gid": 732202932}
UPDATED_ACCOUNTS_PAGES_TAB = {"name": "Pages", "gid": 725463917}

# FB accounts tab columns (A-D)
UPDATED_ACCOUNTS_FB_COLUMNS = {
    'employee': 0,    # A - Employee's Name
    'fb_name': 1,     # B - FB NAME
    'fb_user': 2,     # C - Facebook User
    'password': 3,    # D - Password
}

# BM tab columns (A-B)
UPDATED_ACCOUNTS_BM_COLUMNS = {
    'employee': 0,    # A - Employee's Name
    'bm_name': 1,     # B - BM NAME
}

# Pages tab columns (A-B)
UPDATED_ACCOUNTS_PAGES_COLUMNS = {
    'employee': 0,    # A - Employee's Name
    'page_name': 1,   # B - PAGE NAME
}

# ============================================================
# AGENT PERFORMANCE (P-TABS) CONFIGURATION
# ============================================================
# Each P-tab has one agent's FB advertising data (monthly + daily + ad accounts)
AGENT_PERFORMANCE_TABS = [
    {"name": "P6-Mika", "gid": 1053167165, "agent": "Mika"},
    {"name": "P7-Adrian", "gid": 1573312887, "agent": "Adrian"},
    {"name": "P8-Jomar", "gid": 1484269300, "agent": "Jomar"},
    {"name": "P9-Derr", "gid": 1922385711, "agent": "Derr"},
    {"name": "P10-Ron", "gid": 39183526, "agent": "Ron"},
    {"name": "P11-Krissa", "gid": 30378048, "agent": "Krissa"},
    {"name": "P12-Jason", "gid": 1747171433, "agent": "Jason"},
    {"name": "P13-Shila", "gid": 874276337, "agent": "Shila"},
]

# Overall/monthly columns (0-indexed, col A is empty so data starts at index 1)
AGENT_PERF_OVERALL_COLUMNS = {
    'channel': 1, 'date': 2, 'cost': 3, 'register': 4, 'cpr': 5,
    'ftd': 6, 'cpd': 7, 'conv_rate': 8, 'impressions': 9,
    'clicks': 10, 'ctr': 11, 'recharge': 12, 'arppu': 13, 'roas': 14,
}

# Monthly summary section (0-indexed rows)
AGENT_PERF_MONTHLY_HEADERS_ROW = 2   # Row with monthly column headers
AGENT_PERF_MONTHLY_DATA_START = 3    # First monthly data row (Feb)
AGENT_PERF_MONTHLY_DATA_END = 7      # Exclusive end (rows 3,4,5,6)

# Daily section (0-indexed rows)
AGENT_PERF_DAILY_LABEL_ROW = 8       # Row with "Overall" label + ad account names
AGENT_PERF_DAILY_HEADERS_ROW = 9     # Row with column headers
AGENT_PERF_DAILY_DATA_START = 10     # First daily data row
AGENT_PERF_AD_ACCOUNT_START_COL = 16 # First ad account column (0-indexed)
AGENT_PERF_AD_ACCOUNT_STRIDE = 5    # Every 5 columns per ad account

# ============================================================
# INDIVIDUAL KPI (new data source for Individual Overall tab)
# ============================================================
# Sheet: 13oDZjGctd8mkVik2_kUxSPpIQQUyC_iIuIHplIFWeUM  (same as FACEBOOK_ADS_SHEET_ID)
# Tab: INDIVIDUAL KPI (GID 1788804487)
INDIVIDUAL_KPI_SHEET_ID = "13oDZjGctd8mkVik2_kUxSPpIQQUyC_iIuIHplIFWeUM"
INDIVIDUAL_KPI_GID = 1788804487

# 8 agents, 10-column blocks
INDIVIDUAL_KPI_AGENTS = {
    17: "JASON", 27: "RON", 37: "SHILA", 47: "ADRIAN",
    57: "JOMAR", 67: "KRISSA", 77: "MIKA", 87: "DER",
}

# Column offsets within each agent's 10-col block
# +0: Date, +1: Type, +2: Spend($), +3: Spend(PHP), +4: FTD,
# +5: Register, +6: People Reach, +7: Impressions, +8: Clicks
INDIVIDUAL_KPI_COL_OFFSETS = {
    'date': 0, 'type': 1, 'spend': 2, 'spend_php': 3,
    'ftd': 4, 'register': 5, 'reach': 6, 'impressions': 7, 'clicks': 8,
}

INDIVIDUAL_KPI_DATA_START_ROW = 4  # 0-indexed, first daily data row

# ============================================================
# KPI MONITORING CONFIGURATION
# ============================================================
KPI_PHP_USD_RATE = 57.7  # PHP to USD conversion for ROAS calc

# ROAS formula: =IFERROR(ARPPU / 57.7 / Cost_per_FTD, 0)
# Auto-calculable KPI scoring rubric
KPI_SCORING = {
    'cpa': {
        'name': 'CPA (Cost Per Acquisition)',
        'weight': 0.125,    # 12.5% (CPA + ROAS = 25%)
        'krs': 'Revenue Generation',
        'auto': True,
        'thresholds': [(4, 0, 9.99), (3, 10.0, 13.99), (2, 14.0, 15.0), (1, 15.01, float('inf'))],
        'direction': 'lower_better',
    },
    'roas': {
        'name': 'ROAS',
        'weight': 0.125,    # 12.5% (CPA + ROAS = 25%)
        'krs': 'Revenue Generation',
        'auto': True,
        'thresholds': [(4, 0.40, float('inf')), (3, 0.20, 0.399), (2, 0.10, 0.199), (1, 0, 0.099)],
        'direction': 'higher_better',
    },
    'cvr': {
        'name': 'CVR (Conversion Rate)',
        'weight': 0.15,     # 15% (CVR + Campaign Setup = 30%)
        'krs': 'Revenue Generation',
        'auto': True,
        'thresholds': [(4, 7.0, 100.0), (3, 4.0, 6.99), (2, 2.0, 3.99), (1, 0, 1.99)],
        'direction': 'higher_better',
    },
    'ctr': {
        'name': 'CTR',
        'weight': 0.075,    # 7.5% (CTR + A/B Testing = 15%)
        'krs': 'Campaign Efficiency',
        'auto': True,
        'thresholds': [(4, 3.0, 100.0), (3, 2.0, 2.99), (2, 1.0, 1.99), (1, 0, 0.99)],
        'direction': 'higher_better',
    },
    'account_dev': {
        'name': 'Gmail/FB Account Dev',
        'weight': 0.10,     # 10% Account Management
        'krs': 'Account Management',
        'auto': True,
        'thresholds': [(4, 5, float('inf')), (3, 3, 4), (2, 2, 2), (1, 0, 1)],
        'direction': 'higher_better',
    },
    'ab_testing': {
        'name': 'A/B Testing',
        'weight': 0.075,    # 7.5% (CTR + A/B Testing = 15%)
        'krs': 'Campaign Efficiency',
        'auto': True,
        'thresholds': [(4, 20, float('inf')), (3, 11, 19), (2, 6, 10), (1, 0, 5)],
        'direction': 'higher_better',
    },
    'reporting': {
        'name': 'Reporting Accuracy',
        'weight': 0.10,     # 10% Data & Reporting
        'krs': 'Data & Reporting',
        'auto': True,
        'thresholds': [(4, 0, 14), (3, 15, 24), (2, 25, 34), (1, 35, 999)],
        'direction': 'lower_better',
    },
}

# Manual KPIs (for display on dashboard - manager scores these)
KPI_MANUAL = {
    'campaign_setup': {'name': 'Campaign Setup Accuracy', 'weight': 0.15, 'krs': 'Campaign Efficiency'},  # 15%
    'data_insights': {'name': 'Data-Driven Insights', 'weight': 0, 'krs': 'Data & Reporting'},
    'collaboration': {'name': 'Collaboration', 'weight': 0.10, 'krs': 'Teamwork'},                         # 10%
    'communication': {'name': 'Communication', 'weight': 0, 'krs': 'Teamwork'},
}

# KPI display order
KPI_ORDER = ['cpa', 'roas', 'cvr', 'campaign_setup', 'ctr', 'ab_testing',
             'reporting', 'data_insights', 'account_dev',
             'collaboration', 'communication']

# KPI Sheet write-back configuration
KPI_SHEET_ID = "1p-r-yfofNY3n8TKKWW6GaGNKo3BX6kevYvrWCr3TZdQ"
KPI_AGENT_TABS = {
    'Mika': 'KPI-Mika',
    'Adrian': 'KPI-Adrian',
    'Jomar': 'KPI-Jomar',
    'Derr': 'KPI-Derr',
    'Ron': 'KPI-Ron',
    'Krissa': 'KPI-Krissa',
    'Jason': 'KPI-Jason',
    'Shila': 'KPI-Shila',
}

# ============================================================
# TELEGRAM CHAT LISTENER CONFIGURATION
# ============================================================
CHAT_LISTENER_BOT_TOKEN = "7925543136:AAHv-sp5wO5bavC67ICL-I0fcCEpu7QuxAY"
CHAT_LISTENER_CHAT_ID = "-1003708530748"  # migrated from -4648816254 to supergroup
CHAT_LISTENER_DB = "chat_messages.db"
CHAT_LISTENER_POLL_INTERVAL = 5  # seconds between getUpdates calls

# Reporting Accuracy scoring rubric (minutes after each hour mark)
REPORTING_ACCURACY_SCORING = [
    (4, 0, 14),      # Score 4: < 15 minutes
    (3, 15, 24),     # Score 3: 15-24 minutes
    (2, 25, 34),     # Score 2: 25-34 minutes
    (1, 35, 999),    # Score 1: 35+ minutes
]

# Keywords that indicate a report message (case-insensitive)
REPORT_KEYWORDS = [
    "cost per ftd", "cost/ftd", "cpa", "roas", "cpr",
    "report", "daily report", "update", "summary",
    "register", "ftd", "spend", "cost",
]

# Proper report format requires BOTH a campaign/format indicator AND cost data
REPORT_CAMPAIGN_INDICATORS = [
    "prom", "promo", "b-fb-fb-", "channel", "brandkw", "high int",
    "comp", "p-max", "auto test", "google ads", "meta ads",
    "as of", "hourly report", "yesterday report",
]

# Agents excluded from reporting accuracy (boss/non-reporters)
EXCLUDED_FROM_REPORTING = ["DER"]

# ============================================================
# SHARED SIDEBAR HIDE CSS
# ============================================================
SIDEBAR_HIDE_CSS = """
<style>
    [data-testid="stSidebarNav"] a[href*="Daily_ROI"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Roll_Back"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Violet"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Team_Channel"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Team_Overview"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="KPI_Monitoring"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Team_KPI"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Created_Assets"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="AB_Testing"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Chat_Monitor"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Reporting_Accuracy"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Ad_Spend_Tracker"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Weekly_KPI"] { display: none !important; }
    [data-testid="stSidebarNav"] a[href*="Weekly_Team_KPI"] { display: none !important; }
</style>
"""
