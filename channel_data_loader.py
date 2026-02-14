"""
Channel Data Loader for FB and Google Channel ROI Dashboard
Loads data from Google Sheets containing FB Summary and Google Summary
"""
import os
import sys
import json
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    CHANNEL_ROI_SHEET_ID, CHANNEL_ROI_SERVICE_ACCOUNT,
    CHANNEL_FB_SHEET, CHANNEL_GOOGLE_SHEET,
    CHANNEL_DATE_FORMAT, GOOGLE_REPORT_SECTIONS,
    CHANNEL_FB_DAILY_ROI_COLUMNS,
    CHANNEL_FB_ROLL_BACK_COLUMNS,
    CHANNEL_FB_VIOLET_COLUMNS,
    CHANNEL_GOOGLE_DAILY_ROI_COLUMNS,
    CHANNEL_GOOGLE_ROLL_BACK_COLUMNS,
    CHANNEL_GOOGLE_VIOLET_COLUMNS,
    CHANNEL_FB_HEADER_ROW, CHANNEL_FB_DATA_START_ROW,
    FACEBOOK_ADS_CREDENTIALS_FILE,
    FACEBOOK_ADS_SHEET_ID,
    COUNTERPART_SHEET,
    COUNTERPART_FB_COLUMNS,
    COUNTERPART_GOOGLE_COLUMNS,
    COUNTERPART_DATA_START_ROW,
    TEAM_CHANNEL_SHEET,
    TEAM_CHANNEL_COLUMNS,
    TEAM_CHANNEL_DATA_START_ROW,
    UPDATED_ACCOUNTS_SHEET_ID,
    UPDATED_ACCOUNTS_FB_TAB,
    UPDATED_ACCOUNTS_BM_TAB,
    UPDATED_ACCOUNTS_PAGES_TAB,
    UPDATED_ACCOUNTS_FB_COLUMNS,
    UPDATED_ACCOUNTS_BM_COLUMNS,
    UPDATED_ACCOUNTS_PAGES_COLUMNS,
    AGENT_PERFORMANCE_TABS,
    AGENT_PERF_OVERALL_COLUMNS,
    AGENT_PERF_MONTHLY_DATA_START,
    AGENT_PERF_MONTHLY_DATA_END,
    AGENT_PERF_DAILY_LABEL_ROW,
    AGENT_PERF_DAILY_DATA_START,
    AGENT_PERF_AD_ACCOUNT_START_COL,
    AGENT_PERF_AD_ACCOUNT_STRIDE,
    INDIVIDUAL_KPI_SHEET_ID,
    INDIVIDUAL_KPI_GID,
    INDIVIDUAL_KPI_AGENTS,
    INDIVIDUAL_KPI_COL_OFFSETS,
    INDIVIDUAL_KPI_DATA_START_ROW,
    EXCLUDED_PERSONS,
    KPI_PHP_USD_RATE,
    KPI_SCORING,
    KPI_SHEET_ID,
    KPI_AGENT_TABS,
    ACCOUNT_DEV_ROW,
    CREATED_ASSETS_TAB,
    CREATED_ASSETS_COLUMNS,
    CREATED_ASSETS_HEADER_ROW,
    CREATED_ASSETS_DATA_START,
    AB_TESTING_TAB,
    AB_TESTING_ROW,
    REPORTING_ROW,
)


