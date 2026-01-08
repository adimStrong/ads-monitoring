"""
Google Sheets Data Loader for BINGO365 Monitoring Dashboard
Loads real data from Google Sheets with caching
"""
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GOOGLE_SHEETS_ID, AGENTS, RUNNING_ADS_COLUMNS, CREATIVE_WORK_COLUMNS, SMS_COLUMNS, CONTENT_COLUMNS


def get_public_sheet_url(sheet_id, sheet_name):
    """Get public export URL for a Google Sheet"""
    import urllib.parse
    encoded_name = urllib.parse.quote(sheet_name)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"


def parse_date(date_str):
    """Parse date from various formats"""
    if pd.isna(date_str) or str(date_str).strip() == '':
        return None

    date_str = str(date_str).strip()

    # Handle various date formats
    formats = [
        '%m/%d/%Y',
        '%m/%d',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m-%d-%Y',
        '%B %d, %Y',
        '%b %d, %Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If no year, assume current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt
        except:
            continue

    # Try parsing as Excel serial date
    try:
        excel_date = float(date_str)
        return datetime(1899, 12, 30) + timedelta(days=excel_date)
    except:
        pass

    return None


def parse_numeric(value, default=0):
    """Parse numeric value from string"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        # Remove any non-numeric characters except . and -
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c in '.-')
        return float(cleaned) if cleaned else default
    except:
        return default


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_agent_performance_data(agent_name, sheet_name):
    """
    Load performance data (WITH RUNNING ADS + WITHOUT + SMS) from agent's sheet
    Returns: running_ads_df, creative_df, sms_df
    """
    try:
        url = get_public_sheet_url(GOOGLE_SHEETS_ID, sheet_name)

        # Read all data from sheet
        df = pd.read_csv(url, header=1)  # Header is row 2 (index 1)

        if df.empty:
            return None, None, None

        # ============================================================
        # SECTION 1: WITH RUNNING ADS (Columns A-N, indices 0-13)
        # Column order: DATE, AMOUNT SPENT, TOTAL AD, CAMPAIGN, IMPRESSION,
        #               CLICKS, CTR%, CPC, CPR, CONVERSION RATE,
        #               REJECTED, DELETED, ACTIVE, REMARKS
        # ============================================================
        running_ads_data = []

        for idx, row in df.iterrows():
            date = parse_date(row.iloc[0] if len(row) > 0 else None)
            if not date:
                continue

            running_ads_data.append({
                'date': date,
                'agent_name': agent_name,
                'amount_spent': parse_numeric(row.iloc[1] if len(row) > 1 else 0),  # B - AMOUNT SPENT
                'total_ad': int(parse_numeric(row.iloc[2] if len(row) > 2 else 0)),  # C - TOTAL AD
                'campaign': str(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else '',  # D - CAMPAIGN
                'impressions': int(parse_numeric(row.iloc[4] if len(row) > 4 else 0)),  # E - IMPRESSION
                'clicks': int(parse_numeric(row.iloc[5] if len(row) > 5 else 0)),  # F - CLICKS
                'ctr_percent': parse_numeric(row.iloc[6] if len(row) > 6 else 0),  # G - CTR %
                'cpc': parse_numeric(row.iloc[7] if len(row) > 7 else 0),  # H - CPC
                'cpr': parse_numeric(row.iloc[8] if len(row) > 8 else 0),  # I - CPR
                'conversion_rate': parse_numeric(row.iloc[9] if len(row) > 9 else 0),  # J - CONVERSION RATE
                'rejected_count': int(parse_numeric(row.iloc[10] if len(row) > 10 else 0)),  # K - REJECTED
                'deleted_count': int(parse_numeric(row.iloc[11] if len(row) > 11 else 0)),  # L - DELETED
                'active_count': int(parse_numeric(row.iloc[12] if len(row) > 12 else 0)),  # M - ACTIVE
                'ad_remarks': str(row.iloc[13]) if len(row) > 13 and pd.notna(row.iloc[13]) else '',  # N - REMARKS
            })

        # ============================================================
        # SECTION 2: WITHOUT (Creative Work) (Columns O-T, indices 14-19)
        # Column order: CREATIVE FOLDER, TYPE, TOTAL, CONTENT, CAPTION, REMARKS
        # Note: Creative content can span multiple rows - rows without DATE inherit last valid date
        # ============================================================
        creative_data = []
        last_valid_date = None
        last_creative_folder = ''
        last_creative_type = ''

        for idx, row in df.iterrows():
            row_date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # Update tracking values if this row has a date
            if row_date:
                last_valid_date = row_date
                # Also update folder/type if present on dated rows
                folder = str(row.iloc[14]) if len(row) > 14 and pd.notna(row.iloc[14]) else ''
                if folder and folder.strip() and folder != 'nan':
                    last_creative_folder = folder
                ctype = str(row.iloc[15]) if len(row) > 15 and pd.notna(row.iloc[15]) else ''
                if ctype and ctype.strip() and ctype != 'nan':
                    last_creative_type = ctype

            # Use last valid date for rows without dates
            date_to_use = row_date if row_date else last_valid_date
            if not date_to_use:
                continue

            creative_content = str(row.iloc[17]) if len(row) > 17 and pd.notna(row.iloc[17]) else ''  # R - CONTENT

            if creative_content and creative_content.strip() and creative_content != 'nan':
                # Get folder/type from current row or use last valid
                creative_folder_raw = str(row.iloc[14]) if len(row) > 14 and pd.notna(row.iloc[14]) else ''
                if not creative_folder_raw or creative_folder_raw == 'nan':
                    creative_folder_raw = last_creative_folder
                creative_type_raw = str(row.iloc[15]) if len(row) > 15 and pd.notna(row.iloc[15]) else ''
                if not creative_type_raw or creative_type_raw == 'nan':
                    creative_type_raw = last_creative_type
                creative_total = int(parse_numeric(row.iloc[16] if len(row) > 16 else 0))  # Q - TOTAL

                # Normalize folder and type to title case
                creative_folder = creative_folder_raw.strip().title() if creative_folder_raw else ''
                creative_type = creative_type_raw.strip().upper() if creative_type_raw else ''

                creative_data.append({
                    'date': date_to_use,
                    'agent_name': agent_name,
                    'creative_folder': creative_folder,
                    'creative_type': creative_type,
                    'creative_total': creative_total,
                    'creative_content': creative_content,
                    'caption': str(row.iloc[18]) if len(row) > 18 and pd.notna(row.iloc[18]) else '',  # S - CAPTION
                    'creative_remarks': str(row.iloc[19]) if len(row) > 19 and pd.notna(row.iloc[19]) else '',  # T - REMARKS
                })

        # ============================================================
        # SECTION 3: SMS (Columns U-W, indices 20-22)
        # Column order: SMS TYPE, TOTAL, REMARKS
        # Note: SMS data can span multiple rows - rows without DATE inherit last valid date
        # ============================================================
        sms_data = []
        last_sms_date = None

        for idx, row in df.iterrows():
            row_date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # Update last valid date if this row has a date
            if row_date:
                last_sms_date = row_date

            # Use last valid date for rows without dates
            date_to_use = row_date if row_date else last_sms_date
            if not date_to_use:
                continue

            sms_type_raw = str(row.iloc[20]) if len(row) > 20 and pd.notna(row.iloc[20]) else ''  # U - SMS TYPE
            sms_total = parse_numeric(row.iloc[21] if len(row) > 21 else 0)  # V - TOTAL

            if sms_type_raw and sms_type_raw.strip() and sms_type_raw != 'nan' and sms_total > 0:
                # Normalize SMS type to title case to merge duplicates with different capitalization
                sms_type = sms_type_raw.strip().title()
                sms_data.append({
                    'date': date_to_use,
                    'agent_name': agent_name,
                    'sms_type': sms_type,
                    'sms_total': int(sms_total),
                    'sms_remarks': str(row.iloc[22]) if len(row) > 22 and pd.notna(row.iloc[22]) else '',  # W - REMARKS
                })

        running_ads_df = pd.DataFrame(running_ads_data) if running_ads_data else pd.DataFrame()
        creative_df = pd.DataFrame(creative_data) if creative_data else pd.DataFrame()
        sms_df = pd.DataFrame(sms_data) if sms_data else pd.DataFrame()

        return running_ads_df, creative_df, sms_df

    except Exception as e:
        st.warning(f"Could not load data for {agent_name}: {str(e)}")
        return None, None, None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_agent_content_data(agent_name, sheet_name):
    """
    Load content data from agent's content sheet
    """
    try:
        url = get_public_sheet_url(GOOGLE_SHEETS_ID, sheet_name)

        # Read all data from sheet
        df = pd.read_csv(url, header=0)  # Header is row 1

        if df.empty:
            return None

        content_data = []

        for idx, row in df.iterrows():
            date = parse_date(row.iloc[0] if len(row) > 0 else None)
            if not date:
                continue

            primary_content = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ''

            if primary_content and primary_content.strip() and primary_content != 'nan':
                content_data.append({
                    'date': date,
                    'agent_name': agent_name,
                    'content_type': str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else '',
                    'primary_content': primary_content,
                    'condition': str(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else '',
                    'status': str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else '',
                    'primary_adjustment': str(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else '',
                    'remarks': str(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else '',
                })

        return pd.DataFrame(content_data) if content_data else pd.DataFrame()

    except Exception as e:
        st.warning(f"Could not load content data for {agent_name}: {str(e)}")
        return None


def load_all_data():
    """
    Load all data from all agents
    Returns: running_ads_df, creative_df, sms_df, content_df
    """
    all_running_ads = []
    all_creative = []
    all_sms = []
    all_content = []

    progress_text = st.empty()
    progress_bar = st.progress(0)

    for i, agent in enumerate(AGENTS):
        progress_text.text(f"Loading data for {agent['name']}...")
        progress_bar.progress((i + 1) / len(AGENTS))

        # Load performance data
        running_ads_df, creative_df, sms_df = load_agent_performance_data(
            agent['name'],
            agent['sheet_performance']
        )

        if running_ads_df is not None and not running_ads_df.empty:
            all_running_ads.append(running_ads_df)
        if creative_df is not None and not creative_df.empty:
            all_creative.append(creative_df)
        if sms_df is not None and not sms_df.empty:
            all_sms.append(sms_df)

        # Load content data
        content_df = load_agent_content_data(
            agent['name'],
            agent['sheet_content']
        )

        if content_df is not None and not content_df.empty:
            all_content.append(content_df)

    progress_text.empty()
    progress_bar.empty()

    # Combine all data
    combined_running_ads = pd.concat(all_running_ads, ignore_index=True) if all_running_ads else pd.DataFrame()
    combined_creative = pd.concat(all_creative, ignore_index=True) if all_creative else pd.DataFrame()
    combined_sms = pd.concat(all_sms, ignore_index=True) if all_sms else pd.DataFrame()
    combined_content = pd.concat(all_content, ignore_index=True) if all_content else pd.DataFrame()

    return combined_running_ads, combined_creative, combined_sms, combined_content


def get_date_range(df):
    """Get min and max dates from dataframe"""
    if df.empty or 'date' not in df.columns:
        return datetime.now() - timedelta(days=30), datetime.now()

    min_date = df['date'].min()
    max_date = df['date'].max()

    if pd.isna(min_date):
        min_date = datetime.now() - timedelta(days=30)
    if pd.isna(max_date):
        max_date = datetime.now()

    return min_date, max_date


# Alternative: Use gspread with service account (for private sheets)
def load_with_gspread():
    """
    Load data using gspread (requires credentials.json)
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if not os.path.exists(creds_file):
            return None

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        gc = gspread.authorize(creds)

        spreadsheet = gc.open_by_key(GOOGLE_SHEETS_ID)
        return spreadsheet

    except Exception as e:
        print(f"gspread auth failed: {e}")
        return None
