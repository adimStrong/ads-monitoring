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

# Agent Configuration
AGENTS = [
    {"name": "MIKA", "sheet_performance": "MIKA", "sheet_content": "Mika content"},
    {"name": "SHEENA", "sheet_performance": "SHEENA", "sheet_content": "Sheena content"},
    {"name": "ADRIAN", "sheet_performance": "ADRIAN", "sheet_content": "Adrian content"},
    {"name": "JOMAR", "sheet_performance": "JOMAR", "sheet_content": "Jomar content"},
    {"name": "SHILA", "sheet_performance": "SHILA", "sheet_content": "Shila content"},
    {"name": "KRISSA", "sheet_performance": "KRISSA", "sheet_content": "Krissa content"},
]

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