def get_google_client():
    """
    Get authenticated Google Sheets client using service account.

    Returns:
        gspread.Client: Authenticated gspread client
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        # Try environment variable first (for Railway/cloud deployment)
        google_creds_json = os.getenv('GOOGLE_CREDENTIALS')
        if google_creds_json:
            try:
                creds_dict = json.loads(google_creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                print("[OK] Using GOOGLE_CREDENTIALS environment variable")
            except json.JSONDecodeError as e:
                print(f"[ERROR] Error parsing GOOGLE_CREDENTIALS JSON: {e}")
                return None
        else:
            # Fall back to credentials file (local development)
            creds_file = os.path.join(os.path.dirname(__file__), FACEBOOK_ADS_CREDENTIALS_FILE)
            if not os.path.exists(creds_file):
                print(f"[WARNING] Credentials file not found: {creds_file}")
                st.warning("No Google credentials found. Set GOOGLE_CREDENTIALS env var or add credentials.json file.")
                return None
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
            print("[OK] Using local credentials file")

        client = gspread.authorize(creds)
        return client

    except Exception as e:
        print(f"[ERROR] Failed to get Google client: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_date(date_str):
    """
    Parse date from various formats including MM/DD/YYYY.

    Args:
        date_str: Date string to parse

    Returns:
        datetime or None
    """
    if pd.isna(date_str) or str(date_str).strip() == '':
        return None

    date_str = str(date_str).strip()

    # Skip header rows
    if any(keyword in date_str.upper() for keyword in ['MONTH', 'DATE', 'GOOGLE', 'CHANNEL', 'REPORT']):
        return None

    # Current year for dates without year
    current_year = datetime.now().year

    formats = [
        '%m/%d/%Y',    # 9/21/2025
        '%m/%d/%y',    # 9/21/25
        '%Y-%m-%d',    # 2025-09-21
        '%d/%m/%Y',    # 21/9/2025
        '%m-%d-%Y',    # 9-21-2025
        '%B %d, %Y',   # September 21, 2025
        '%b %d, %Y',   # Sep 21, 2025
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Handle 2-digit year
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            return dt
        except:
            continue

    return None


def parse_numeric(value, default=0):
    """Parse numeric value from string, handling currency symbols and commas."""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        # Remove currency symbols, commas, and whitespace
        cleaned = str(value).replace(',', '').replace('$', '').replace('₱', '').replace('%', '').strip()
        return float(cleaned) if cleaned else default
    except:
        return default


def is_section_header(row):
    """Check if a row is a section header (like 'GOOGLE CHANNEL REPORT (DAILY ROI)').

    Note: Headers are in column B (index 1), not column A.
    """
    if not row or len(row) < 2:
        return False

    # Check column B (index 1) where headers are located
    cell_b = str(row[1]).strip().upper() if len(row) > 1 else ''
    cell_a = str(row[0]).strip().upper()

    # Check both columns for section headers
    for cell in [cell_b, cell_a]:
        if any(section.upper() in cell for section in GOOGLE_REPORT_SECTIONS):
            return True
    return False


def get_section_name(row):
    """Extract section name from header row.

    Note: Headers are in column B (index 1), not column A.
    """
    if not row or len(row) < 2:
        return None

    # Check column B (index 1) first, then column A
    cell_b = str(row[1]).strip() if len(row) > 1 else ''
    cell_a = str(row[0]).strip()

    for cell in [cell_b, cell_a]:
        for section in GOOGLE_REPORT_SECTIONS:
            if section.upper() in cell.upper():
                return section
    return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_fb_channel_data():
    """
    Load Facebook Summary with 3 report sections from Google Sheet.

    The sheet has 3 sections in DIFFERENT COLUMNS:
    1. DAILY ROI: Columns B-L (index 1-11)
    2. ROLL BACK: Columns N-X (index 13-23)
    3. VIOLET: Columns Z-AF (index 25-31)

    Data starts at row 5 (index 4).

    Returns:
        dict: {'daily_roi': DataFrame, 'roll_back': DataFrame, 'violet': DataFrame}
    """
    try:
        client = get_google_client()
        if client is None:
            return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.worksheet(CHANNEL_FB_SHEET['name'])

        all_data = worksheet.get_all_values()

        # Data starts at row 5 (index 4)
        data_start_idx = CHANNEL_FB_DATA_START_ROW - 1

        if len(all_data) <= data_start_idx:
            print("[WARNING] FB Summary sheet has no data")
            return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}

        data_rows = all_data[data_start_idx:]
        result = {}

        # Parse FB DAILY ROI (Columns B-L)
        cols = CHANNEL_FB_DAILY_ROI_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': int(parse_numeric(row[cols['register']])),
                'ftd': int(parse_numeric(row[cols['ftd']])),
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),
                'conversion_ratio': parse_numeric(row[cols.get('conversion_ratio', 7)]) if 'conversion_ratio' in cols else 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),
                'cpftd': parse_numeric(row[cols.get('cpftd', 9)]) if 'cpftd' in cols else 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': parse_numeric(row[cols.get('cpm', 11)]) if 'cpm' in cols else 0,
                'channel': 'Facebook',
                'section': 'daily_roi',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['daily_roi'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} FB Daily ROI records")

        # Parse FB ROLL BACK (Columns N-X)
        cols = CHANNEL_FB_ROLL_BACK_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': int(parse_numeric(row[cols['register']])),
                'ftd': int(parse_numeric(row[cols['ftd']])),
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),
                'conversion_ratio': parse_numeric(row[cols.get('conversion_ratio', 19)]) if 'conversion_ratio' in cols else 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),
                'cpftd': parse_numeric(row[cols.get('cpftd', 21)]) if 'cpftd' in cols else 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': parse_numeric(row[cols.get('cpm', 23)]) if 'cpm' in cols else 0,
                'channel': 'Facebook',
                'section': 'roll_back',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['roll_back'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} FB Roll Back records")

        # Parse FB VIOLET (Columns Z-AF) - Different structure!
        cols = CHANNEL_FB_VIOLET_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': 0,  # Violet doesn't have register
                'ftd': int(parse_numeric(row[cols['ftd']])),  # FIRST RECHARGE
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),  # RECHARGE AMOUNT
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),  # ARPPU
                'conversion_ratio': 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),  # COST PER RECHARGE
                'cpftd': 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': 0,
                'channel': 'Facebook',
                'section': 'violet',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['violet'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} FB Violet records")

        return result

    except Exception as e:
        print(f"[ERROR] Failed to load FB channel data: {e}")
        import traceback
        traceback.print_exc()
        return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_google_channel_data():
    """
    Load Google Summary with 3 report sections from Google Sheet.

    The sheet has 3 sections in DIFFERENT COLUMNS:
    1. DAILY ROI: Columns B-L (index 1-11)
    2. ROLL BACK: Columns N-W (index 13-22)
    3. VIOLET: Columns Y-AE (index 24-30)

    Data starts at row 4 (index 3).

    Returns:
        dict: {'daily_roi': DataFrame, 'roll_back': DataFrame, 'violet': DataFrame}
    """
    try:
        client = get_google_client()
        if client is None:
            return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.worksheet(CHANNEL_GOOGLE_SHEET['name'])

        all_data = worksheet.get_all_values()

        # Data starts at row 4 (index 3)
        data_start_idx = 3

        if len(all_data) <= data_start_idx:
            print("[WARNING] Google Summary sheet has no data")
            return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}

        data_rows = all_data[data_start_idx:]
        result = {}

        # Parse DAILY ROI (Columns B-L)
        cols = CHANNEL_GOOGLE_DAILY_ROI_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': int(parse_numeric(row[cols['register']])),
                'ftd': int(parse_numeric(row[cols['ftd']])),
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),
                'conversion_ratio': parse_numeric(row[cols.get('conversion_ratio', 7)]) if 'conversion_ratio' in cols else 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),
                'cpftd': parse_numeric(row[cols.get('cpftd', 9)]) if 'cpftd' in cols else 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': parse_numeric(row[cols.get('cpm', 11)]) if 'cpm' in cols else 0,
                'channel': 'Google',
                'section': 'daily_roi',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['daily_roi'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} Google Daily ROI records")

        # Parse ROLL BACK (Columns N-W)
        cols = CHANNEL_GOOGLE_ROLL_BACK_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': int(parse_numeric(row[cols['register']])),
                'ftd': int(parse_numeric(row[cols['ftd']])),
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),
                'conversion_ratio': 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),
                'cpftd': parse_numeric(row[cols.get('cpftd', 20)]) if 'cpftd' in cols else 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': parse_numeric(row[cols.get('cpm', 22)]) if 'cpm' in cols else 0,
                'channel': 'Google',
                'section': 'roll_back',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['roll_back'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} Google Roll Back records")

        # Parse VIOLET (Columns Y-AE) - Different structure!
        cols = CHANNEL_GOOGLE_VIOLET_COLUMNS
        records = []
        for row in data_rows:
            if len(row) <= max(cols.values()):
                continue
            date_val = parse_date(row[cols['date']])
            if not date_val:
                continue
            records.append({
                'date': date_val,
                'register': 0,  # Violet doesn't have register
                'ftd': int(parse_numeric(row[cols['ftd']])),  # FIRST RECHARGE
                'ftd_recharge': parse_numeric(row[cols['ftd_recharge']]),  # RECHARGE AMOUNT
                'avg_recharge': parse_numeric(row[cols['avg_recharge']]),  # ARPPU
                'conversion_ratio': 0,
                'cost': parse_numeric(row[cols['cost']]),
                'cpr': parse_numeric(row[cols['cpr']]),  # COST PER RECHARGE
                'cpftd': 0,
                'roas': parse_numeric(row[cols['roas']]),
                'cpm': 0,
                'channel': 'Google',
                'section': 'violet',
                'deposit_amount': parse_numeric(row[cols['ftd_recharge']]),
            })
        result['violet'] = pd.DataFrame(records) if records else pd.DataFrame()
        print(f"[OK] Loaded {len(records)} Google Violet records")

        return result

    except Exception as e:
        print(f"[ERROR] Failed to load Google channel data: {e}")
        import traceback
        traceback.print_exc()
        return {'daily_roi': pd.DataFrame(), 'roll_back': pd.DataFrame(), 'violet': pd.DataFrame()}


def combine_all_channel_data():
    """
    Combine FB and all Google channel data into a single DataFrame.

    Returns:
        DataFrame with all channel data combined
    """
    all_data = []

    # Load FB data (now returns dict with 3 sections)
    fb_data = load_fb_channel_data()
    for key, df in fb_data.items():
        if not df.empty:
            all_data.append(df)

    # Load Google data
    google_data = load_google_channel_data()
    for key, df in google_data.items():
        if not df.empty:
            all_data.append(df)

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    return combined


def aggregate_daily(df):
    """
    Aggregate data by date (daily summary).

    Args:
        df: DataFrame with channel data

    Returns:
        DataFrame aggregated by date
    """
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date_only'] = pd.to_datetime(df['date']).dt.date

    agg_df = df.groupby('date_only').agg({
        'register': 'sum',
        'ftd': 'sum',
        'deposit_amount': 'sum',
        'cost': 'sum',
    }).reset_index()

    # Calculate derived metrics
    agg_df['cpr'] = agg_df.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(lambda x: x['deposit_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    agg_df = agg_df.sort_values('date_only')
    return agg_df


def aggregate_weekly(df):
    """
    Aggregate data by week.

    Args:
        df: DataFrame with channel data

    Returns:
        DataFrame aggregated by week
    """
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['week'] = df['date'].dt.isocalendar().week
    df['year'] = df['date'].dt.isocalendar().year
    df['week_label'] = df.apply(lambda x: f"{x['year']}-W{x['week']:02d}", axis=1)

    agg_df = df.groupby('week_label').agg({
        'register': 'sum',
        'ftd': 'sum',
        'deposit_amount': 'sum',
        'cost': 'sum',
    }).reset_index()

    # Calculate derived metrics
    agg_df['cpr'] = agg_df.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(lambda x: x['deposit_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    agg_df = agg_df.sort_values('week_label')
    return agg_df


def aggregate_monthly(df):
    """
    Aggregate data by month.

    Args:
        df: DataFrame with channel data

    Returns:
        DataFrame aggregated by month
    """
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    agg_df = df.groupby('month').agg({
        'register': 'sum',
        'ftd': 'sum',
        'deposit_amount': 'sum',
        'cost': 'sum',
    }).reset_index()

    # Calculate derived metrics
    agg_df['cpr'] = agg_df.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(lambda x: x['deposit_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    # Convert period to string for display
    agg_df['month_str'] = agg_df['month'].astype(str)
    agg_df = agg_df.sort_values('month')

    return agg_df


def aggregate_by_channel(df):
    """
    Aggregate data by channel (FB vs Google).

    Args:
        df: DataFrame with channel data

    Returns:
        DataFrame aggregated by channel
    """
    if df.empty or 'channel' not in df.columns:
        return pd.DataFrame()

    agg_df = df.groupby('channel').agg({
        'register': 'sum',
        'ftd': 'sum',
        'deposit_amount': 'sum',
        'cost': 'sum',
    }).reset_index()

    # Calculate derived metrics
    agg_df['cpr'] = agg_df.apply(lambda x: x['cost'] / x['register'] if x['register'] > 0 else 0, axis=1)
    agg_df['roas'] = agg_df.apply(lambda x: x['deposit_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

    return agg_df


def get_date_range(df):
    """Get min and max dates from dataframe."""
    if df.empty or 'date' not in df.columns:
        return None, None

    df['date'] = pd.to_datetime(df['date'])
    min_date = df['date'].min()
    max_date = df['date'].max()

    return min_date, max_date


def refresh_channel_data():
    """Clear cache to force data refresh."""
    load_fb_channel_data.clear()
    load_google_channel_data.clear()


def is_date_header(text):
    """Check if text is a date header like 'January 27' or 'February 1'."""
    if not text or not isinstance(text, str):
        return False
    return bool(re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', text.strip()))


def parse_date_header(text):
    """Parse date header like 'January 27' to datetime."""
    try:
        # Add current year
        current_year = datetime.now().year
        return datetime.strptime(f"{text.strip()}, {current_year}", "%B %d, %Y")
    except:
        return None


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_counterpart_data():
    """
    Load Counterpart Performance data from Google Sheets.

    The sheet has:
    1. OVERALL PERFORMANCE section at top (rows 3-11) with totals
    2. Daily sections with date headers like "January 27"

    Returns:
        dict: {
            'fb': DataFrame (daily data),
            'google': DataFrame (daily data),
            'fb_overall': DataFrame (overall totals),
            'google_overall': DataFrame (overall totals)
        }
    """
    try:
        client = get_google_client()
        if client is None:
            return {'fb': pd.DataFrame(), 'google': pd.DataFrame(),
                    'fb_overall': pd.DataFrame(), 'google_overall': pd.DataFrame()}

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(COUNTERPART_SHEET['gid'])
        all_data = worksheet.get_all_values()

        fb_records = []
        google_records = []
        fb_overall_records = []
        google_overall_records = []
        current_date = None
        in_overall_section = False

        for row_idx, row in enumerate(all_data):
            # Check column B (index 1) - column A is empty
            cell_b = str(row[1]).strip() if len(row) > 1 else ''

            # Detect OVERALL PERFORMANCE section
            if 'OVERALL PERFORMANCE' in cell_b:
                in_overall_section = True
                continue

            # Skip header rows
            if '渠道来源' in cell_b or 'Channel Source' in cell_b:
                continue

            # Detect date header - marks end of OVERALL section
            if is_date_header(cell_b):
                in_overall_section = False
                current_date = parse_date_header(cell_b)
                continue

            # Skip empty rows
            if not cell_b:
                continue

            # Parse FB data (columns B-H, index 1-7)
            fb_cols = COUNTERPART_FB_COLUMNS
            if len(row) > max(fb_cols.values()):
                channel = str(row[fb_cols['channel_source']]).strip()
                first_recharge = parse_numeric(row[fb_cols['first_recharge']])
                if channel and first_recharge > 0:
                    record = {
                        'channel': channel,
                        'first_recharge': int(first_recharge),
                        'total_amount': parse_numeric(row[fb_cols['total_amount']]),
                        'arppu': parse_numeric(row[fb_cols['arppu']]),
                        'spending': parse_numeric(row[fb_cols['spending']]),
                        'cost_per_recharge': parse_numeric(row[fb_cols['cost_per_recharge']]),
                        'roas': parse_numeric(row[fb_cols['roas']]),
                    }
                    if in_overall_section:
                        fb_overall_records.append(record)
                    elif current_date is not None:
                        record['date'] = current_date
                        fb_records.append(record)

            # Parse Google data (columns J-P, index 9-15)
            google_cols = COUNTERPART_GOOGLE_COLUMNS
            if len(row) > max(google_cols.values()):
                channel = str(row[google_cols['channel_source']]).strip()
                first_recharge = parse_numeric(row[google_cols['first_recharge']])
                if channel and first_recharge > 0:
                    record = {
                        'channel': channel,
                        'first_recharge': int(first_recharge),
                        'total_amount': parse_numeric(row[google_cols['total_amount']]),
                        'arppu': parse_numeric(row[google_cols['arppu']]),
                        'spending': parse_numeric(row[google_cols['spending']]),
                        'cost_per_recharge': parse_numeric(row[google_cols['cost_per_recharge']]),
                        'roas': parse_numeric(row[google_cols['roas']]),
                    }
                    if in_overall_section:
                        google_overall_records.append(record)
                    elif current_date is not None:
                        record['date'] = current_date
                        google_records.append(record)

        fb_df = pd.DataFrame(fb_records) if fb_records else pd.DataFrame()
        google_df = pd.DataFrame(google_records) if google_records else pd.DataFrame()
        fb_overall_df = pd.DataFrame(fb_overall_records) if fb_overall_records else pd.DataFrame()
        google_overall_df = pd.DataFrame(google_overall_records) if google_overall_records else pd.DataFrame()

        print(f"[OK] Loaded {len(fb_records)} Counterpart FB daily records")
        print(f"[OK] Loaded {len(google_records)} Counterpart Google daily records")
        print(f"[OK] Loaded {len(fb_overall_records)} Counterpart FB overall records")
        print(f"[OK] Loaded {len(google_overall_records)} Counterpart Google overall records")

        return {
            'fb': fb_df,
            'google': google_df,
            'fb_overall': fb_overall_df,
            'google_overall': google_overall_df
        }

    except Exception as e:
        print(f"[ERROR] Failed to load Counterpart data: {e}")
        import traceback
        traceback.print_exc()
        return {'fb': pd.DataFrame(), 'google': pd.DataFrame(),
                'fb_overall': pd.DataFrame(), 'google_overall': pd.DataFrame()}


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_team_channel_data():
    """
    Load Team Channel data from Google Sheets.

    Sheet structure:
    - Rows 1-15: OVERALL section (team names in col B, channel in col C, data in D-H)
      + Also PER TEAM OVERALL section in columns I-P
    - Then empty rows
    - Then "DAILY SUMMARY REFERRAL CHANNEL REPORT" header
    - Then daily sections with date headers like "January 28" in col C
    - Daily data: no team name, just channel + metrics in C-H

    Returns:
        dict: {
            'overall': DataFrame (overall per-team per-channel totals),
            'daily': DataFrame (daily channel-level data)
        }
    """
    try:
        client = get_google_client()
        if client is None:
            return {'overall': pd.DataFrame(), 'daily': pd.DataFrame()}

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(TEAM_CHANNEL_SHEET['gid'])
        all_data = worksheet.get_all_values()

        overall_records = []
        daily_records = []
        current_date = None
        cols = TEAM_CHANNEL_COLUMNS

        # Keywords to skip (lowercase)
        skip_keywords = [
            '渠道来源', 'channel source', 'overall channel statistics report',
            'per team overall channel statistics report',
            'per team over all channel statistics report',
            'daily summary referral channel report',
            'weekly summary referral channel report',
            'cost', 'team',
        ]

        def is_skip_header(text):
            """Check if text is a section/column header to skip."""
            t = text.lower().strip()
            for kw in skip_keywords:
                if kw in t:
                    return True
            return False

        in_daily_section = False

        for row_idx, row in enumerate(all_data):
            if not row or len(row) <= cols['arppu']:
                continue

            team_cell = str(row[cols['team_name']]).strip() if len(row) > cols['team_name'] else ''
            channel_cell = str(row[cols['channel_source']]).strip() if len(row) > cols['channel_source'] else ''

            # Check for "DAILY SUMMARY" marker
            if 'daily summary' in channel_cell.lower():
                in_daily_section = True
                continue

            # Check if channel cell is a date header (in daily section)
            if is_date_header(channel_cell):
                current_date = parse_date_header(channel_cell)
                in_daily_section = True
                continue

            # Skip header rows
            if is_skip_header(channel_cell) or is_skip_header(team_cell):
                continue

            # Skip empty channel rows
            if not channel_cell:
                continue

            # Skip if channel source doesn't look like a DEERPROMO channel
            if not channel_cell.startswith('FB-FB-FB-DEERPROMO'):
                continue

            # Parse data
            cost = parse_numeric(row[cols['cost']])
            registrations = parse_numeric(row[cols['registrations']])
            first_recharge = parse_numeric(row[cols['first_recharge']])
            total_amount = parse_numeric(row[cols['total_amount']])
            arppu = parse_numeric(row[cols['arppu']])

            # Only add rows with some actual data
            if cost > 0 or registrations > 0 or first_recharge > 0:
                if in_daily_section and current_date is not None:
                    # Daily data (no team)
                    daily_records.append({
                        'date': current_date,
                        'team': team_cell if team_cell else 'All',
                        'channel': channel_cell,
                        'cost': cost,
                        'registrations': int(registrations),
                        'first_recharge': int(first_recharge),
                        'total_amount': total_amount,
                        'arppu': arppu,
                    })
                elif not in_daily_section and team_cell:
                    # Overall section (has team)
                    overall_records.append({
                        'team': team_cell,
                        'channel': channel_cell,
                        'cost': cost,
                        'registrations': int(registrations),
                        'first_recharge': int(first_recharge),
                        'total_amount': total_amount,
                        'arppu': arppu,
                    })

        overall_df = pd.DataFrame(overall_records)
        daily_df = pd.DataFrame(daily_records)

        if not daily_df.empty:
            daily_df['date'] = pd.to_datetime(daily_df['date'])
            daily_df['cpr'] = daily_df.apply(
                lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
            daily_df['cpfd'] = daily_df.apply(
                lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
            daily_df['roas'] = daily_df.apply(
                lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

        if not overall_df.empty:
            overall_df['cpr'] = overall_df.apply(
                lambda x: x['cost'] / x['registrations'] if x['registrations'] > 0 else 0, axis=1)
            overall_df['cpfd'] = overall_df.apply(
                lambda x: x['cost'] / x['first_recharge'] if x['first_recharge'] > 0 else 0, axis=1)
            overall_df['roas'] = overall_df.apply(
                lambda x: x['total_amount'] / x['cost'] if x['cost'] > 0 else 0, axis=1)

        print(f"[OK] Loaded {len(overall_records)} Team Channel overall records")
        print(f"[OK] Loaded {len(daily_records)} Team Channel daily records")

        return {'overall': overall_df, 'daily': daily_df}

    except Exception as e:
        print(f"[ERROR] Failed to load Team Channel data: {e}")
        import traceback
        traceback.print_exc()
        return {'overall': pd.DataFrame(), 'daily': pd.DataFrame()}


def refresh_team_channel_data():
    """Clear Team Channel data cache."""
    load_team_channel_data.clear()


def refresh_counterpart_data():
    """Clear counterpart data cache."""
    load_counterpart_data.clear()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_updated_accounts_data():
    """
    Load Updated Accounts data from separate spreadsheet with 3 tabs.

    Tabs: FB accounts, BM, Pages

    Returns:
        dict with 3 DataFrames: fb_accounts, bm, pages
    """
    empty = {'fb_accounts': pd.DataFrame(), 'bm': pd.DataFrame(), 'pages': pd.DataFrame()}
    try:
        client = get_google_client()
        if client is None:
            return empty

        spreadsheet = client.open_by_key(UPDATED_ACCOUNTS_SHEET_ID)

        def safe_get(row, idx):
            if idx < len(row):
                return str(row[idx]).strip()
            return ''

        def mask_password(val):
            if val and val not in ('', '-', 'N/A', 'n/a'):
                return '********'
            return val

        # --- FB accounts tab ---
        fb_cols = UPDATED_ACCOUNTS_FB_COLUMNS
        ws_fb = spreadsheet.get_worksheet_by_id(UPDATED_ACCOUNTS_FB_TAB['gid'])
        fb_data = ws_fb.get_all_values()
        fb_records = []
        for row in fb_data[1:]:  # Skip header
            employee = safe_get(row, fb_cols['employee'])
            if not employee:
                continue
            fb_records.append({
                'Employee': employee,
                'FB Name': safe_get(row, fb_cols['fb_name']),
                'Facebook User': safe_get(row, fb_cols['fb_user']),
                'Password': mask_password(safe_get(row, fb_cols['password'])),
            })
        print(f"[OK] Loaded {len(fb_records)} FB account records")

        # --- BM tab ---
        bm_cols = UPDATED_ACCOUNTS_BM_COLUMNS
        ws_bm = spreadsheet.get_worksheet_by_id(UPDATED_ACCOUNTS_BM_TAB['gid'])
        bm_data = ws_bm.get_all_values()
        bm_records = []
        for row in bm_data[1:]:
            employee = safe_get(row, bm_cols['employee'])
            if not employee:
                continue
            bm_records.append({
                'Employee': employee,
                'BM Name': safe_get(row, bm_cols['bm_name']),
            })
        print(f"[OK] Loaded {len(bm_records)} BM records")

        # --- Pages tab ---
        pg_cols = UPDATED_ACCOUNTS_PAGES_COLUMNS
        ws_pg = spreadsheet.get_worksheet_by_id(UPDATED_ACCOUNTS_PAGES_TAB['gid'])
        pg_data = ws_pg.get_all_values()
        pg_records = []
        for row in pg_data[1:]:
            employee = safe_get(row, pg_cols['employee'])
            if not employee:
                continue
            pg_records.append({
                'Employee': employee,
                'Page Name': safe_get(row, pg_cols['page_name']),
            })
        print(f"[OK] Loaded {len(pg_records)} Pages records")

        return {
            'fb_accounts': pd.DataFrame(fb_records) if fb_records else pd.DataFrame(),
            'bm': pd.DataFrame(bm_records) if bm_records else pd.DataFrame(),
            'pages': pd.DataFrame(pg_records) if pg_records else pd.DataFrame(),
        }

    except Exception as e:
        print(f"[ERROR] Failed to load Updated Accounts data: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"Failed to load Updated Accounts: {e}")
        return empty


def refresh_updated_accounts_data():
    """Clear Updated Accounts data cache."""
    load_updated_accounts_data.clear()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_created_assets_data():
    """
    Load Created Assets data from Channel ROI sheet.

    Parses the left section (cols B-N) which has a detailed creation log:
    DATE, CREATOR, GMAIL, FB_USERNAME, FB_PAGE, BM_NAME, etc.

    Returns:
        DataFrame with all creation records
    """
    try:
        client = get_google_client()
        if client is None:
            return pd.DataFrame()

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(CREATED_ASSETS_TAB['gid'])
        all_data = worksheet.get_all_values()

        if len(all_data) <= CREATED_ASSETS_DATA_START:
            print("[WARNING] Created Assets tab has no data")
            return pd.DataFrame()

        cols = CREATED_ASSETS_COLUMNS
        records = []

        for row_idx in range(CREATED_ASSETS_DATA_START, len(all_data)):
            row = all_data[row_idx]
            if len(row) <= cols['creator']:
                continue

            creator = str(row[cols['creator']]).strip()
            if not creator:
                continue

            date_val = parse_date(str(row[cols['date']]).strip()) if cols['date'] < len(row) else None

            def safe_get(idx):
                return str(row[idx]).strip() if idx < len(row) else ''

            records.append({
                'date': date_val,
                'creator': creator,
                'gmail': safe_get(cols['gmail']),
                'fb_username': safe_get(cols['fb_username']),
                'fb_condition': safe_get(cols['fb_condition']),
                'fb_page': safe_get(cols['fb_page']),
                'page_condition': safe_get(cols['page_condition']),
                'bm_name': safe_get(cols['bm_name']),
                'bm_condition': safe_get(cols['bm_condition']),
            })

        if not records:
            print("[WARNING] Created Assets: no data rows found")
            return pd.DataFrame()

        df = pd.DataFrame(records)
        print(f"[OK] Created Assets: {len(df)} rows loaded")
        return df

    except Exception as e:
        print(f"[ERROR] Failed to load Created Assets: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def refresh_created_assets_data():
    """Clear Created Assets data cache."""
    load_created_assets_data.clear()


def count_created_assets(assets_df):
    """Count created assets per agent from Created Assets data.

    Args:
        assets_df: DataFrame from load_created_assets_data()

    Returns:
        dict: {agent_upper: {'gmail': N, 'fb_accounts': N, 'fb_pages': N, 'bms': N,
                              'total_accounts': N, 'total_assets': N}}
    """
    if assets_df is None or assets_df.empty:
        return {}

    result = {}

    for _, row in assets_df.iterrows():
        creator = str(row.get('creator', '')).strip().upper()
        if not creator:
            continue

        if creator not in result:
            result[creator] = {
                'gmail': 0, 'fb_accounts': 0, 'fb_pages': 0, 'bms': 0,
                'total_accounts': 0, 'total_assets': 0,
            }

        # Count non-empty fields
        if str(row.get('gmail', '')).strip():
            result[creator]['gmail'] += 1
        if str(row.get('fb_username', '')).strip():
            result[creator]['fb_accounts'] += 1
        if str(row.get('fb_page', '')).strip():
            result[creator]['fb_pages'] += 1
        if str(row.get('bm_name', '')).strip():
            result[creator]['bms'] += 1

    # Calculate totals
    for name in result:
        r = result[name]
        r['total_accounts'] = r['gmail'] + r['fb_accounts']  # for account_dev
        r['total_assets'] = r['fb_pages'] + r['bms']         # for profile_dev

    return result


def score_account_dev(total_accounts):
    """Score Account Dev based on total Gmail + FB accounts created.

    Rubric: 4 if total >= 5, 3 if total >= 3, 2 if total >= 2, 1 if total < 2
    """
    if total_accounts >= 5:
        return 4
    elif total_accounts >= 3:
        return 3
    elif total_accounts >= 2:
        return 2
    return 1


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_ab_testing_data():
    """
    Load A/B Testing data from Text/AbTest tab in Channel ROI sheet.

    The sheet has:
    - Summary section (rows 0-7): Per-agent OUTPUT counts
    - Detail log (rows ~9+): DATE, CREATOR, HEADLINE, PRIMARY TEXT, then daily columns

    We parse the detail log to count published campaigns per advertiser.
    Each advertiser block has columns: AD STRUCTURE, TYPE OF CONTENT, CONDITION, PUBLISHED CAMPAIGN

    Returns:
        dict: {'summary': DataFrame (per-agent totals), 'detail': DataFrame (raw log)}
    """
    empty = {'summary': pd.DataFrame(), 'detail': pd.DataFrame()}
    try:
        client = get_google_client()
        if client is None:
            return empty

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(AB_TESTING_TAB['gid'])
        all_data = worksheet.get_all_values()

        if len(all_data) < 10:
            print("[WARNING] Text/AbTest tab has insufficient rows")
            return empty

        # --- Parse summary section (rows 0-7) ---
        # Row 2 typically: "Primary Text" label, then agent names in cols C-I
        # Row 3: counts
        # Row 4: "Published Ad" label, then counts
        summary_records = []

        # Find agent names from row 1-2 area
        agent_names_row = None
        for r_idx in range(min(5, len(all_data))):
            row = all_data[r_idx]
            # Look for row with agent names (Jason, Ron, etc.)
            names_found = 0
            for cell in row:
                if str(cell).strip().upper() in ['JASON', 'RON', 'MIKA', 'SHILA', 'ADRIAN', 'JOMAR', 'KRISSA']:
                    names_found += 1
            if names_found >= 3:
                agent_names_row = r_idx
                break

        if agent_names_row is not None:
            names_row = all_data[agent_names_row]
            # Map column index to agent name
            agent_cols = {}
            for col_idx, cell in enumerate(names_row):
                name = str(cell).strip().upper()
                if name in ['JASON', 'RON', 'MIKA', 'SHILA', 'ADRIAN', 'JOMAR', 'KRISSA']:
                    agent_cols[col_idx] = name

            # Look for Primary Text and Published Ad rows
            for r_idx in range(agent_names_row + 1, min(agent_names_row + 6, len(all_data))):
                row = all_data[r_idx]
                label = str(row[1]).strip().lower() if len(row) > 1 else ''
                if 'primary text' in label or 'published' in label:
                    metric = 'primary_text' if 'primary' in label else 'published_ad'
                    for col_idx, agent in agent_cols.items():
                        if col_idx < len(row):
                            count = int(parse_numeric(row[col_idx]))
                            summary_records.append({
                                'agent': agent,
                                'metric': metric,
                                'count': count,
                            })

        # --- Parse detail log ---
        # Find the detail section start (look for DATE header)
        detail_start = None
        date_col = 1  # default col B
        creator_col = 2  # default col C
        headline_col = 3  # default col D
        primary_text_col = 4  # default col E
        advertiser_col = 8  # default col I

        for r_idx in range(5, min(15, len(all_data))):
            row = all_data[r_idx]
            for c_idx, cell in enumerate(row):
                if str(cell).strip().upper() == 'DATE':
                    date_col = c_idx
                    detail_start = r_idx + 1
                    break
                if str(cell).strip().upper() == 'CREATOR':
                    creator_col = c_idx
            if detail_start is not None:
                break

        # Also find ADVERTISER NAME column and daily date columns
        if detail_start is not None and detail_start > 0:
            header_row = all_data[detail_start - 1]
            for c_idx, cell in enumerate(header_row):
                upper = str(cell).strip().upper()
                if upper == 'CREATOR':
                    creator_col = c_idx
                elif upper == 'HEADLINE':
                    headline_col = c_idx
                elif 'CREATED PRIMARY' in upper or 'PRIMARY TEXT' in upper:
                    primary_text_col = c_idx
                elif 'ADVERTISER' in upper:
                    advertiser_col = c_idx

        detail_records = []
        if detail_start is not None:
            # Find daily date column blocks (after ADVERTISER NAME)
            # Each date has 4 sub-columns: AD STRUCTURE, TYPE, CONDITION, PUBLISHED CAMPAIGN
            # The date headers are in the row BEFORE the column headers
            date_header_row = all_data[detail_start - 2] if detail_start >= 2 else []
            daily_dates = []
            for c_idx in range(advertiser_col + 1, len(date_header_row)):
                cell = str(date_header_row[c_idx]).strip()
                dt = parse_date(cell)
                if dt:
                    daily_dates.append({'col': c_idx, 'date': dt})

            current_date = None
            current_creator = None

            for r_idx in range(detail_start, len(all_data)):
                row = all_data[r_idx]
                if len(row) <= advertiser_col:
                    continue

                # Check for date in date column
                date_val = parse_date(str(row[date_col]).strip()) if date_col < len(row) else None
                if date_val:
                    current_date = date_val

                creator = str(row[creator_col]).strip() if creator_col < len(row) else ''
                if creator:
                    current_creator = creator

                headline = str(row[headline_col]).strip() if headline_col < len(row) else ''
                primary_text = str(row[primary_text_col]).strip() if primary_text_col < len(row) else ''
                advertiser = str(row[advertiser_col]).strip() if advertiser_col < len(row) else ''

                # Skip empty rows
                if not headline and not primary_text and not advertiser:
                    continue

                # Count published campaigns from daily columns
                total_published = 0
                for dd in daily_dates:
                    pub_col = dd['col'] + 3  # PUBLISHED CAMPAIGN is 4th sub-column (offset +3)
                    if pub_col < len(row):
                        pub_count = int(parse_numeric(row[pub_col]))
                        total_published += pub_count

                detail_records.append({
                    'batch_date': current_date,
                    'creator': current_creator or creator,
                    'headline': headline,
                    'primary_text': primary_text,
                    'advertiser': advertiser,
                    'total_published': total_published,
                })

        summary_df = pd.DataFrame(summary_records) if summary_records else pd.DataFrame()
        detail_df = pd.DataFrame(detail_records) if detail_records else pd.DataFrame()

        print(f"[OK] AB Testing: {len(summary_records)} summary rows, {len(detail_records)} detail rows")
        return {'summary': summary_df, 'detail': detail_df}

    except Exception as e:
        print(f"[ERROR] Failed to load AB Testing data: {e}")
        import traceback
        traceback.print_exc()
        return empty


def refresh_ab_testing_data():
    """Clear AB Testing data cache."""
    load_ab_testing_data.clear()


def count_ab_testing(ab_data):
    """Count A/B testing metrics per agent from Text/AbTest data.

    Args:
        ab_data: dict from load_ab_testing_data()

    Returns:
        dict: {agent_upper: {'primary_text': N, 'published_ad': N, 'total_published': N}}
    """
    result = {}
    summary_df = ab_data.get('summary', pd.DataFrame())
    detail_df = ab_data.get('detail', pd.DataFrame())

    # From summary section
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            agent = str(row.get('agent', '')).strip().upper()
            metric = row.get('metric', '')
            count = int(row.get('count', 0))
            if not agent:
                continue
            if agent not in result:
                result[agent] = {'primary_text': 0, 'published_ad': 0, 'total_published': 0}
            if metric == 'primary_text':
                result[agent]['primary_text'] = count
            elif metric == 'published_ad':
                result[agent]['published_ad'] = count

    # From detail section - count total published per advertiser
    if not detail_df.empty:
        for _, row in detail_df.iterrows():
            advertiser = str(row.get('advertiser', '')).strip().upper()
            published = int(row.get('total_published', 0))
            if not advertiser or published == 0:
                continue
            if advertiser not in result:
                result[advertiser] = {'primary_text': 0, 'published_ad': 0, 'total_published': 0}
            result[advertiser]['total_published'] += published

    # Use published_ad from summary as the scoring metric (if available),
    # otherwise use total_published from detail
    for agent in result:
        if result[agent]['published_ad'] == 0:
            result[agent]['published_ad'] = result[agent]['total_published']

    return result


def score_ab_testing(published_count):
    """Score A/B Testing based on published campaign count.

    Rubric: 4 if >= 20, 3 if >= 11, 2 if >= 6, 1 if < 6
    """
    if published_count >= 20:
        return 4
    elif published_count >= 11:
        return 3
    elif published_count >= 6:
        return 2
    return 1


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_agent_performance_data():
    """
    Load Agent Performance data from P-tabs (P6-P13) in Channel ROI sheet.

    Each tab has:
    - Monthly summary (rows 3-6, cols 0-12)
    - Daily overall data (rows 10+, cols 0-12)
    - Ad account data (row 8 has names, rows 10+ cols 14+ with stride 5)

    Returns:
        dict: {'monthly': DataFrame, 'daily': DataFrame, 'ad_accounts': DataFrame}
    """
    empty = {'monthly': pd.DataFrame(), 'daily': pd.DataFrame(), 'ad_accounts': pd.DataFrame()}
    try:
        client = get_google_client()
        if client is None:
            return empty

        spreadsheet = client.open_by_key(CHANNEL_ROI_SHEET_ID)
        cols = AGENT_PERF_OVERALL_COLUMNS

        monthly_records = []
        daily_records = []
        ad_account_records = []
        errors = []

        for tab_info in AGENT_PERFORMANCE_TABS:
            agent = tab_info['agent']
            try:
                worksheet = spreadsheet.get_worksheet_by_id(tab_info['gid'])
                all_data = worksheet.get_all_values()
            except Exception as e:
                msg = f"Could not load tab {tab_info['name']}: {e}"
                print(f"[WARNING] {msg}")
                errors.append(msg)
                continue

            if len(all_data) < AGENT_PERF_DAILY_DATA_START + 1:
                print(f"[WARNING] Tab {tab_info['name']} has insufficient rows")
                continue

            # --- Parse monthly summary (rows 3-6, 0-indexed) ---
            for row_idx in range(AGENT_PERF_MONTHLY_DATA_START, min(AGENT_PERF_MONTHLY_DATA_END, len(all_data))):
                row = all_data[row_idx]
                if len(row) <= cols['roas']:
                    continue
                month_val = str(row[cols['date']]).strip() if len(row) > cols['date'] else ''
                if not month_val:
                    continue
                cost = parse_numeric(row[cols['cost']])
                register = parse_numeric(row[cols['register']])
                # Skip empty months
                if cost == 0 and register == 0:
                    continue
                monthly_records.append({
                    'agent': agent,
                    'month': month_val,
                    'channel': str(row[cols['channel']]).strip() if len(row) > cols['channel'] else '',
                    'cost': cost,
                    'register': int(register),
                    'cpr': parse_numeric(row[cols['cpr']]),
                    'ftd': int(parse_numeric(row[cols['ftd']])),
                    'cpd': parse_numeric(row[cols['cpd']]),
                    'conv_rate': parse_numeric(row[cols['conv_rate']]),
                    'impressions': int(parse_numeric(row[cols['impressions']])),
                    'clicks': int(parse_numeric(row[cols['clicks']])),
                    'ctr': parse_numeric(row[cols['ctr']]),
                    'arppu': parse_numeric(row[cols['arppu']]),
                    'roas': parse_numeric(row[cols['roas']]),
                })

            # --- Parse ad account names from label row ---
            label_row = all_data[AGENT_PERF_DAILY_LABEL_ROW] if len(all_data) > AGENT_PERF_DAILY_LABEL_ROW else []
            ad_accounts = []
            col_idx = AGENT_PERF_AD_ACCOUNT_START_COL
            while col_idx < len(label_row):
                acct_name = str(label_row[col_idx]).strip()
                if acct_name and 'AD ACCOUNT 4' not in acct_name.upper():
                    ad_accounts.append({'name': acct_name, 'col': col_idx})
                elif not acct_name:
                    pass  # skip blank
                col_idx += AGENT_PERF_AD_ACCOUNT_STRIDE

            # --- Parse daily data ---
            for row_idx in range(AGENT_PERF_DAILY_DATA_START, len(all_data)):
                row = all_data[row_idx]
                if len(row) <= cols['roas']:
                    continue

                date_val = parse_date(str(row[cols['date']]).strip())
                if not date_val:
                    continue

                cost = parse_numeric(row[cols['cost']])
                register = parse_numeric(row[cols['register']])
                # Skip future rows with no data
                if cost == 0 and register == 0:
                    continue

                daily_records.append({
                    'agent': agent,
                    'date': date_val,
                    'channel': str(row[cols['channel']]).strip() if len(row) > cols['channel'] else '',
                    'cost': cost,
                    'register': int(register),
                    'cpr': parse_numeric(row[cols['cpr']]),
                    'ftd': int(parse_numeric(row[cols['ftd']])),
                    'cpd': parse_numeric(row[cols['cpd']]),
                    'conv_rate': parse_numeric(row[cols['conv_rate']]),
                    'impressions': int(parse_numeric(row[cols['impressions']])),
                    'clicks': int(parse_numeric(row[cols['clicks']])),
                    'ctr': parse_numeric(row[cols['ctr']]),
                    'arppu': parse_numeric(row[cols['arppu']]),
                    'roas': parse_numeric(row[cols['roas']]),
                })

                # Parse per-ad-account data for this row
                for acct in ad_accounts:
                    ac = acct['col']
                    if ac + 3 >= len(row):
                        continue
                    acct_cost = parse_numeric(row[ac])
                    acct_impressions = parse_numeric(row[ac + 1])
                    acct_clicks = parse_numeric(row[ac + 2])
                    acct_ctr = parse_numeric(row[ac + 3])
                    if acct_cost == 0 and acct_impressions == 0:
                        continue
                    ad_account_records.append({
                        'agent': agent,
                        'date': date_val,
                        'ad_account': acct['name'],
                        'cost': acct_cost,
                        'impressions': int(acct_impressions),
                        'clicks': int(acct_clicks),
                        'ctr': acct_ctr,
                    })

            print(f"[OK] Loaded P-tab {tab_info['name']}: {len([r for r in daily_records if r['agent'] == agent])} daily rows, {len(ad_accounts)} ad accounts")

        monthly_df = pd.DataFrame(monthly_records) if monthly_records else pd.DataFrame()
        daily_df = pd.DataFrame(daily_records) if daily_records else pd.DataFrame()
        ad_accounts_df = pd.DataFrame(ad_account_records) if ad_account_records else pd.DataFrame()

        if not daily_df.empty:
            daily_df['date'] = pd.to_datetime(daily_df['date'])

        if not ad_accounts_df.empty:
            ad_accounts_df['date'] = pd.to_datetime(ad_accounts_df['date'])

        print(f"[OK] Agent Performance totals: {len(monthly_records)} monthly, {len(daily_records)} daily, {len(ad_account_records)} ad-account rows")
        return {'monthly': monthly_df, 'daily': daily_df, 'ad_accounts': ad_accounts_df, 'errors': errors}

    except Exception as e:
        msg = f"Failed to load Agent Performance data: {e}"
        print(f"[ERROR] {msg}")
        import traceback
        traceback.print_exc()
        empty['errors'] = [msg]
        return empty


def refresh_agent_performance_data():
    """Clear Agent Performance data cache."""
    load_agent_performance_data.clear()


@st.cache_data(ttl=600)
def load_individual_kpi_data():
    """
    Load per-agent daily data from INDIVIDUAL KPI tab.
    Applies DER redistribution (splits DER metrics evenly across remaining agents).

    Returns:
        DataFrame with columns: date, person_name, spend, spend_php, ftd, register,
                                reach, impressions, clicks, ctr, cpc, cpm,
                                cost_per_register, cost_per_ftd
    """
    try:
        client = get_google_client()
        if client is None:
            return pd.DataFrame()

        spreadsheet = client.open_by_key(INDIVIDUAL_KPI_SHEET_ID)
        ws = spreadsheet.get_worksheet_by_id(INDIVIDUAL_KPI_GID)
        all_data = ws.get_all_values()

        if len(all_data) < INDIVIDUAL_KPI_DATA_START_ROW + 1:
            print("[WARNING] INDIVIDUAL KPI tab has insufficient rows")
            return pd.DataFrame()

        offsets = INDIVIDUAL_KPI_COL_OFFSETS
        records = []

        # Parse ad account names from row 2 (stored for later use)
        acct_row = all_data[2] if len(all_data) > 2 else []
        agent_accounts = {}
        for start_col, agent_name in INDIVIDUAL_KPI_AGENTS.items():
            acct_text = str(acct_row[start_col]).strip() if start_col < len(acct_row) else ''
            if acct_text:
                agent_accounts[agent_name] = acct_text.replace('\n', ' | ')

        for row_idx in range(INDIVIDUAL_KPI_DATA_START_ROW, len(all_data)):
            row = all_data[row_idx]

            for start_col, agent_name in INDIVIDUAL_KPI_AGENTS.items():
                # Get date
                date_col = start_col + offsets['date']
                if date_col >= len(row):
                    continue
                date_val = parse_date(str(row[date_col]).strip())
                if not date_val:
                    continue

                # Get spend
                spend_col = start_col + offsets['spend']
                spend = parse_numeric(row[spend_col] if spend_col < len(row) else '')
                if spend == 0:
                    continue  # Skip zero-spend rows (future dates)

                # Get other metrics
                spend_php = parse_numeric(row[start_col + offsets['spend_php']] if start_col + offsets['spend_php'] < len(row) else '')
                ftd = int(parse_numeric(row[start_col + offsets['ftd']] if start_col + offsets['ftd'] < len(row) else ''))
                register = int(parse_numeric(row[start_col + offsets['register']] if start_col + offsets['register'] < len(row) else ''))
                reach = int(parse_numeric(row[start_col + offsets['reach']] if start_col + offsets['reach'] < len(row) else ''))
                impressions = int(parse_numeric(row[start_col + offsets['impressions']] if start_col + offsets['impressions'] < len(row) else ''))
                clicks = int(parse_numeric(row[start_col + offsets['clicks']] if start_col + offsets['clicks'] < len(row) else ''))

                # Derived metrics
                ctr = round((clicks / impressions * 100) if impressions > 0 else 0, 2)
                cpc = round((spend / clicks) if clicks > 0 else 0, 2)
                cpm = round((spend / impressions * 1000) if impressions > 0 else 0, 2)
                cost_per_register = round((spend / register) if register > 0 else 0, 2)
                cost_per_ftd = round((spend / ftd) if ftd > 0 else 0, 2)

                records.append({
                    'date': date_val,
                    'person_name': agent_name,
                    'account_name': agent_accounts.get(agent_name, ''),
                    'spend': spend,
                    'spend_php': spend_php,
                    'ftd': ftd,
                    'register': register,
                    'reach': reach,
                    'impressions': impressions,
                    'clicks': clicks,
                    'ctr': ctr,
                    'cpc': cpc,
                    'cpm': cpm,
                    'cost_per_register': cost_per_register,
                    'cost_per_ftd': cost_per_ftd,
                })

        if not records:
            print("[WARNING] INDIVIDUAL KPI: no data rows found")
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])

        # --- DER redistribution (same logic as Facebook Ads) ---
        if EXCLUDED_PERSONS:
            excluded_upper = [p.upper() for p in EXCLUDED_PERSONS]
            excluded_mask = df['person_name'].str.upper().isin(excluded_upper)
            excluded_df = df[excluded_mask]
            df = df[~excluded_mask]

            if not excluded_df.empty and not df.empty:
                remaining_agents = df['person_name'].unique().tolist()
                n_agents = len(remaining_agents)
                numeric_cols = ['spend', 'spend_php', 'ftd', 'register', 'reach', 'impressions', 'clicks']

                redistributed_rows = []
                for _, row in excluded_df.iterrows():
                    for agent in remaining_agents:
                        new_row = row.copy()
                        new_row['person_name'] = agent
                        for col in numeric_cols:
                            if col in new_row.index:
                                new_row[col] = new_row[col] / n_agents
                        # Recalculate derived metrics
                        new_row['ctr'] = round((new_row['clicks'] / new_row['impressions'] * 100) if new_row['impressions'] > 0 else 0, 2)
                        new_row['cpc'] = round((new_row['spend'] / new_row['clicks']) if new_row['clicks'] > 0 else 0, 2)
                        new_row['cpm'] = round((new_row['spend'] / new_row['impressions'] * 1000) if new_row['impressions'] > 0 else 0, 2)
                        new_row['cost_per_register'] = round((new_row['spend'] / new_row['register']) if new_row['register'] > 0 else 0, 2)
                        new_row['cost_per_ftd'] = round((new_row['spend'] / new_row['ftd']) if new_row['ftd'] > 0 else 0, 2)
                        redistributed_rows.append(new_row)

                if redistributed_rows:
                    redistributed_df = pd.DataFrame(redistributed_rows)
                    df = pd.concat([df, redistributed_df], ignore_index=True)

                print(f"[OK] INDIVIDUAL KPI: redistributed {EXCLUDED_PERSONS} across {n_agents} agents")

        print(f"[OK] INDIVIDUAL KPI: {len(df)} rows loaded")
        return df

    except Exception as e:
        print(f"[ERROR] Failed to load INDIVIDUAL KPI: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def refresh_individual_kpi_data():
    """Clear INDIVIDUAL KPI data cache."""
    load_individual_kpi_data.clear()


# ============================================================
# KPI MONITORING FUNCTIONS
# ============================================================

def score_kpi(metric_key, value):
    """Score a single KPI metric based on rubric thresholds.
    Returns (score, raw_value) tuple."""
    if value is None or pd.isna(value):
        return (0, 0)

    rubric = KPI_SCORING.get(metric_key)
    if not rubric:
        return (0, value)

    for score, low, high in rubric['thresholds']:
        if rubric['direction'] == 'lower_better':
            if low <= value <= high:
                return (score, value)
        else:  # higher_better
            if low <= value <= high:
                return (score, value)

    # Fallback: if value doesn't match any range, score 1
    return (1, value)


def count_profile_assets(accounts_data):
    """Count profile assets (FB accounts, BMs, Pages) per agent from Updated Accounts data.

    Args:
        accounts_data: dict from load_updated_accounts_data() with fb_accounts, bm, pages DataFrames

    Returns:
        dict: {agent_name_upper: {'fb_accounts': N, 'bm': N, 'pages': N, 'total': N}}
    """
    result = {}

    for tab_key, col_name in [('fb_accounts', 'Employee'), ('bm', 'Employee'), ('pages', 'Employee')]:
        df = accounts_data.get(tab_key, pd.DataFrame())
        if df.empty or col_name not in df.columns:
            continue
        counts = df[col_name].str.strip().str.upper().value_counts().to_dict()
        asset_key = tab_key  # fb_accounts, bm, or pages
        for name, count in counts.items():
            if not name:
                continue
            if name not in result:
                result[name] = {'fb_accounts': 0, 'bm': 0, 'pages': 0, 'total': 0}
            result[name][asset_key] = count

    # Calculate totals
    for name in result:
        r = result[name]
        r['total'] = r['fb_accounts'] + r['bm'] + r['pages']

    return result


def score_profile_dev(total_count):
    """Score Profile Development based on total BMs + Pages + FB accounts.

    Rubric: 4 if total >= 5, 3 if total >= 3, 2 if total >= 2, 1 if total < 2
    """
    if total_count >= 5:
        return 4
    elif total_count >= 3:
        return 3
    elif total_count >= 2:
        return 2
    return 1


def calculate_kpi_scores(monthly_df, agent_name, daily_df=None, accounts_data=None, created_assets_data=None, ab_testing_data=None, reporting_data=None):
    """Calculate auto KPI scores for an agent from P-tab data.
    ROAS = ARPPU / 57.7 / Cost_per_FTD (IFERROR -> 0)

    Uses monthly data for CPA/CVR, calculates CTR from clicks/impressions,
    and gets ARPPU from daily data (latest available) for ROAS.
    Account Dev is scored from Created Assets tab (Gmail + FB accounts).

    Returns dict: {metric_key: {'score': int, 'value': float, 'name': str, ...}}
    """
    scores = {}
    agent_data = monthly_df[monthly_df['agent'] == agent_name]

    if agent_data.empty:
        for key in KPI_SCORING:
            if key in ('profile_dev', 'account_dev'):
                continue  # Handle separately below
            scores[key] = {'score': 0, 'value': 0, 'name': KPI_SCORING[key]['name']}
    else:
        # Use the most recent month's data
        row = agent_data.iloc[-1]

        # CPA = cost / ftd
        cost = float(row.get('cost', 0) or 0)
        ftd = float(row.get('ftd', 0) or 0)
        cpa = cost / ftd if ftd > 0 else 0
        s, v = score_kpi('cpa', cpa)
        scores['cpa'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['cpa']['name']}

        # ROAS = ARPPU / 57.7 / Cost_per_FTD
        # Monthly ARPPU is often empty, so get from daily data (latest row with ARPPU)
        arppu = float(row.get('arppu', 0) or 0)
        cpd = float(row.get('cpd', 0) or 0)

        if arppu == 0 and daily_df is not None and not daily_df.empty:
            agent_daily = daily_df[daily_df['agent'] == agent_name].copy()
            if not agent_daily.empty:
                agent_daily['arppu_num'] = pd.to_numeric(agent_daily['arppu'], errors='coerce').fillna(0)
                has_arppu = agent_daily[agent_daily['arppu_num'] > 0]
                if not has_arppu.empty:
                    arppu = has_arppu.iloc[-1]['arppu_num']
                    cpd = float(has_arppu.iloc[-1].get('cpd', 0) or 0)

        try:
            roas = arppu / KPI_PHP_USD_RATE / cpd if (cpd > 0 and arppu > 0) else 0
        except (ZeroDivisionError, TypeError):
            roas = 0
        s, v = score_kpi('roas', roas)
        scores['roas'] = {'score': s, 'value': round(v, 4), 'name': KPI_SCORING['roas']['name']}

        # CVR = FTD / Register * 100
        register = float(row.get('register', 0) or 0)
        cvr = (ftd / register * 100) if register > 0 else 0
        s, v = score_kpi('cvr', cvr)
        scores['cvr'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['cvr']['name']}

        # CTR = calculate from clicks/impressions (monthly CTR formula is broken in sheet)
        impressions = float(row.get('impressions', 0) or 0)
        clicks = float(row.get('clicks', 0) or 0)
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        s, v = score_kpi('ctr', ctr)
        scores['ctr'] = {'score': s, 'value': round(v, 2), 'name': KPI_SCORING['ctr']['name']}

    # Created Assets scoring (Account Dev + Profile Dev)
    agent_upper = agent_name.upper()
    asset_counts = {}

    if created_assets_data is not None and not created_assets_data.empty:
        asset_counts = count_created_assets(created_assets_data).get(agent_upper, {})

    # Account Dev (Gmail + FB accounts from Created Assets)
    acct_gmail = asset_counts.get('gmail', 0)
    acct_fb = asset_counts.get('fb_accounts', 0)
    acct_total = asset_counts.get('total_accounts', 0)
    acct_score = score_account_dev(acct_total)
    scores['account_dev'] = {
        'score': acct_score,
        'value': acct_total,
        'name': KPI_SCORING['account_dev']['name'],
        'gmail': acct_gmail,
        'fb_accounts': acct_fb,
    }

    # A/B Testing (Published campaigns from Text/AbTest tab)
    ab_counts = {}
    if ab_testing_data is not None:
        ab_counts = count_ab_testing(ab_testing_data).get(agent_upper, {})

    ab_published = ab_counts.get('published_ad', 0)
    ab_primary = ab_counts.get('primary_text', 0)
    ab_score = score_ab_testing(ab_published)
    scores['ab_testing'] = {
        'score': ab_score,
        'value': ab_published,
        'name': KPI_SCORING['ab_testing']['name'],
        'primary_text': ab_primary,
        'published_ad': ab_published,
    }

    # Reporting Accuracy (from Telegram Chat Listener API)
    rep_score = 0
    rep_avg_min = 0
    rep_count = 0
    if reporting_data and agent_name in reporting_data:
        rep_info = reporting_data[agent_name]
        rep_score = rep_info.get('score', 0)
        rep_avg_min = rep_info.get('avg_minute', 0)
        rep_count = rep_info.get('report_count', 0)
    scores['reporting'] = {
        'score': rep_score,
        'value': rep_avg_min,
        'name': KPI_SCORING['reporting']['name'],
        'avg_minute': rep_avg_min,
        'report_count': rep_count,
    }

    return scores


def get_google_write_client():
    """Get authenticated Google Sheets client with read+write scope for KPI write-back."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
        ]

        google_creds_json = os.getenv('GOOGLE_CREDENTIALS')
        if google_creds_json:
            creds_dict = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds_file = os.path.join(os.path.dirname(__file__), FACEBOOK_ADS_CREDENTIALS_FILE)
            if not os.path.exists(creds_file):
                print(f"[WARNING] Credentials file not found: {creds_file}")
                return None
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)

        return gspread.authorize(creds)
    except Exception as e:
        print(f"[ERROR] Failed to get Google write client: {e}")
        return None


