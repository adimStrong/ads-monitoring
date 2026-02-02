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
EXCLUDED_PERSONS = []

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
    {"name": "INDIVIDUAL KPI", "gid": 1788804487},
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
