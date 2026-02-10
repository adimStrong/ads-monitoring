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
    UPDATED_ACCOUNTS_SHEET,
    UPDATED_ACCOUNTS_GROUP1_COLUMNS,
    UPDATED_ACCOUNTS_GROUP2_COLUMNS,
    UPDATED_ACCOUNTS_GROUP3_COLUMNS,
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
    Load Updated Accounts data from the Facebook Ads spreadsheet.

    The "UPDATED ACCOUNTS" tab has 3 groups:
    - Group 1 (B-J): Personal FB accounts
    - Group 2 (L-S): Company accounts
    - Group 3 (Y-AB): BM Record

    Returns:
        dict: {'group1': DataFrame, 'group2': DataFrame, 'group3': DataFrame}
    """
    empty = {'group1': pd.DataFrame(), 'group2': pd.DataFrame(), 'group3': pd.DataFrame()}
    try:
        client = get_google_client()
        if client is None:
            return empty

        spreadsheet = client.open_by_key(FACEBOOK_ADS_SHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(UPDATED_ACCOUNTS_SHEET['gid'])
        all_data = worksheet.get_all_values()

        if len(all_data) < 2:
            print("[WARNING] Updated Accounts sheet has no data")
            return empty

        # Data starts at row 2 (index 1) - row 1 is headers
        data_rows = all_data[1:]

        def safe_get(row, idx):
            """Safely get a cell value by index."""
            if idx < len(row):
                return str(row[idx]).strip()
            return ''

        def mask_password(val):
            """Mask password values."""
            if val and val not in ('', '-', 'N/A', 'n/a'):
                return '********'
            return val

        # --- Group 1: Personal FB Accounts ---
        g1 = UPDATED_ACCOUNTS_GROUP1_COLUMNS
        g1_records = []
        for row in data_rows:
            employee = safe_get(row, g1['employee'])
            if not employee:
                continue
            g1_records.append({
                'Employee': employee,
                'FB Name': safe_get(row, g1['fb_name']),
                'Phone': safe_get(row, g1['phone']),
                'Password': mask_password(safe_get(row, g1['password'])),
                'Status': safe_get(row, g1['status']),
                'Email': safe_get(row, g1['email']),
                'Email Password': mask_password(safe_get(row, g1['email_password'])),
                'Email Status': safe_get(row, g1['email_status']),
                'Remarks': safe_get(row, g1['remarks']),
            })
        group1_df = pd.DataFrame(g1_records) if g1_records else pd.DataFrame()
        print(f"[OK] Loaded {len(g1_records)} Updated Accounts Group 1 (Personal FB) records")

        # --- Group 2: Company Accounts ---
        g2 = UPDATED_ACCOUNTS_GROUP2_COLUMNS
        g2_records = []
        for row in data_rows:
            employee = safe_get(row, g2['employee'])
            if not employee:
                continue
            g2_records.append({
                'Employee': employee,
                'FB User': safe_get(row, g2['fb_user']),
                'Password': mask_password(safe_get(row, g2['password'])),
                'Status': safe_get(row, g2['status']),
                'Email': safe_get(row, g2['email']),
                'Email Password': mask_password(safe_get(row, g2['email_password'])),
                'Email Status': safe_get(row, g2['email_status']),
                'Remarks': safe_get(row, g2['remarks']),
            })
        group2_df = pd.DataFrame(g2_records) if g2_records else pd.DataFrame()
        print(f"[OK] Loaded {len(g2_records)} Updated Accounts Group 2 (Company) records")

        # --- Group 3: BM Record ---
        g3 = UPDATED_ACCOUNTS_GROUP3_COLUMNS
        g3_records = []
        for row in data_rows:
            link_owner = safe_get(row, g3['link_owner'])
            if not link_owner:
                continue
            g3_records.append({
                'Link Owner': link_owner,
                'Game ID Code': safe_get(row, g3['game_id_code']),
                'PWA Links': safe_get(row, g3['pwa_links']),
                'Facebook Page Link': safe_get(row, g3['fb_page_link']),
            })
        group3_df = pd.DataFrame(g3_records) if g3_records else pd.DataFrame()
        print(f"[OK] Loaded {len(g3_records)} Updated Accounts Group 3 (BM Record) records")

        return {'group1': group1_df, 'group2': group2_df, 'group3': group3_df}

    except Exception as e:
        print(f"[ERROR] Failed to load Updated Accounts data: {e}")
        import traceback
        traceback.print_exc()
        return empty


def refresh_updated_accounts_data():
    """Clear Updated Accounts data cache."""
    load_updated_accounts_data.clear()


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