def write_kpi_scores_to_sheet(agent_name, scores_dict):
    """Write auto-scored KPI values to the agent's KPI tab in Google Sheets.

    Args:
        agent_name: Agent name (e.g. 'Mika')
        scores_dict: dict from calculate_kpi_scores() with account_dev and ab_testing entries

    Returns:
        (success: bool, message: str)
    """
    tab_name = KPI_AGENT_TABS.get(agent_name)
    if not tab_name:
        return False, f"No KPI tab mapping for {agent_name}"

    try:
        client = get_google_write_client()
        if client is None:
            return False, "Could not authenticate Google Sheets write client"

        spreadsheet = client.open_by_key(KPI_SHEET_ID)
        worksheet = spreadsheet.worksheet(tab_name)

        messages = []

        # Write Account Dev (row ACCOUNT_DEV_ROW)
        acct_info = scores_dict.get('account_dev', {})
        acct_score = acct_info.get('score', 0)
        acct_raw = acct_info.get('value', 0)
        acct_weight = KPI_SCORING.get('account_dev', {}).get('weight', 0.10)
        acct_weighted = round(acct_score * acct_weight, 4)

        acct_row_num = ACCOUNT_DEV_ROW + 1  # 0-indexed to 1-indexed
        worksheet.update_cell(acct_row_num, 5, acct_score)
        worksheet.update_cell(acct_row_num, 6, acct_weighted)
        worksheet.update_cell(acct_row_num, 7, int(acct_raw))
        messages.append(f"Account Dev score={acct_score}, assets={int(acct_raw)}")

        # Write A/B Testing (row AB_TESTING_ROW)
        ab_info = scores_dict.get('ab_testing', {})
        ab_score = ab_info.get('score', 0)
        ab_raw = ab_info.get('value', 0)
        ab_weight = KPI_SCORING.get('ab_testing', {}).get('weight', 0.075)
        ab_weighted = round(ab_score * ab_weight, 4)

        ab_row_num = AB_TESTING_ROW + 1  # 0-indexed to 1-indexed
        worksheet.update_cell(ab_row_num, 5, ab_score)
        worksheet.update_cell(ab_row_num, 6, ab_weighted)
        worksheet.update_cell(ab_row_num, 7, int(ab_raw))
        messages.append(f"A/B Testing score={ab_score}, published={int(ab_raw)}")

        # Write Reporting Accuracy (row REPORTING_ROW)
        rep_info = scores_dict.get('reporting', {})
        rep_score = rep_info.get('score', 0)
        rep_raw = rep_info.get('avg_minute', 0)
        rep_weight = KPI_SCORING.get('reporting', {}).get('weight', 0.10)
        rep_weighted = round(rep_score * rep_weight, 4)

        rep_row_num = REPORTING_ROW + 1  # 0-indexed to 1-indexed
        worksheet.update_cell(rep_row_num, 5, rep_score)
        worksheet.update_cell(rep_row_num, 6, rep_weighted)
        worksheet.update_cell(rep_row_num, 7, round(rep_raw, 1))
        messages.append(f"Reporting score={rep_score}, avg_min={rep_raw:.1f}")

        return True, f"Wrote to {tab_name}: {'; '.join(messages)}"

    except Exception as e:
        return False, f"Failed to write to {tab_name}: {e}"


# Test functions
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Channel Data Loader Test')
    parser.add_argument('--fb', action='store_true', help='Test FB Summary loading')
    parser.add_argument('--google', action='store_true', help='Test Google Summary loading')
    parser.add_argument('--all', action='store_true', help='Test all data loading')

    args = parser.parse_args()

    if args.fb or args.all:
        print("\n" + "=" * 50)
        print("Testing FB Summary Loading")
        print("=" * 50)
        fb_df = load_fb_channel_data()
        if not fb_df.empty:
            print(f"Loaded {len(fb_df)} records")
            print(fb_df.head())
        else:
            print("No data loaded")

    if args.google or args.all:
        print("\n" + "=" * 50)
        print("Testing Google Summary Loading")
        print("=" * 50)
        google_data = load_google_channel_data()
        for key, df in google_data.items():
            if not df.empty:
                print(f"\n{key}: {len(df)} records")
                print(df.head())
            else:
                print(f"\n{key}: No data")

    if args.all:
        print("\n" + "=" * 50)
        print("Testing Combined Data")
        print("=" * 50)
        combined = combine_all_channel_data()
        if not combined.empty:
            print(f"Total records: {len(combined)}")
            print("\nBy Channel:")
            print(aggregate_by_channel(combined))

