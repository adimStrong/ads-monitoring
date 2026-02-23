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
from config import (
    GOOGLE_SHEETS_ID, AGENTS, RUNNING_ADS_COLUMNS, CREATIVE_WORK_COLUMNS, SMS_COLUMNS, CONTENT_COLUMNS,
    INDIAN_PROMOTION_SHEET_ID, INDIAN_PROMOTION_GID, INDIAN_PROMOTION_AGENTS,
    FACEBOOK_ADS_SHEET_ID, FACEBOOK_ADS_CREDENTIALS_FILE, FACEBOOK_ADS_SHEETS,
    FACEBOOK_ADS_ACCOUNT_START_COLS, FACEBOOK_ADS_COLUMN_OFFSETS, FACEBOOK_ADS_DATA_START_ROW,
    FACEBOOK_ADS_NAMES_ROW, EXCLUDED_PERSONS
)


def get_public_sheet_url(sheet_id, sheet_name):
    """Get public export URL for a Google Sheet"""
    import urllib.parse
    encoded_name = urllib.parse.quote(sheet_name)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"


def normalize_agent_name(name):
    """Normalize agent name to consistent format (uppercase)"""
    if not name:
        return ''
    return str(name).strip().upper()


def parse_date(date_str):
    """Parse date from various formats including malformed dates"""
    if pd.isna(date_str) or str(date_str).strip() == '':
        return None

    date_str = str(date_str).strip()

    # Skip if it looks like header text or concatenated merged cell data
    if len(date_str) > 20:  # Date strings shouldn't be this long
        return None
    if any(keyword in date_str.upper() for keyword in ['TYPE', 'PRIMARY', 'CONTENT', 'DATE', 'CONDITION']):
        return None

    # Clean up malformed dates like "1//7" -> "1/7"
    import re
    date_str = re.sub(r'/+', '/', date_str)  # Replace multiple slashes with single
    date_str = date_str.strip('/')  # Remove leading/trailing slashes

    # Current year for dates without year
    current_year = datetime.now().year

    # Handle various date formats
    formats = [
        '%m/%d/%Y',
        '%m/%d/%y',    # 2-digit year like 01/05/26
        '%m/%d',       # No year like 1/8 or 01/05
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m-%d-%Y',
        '%B %d, %Y',
        '%b %d, %Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If no year (defaults to 1900), use current year
            if dt.year == 1900:
                dt = dt.replace(year=current_year)
            # Handle 2-digit year - if parsed year is far in future, adjust
            elif dt.year > current_year + 10:
                dt = dt.replace(year=dt.year - 100)
            return dt
        except:
            continue

    # Try parsing as Excel serial date
    try:
        excel_date = float(date_str)
        if 1 < excel_date < 100000:  # Reasonable Excel date range
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


def parse_creative_total(value, default=0):
    """
    Parse creative total from various formats:
    - "9" -> 9
    - "8 Banners" -> 8
    - "7 Banners & 2 Videos" -> 9 (sum of all numbers)
    - "10" -> 10
    """
    import re
    if pd.isna(value) or value == '' or value is None:
        return default

    value_str = str(value).strip()
    if not value_str or value_str == 'nan':
        return default

    # Find all numbers in the string
    numbers = re.findall(r'\d+', value_str)
    if numbers:
        # Sum all numbers found (e.g., "7 Banners & 2 Videos" = 9)
        return sum(int(n) for n in numbers)

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
        df = pd.read_csv(url, header=0)  # Header is row 1 (index 0)

        if df.empty:
            return None, None, None

        # Normalize agent name
        normalized_agent = normalize_agent_name(agent_name)

        # ============================================================
        # SECTION 1: WITH RUNNING ADS (Columns A-N, indices 0-13)
        # Column order: DATE, AMOUNT SPENT, TOTAL AD, CAMPAIGN, IMPRESSION,
        #               CLICKS, CTR%, CPC, CPR, CONVERSION RATE,
        #               REJECTED, DELETED, ACTIVE, REMARKS
        # Note: Only rows with valid dates get performance data (no merging)
        # ============================================================
        running_ads_data = []
        last_perf_date = None

        for idx, row in df.iterrows():
            date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # For running ads, only process rows with actual dates
            # (performance data is per-date, not merged)
            if not date:
                continue

            last_perf_date = date

            running_ads_data.append({
                'date': date,
                'agent_name': normalized_agent,
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
        # TOTAL column is also merged - inherit from last valid total
        # ============================================================
        creative_data = []
        last_valid_date = None
        last_creative_folder = ''
        last_creative_type = ''
        last_creative_total = 0  # Track last valid total for merged cells
        default_date = datetime.now()  # Fallback for sheets with no dates

        for idx, row in df.iterrows():
            row_date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # Update tracking values if this row has a date
            if row_date:
                last_valid_date = row_date
                # Also update folder/type/total if present on dated rows
                folder = str(row.iloc[14]) if len(row) > 14 and pd.notna(row.iloc[14]) else ''
                if folder and folder.strip() and folder != 'nan':
                    last_creative_folder = folder
                ctype = str(row.iloc[15]) if len(row) > 15 and pd.notna(row.iloc[15]) else ''
                if ctype and ctype.strip() and ctype != 'nan':
                    last_creative_type = ctype
                # Update total if present on dated row
                total_raw = row.iloc[16] if len(row) > 16 else None
                if pd.notna(total_raw) and str(total_raw).strip() and str(total_raw).strip() != 'nan':
                    last_creative_total = parse_creative_total(total_raw)

            # Use last valid date for rows without dates, or default date if no dates at all
            date_to_use = row_date if row_date else last_valid_date
            if not date_to_use:
                date_to_use = default_date  # Use today's date for sheets without any dates

            creative_content = str(row.iloc[17]) if len(row) > 17 and pd.notna(row.iloc[17]) else ''  # R - CONTENT

            # Get total from current row or inherit from last valid total
            total_raw = row.iloc[16] if len(row) > 16 else None
            if pd.notna(total_raw) and str(total_raw).strip() and str(total_raw).strip() != 'nan':
                creative_total = parse_creative_total(total_raw)
                last_creative_total = creative_total  # Update last valid total
            else:
                creative_total = last_creative_total  # Inherit from merged cell

            # Only count creative work when actual content exists
            has_content = creative_content and creative_content.strip() and creative_content != 'nan'

            if has_content:
                # Get folder/type from current row or use last valid
                creative_folder_raw = str(row.iloc[14]) if len(row) > 14 and pd.notna(row.iloc[14]) else ''
                if not creative_folder_raw or creative_folder_raw == 'nan':
                    creative_folder_raw = last_creative_folder
                creative_type_raw = str(row.iloc[15]) if len(row) > 15 and pd.notna(row.iloc[15]) else ''
                if not creative_type_raw or creative_type_raw == 'nan':
                    creative_type_raw = last_creative_type

                # Normalize folder and type to title case
                creative_folder = creative_folder_raw.strip().title() if creative_folder_raw else ''
                creative_type = creative_type_raw.strip().upper() if creative_type_raw else ''

                creative_data.append({
                    'date': date_to_use,
                    'agent_name': normalized_agent,
                    'creative_folder': creative_folder,
                    'creative_type': creative_type,
                    'creative_total': creative_total,  # Inherited from merged cell if empty
                    'creative_content': creative_content,
                    'caption': str(row.iloc[18]) if len(row) > 18 and pd.notna(row.iloc[18]) else '',  # S - CAPTION
                    'creative_remarks': str(row.iloc[19]) if len(row) > 19 and pd.notna(row.iloc[19]) else '',  # T - REMARKS
                })

        # ============================================================
        # SECTION 3: SMS (Columns U-W, indices 20-22)
        # Column order: SMS TYPE, TOTAL, REMARKS
        # Note: SMS data can span multiple rows - rows without DATE inherit last valid date
        # TOTAL column is also merged - inherit from last valid total
        # ============================================================
        sms_data = []
        last_sms_date = None
        last_sms_total = 0  # Track last valid SMS total for merged cells

        for idx, row in df.iterrows():
            row_date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # Update last valid date if this row has a date
            if row_date:
                last_sms_date = row_date
                # Update SMS total if present on dated row
                total_raw = row.iloc[21] if len(row) > 21 else None
                if pd.notna(total_raw) and str(total_raw).strip() and str(total_raw).strip() != 'nan':
                    last_sms_total = int(parse_numeric(total_raw))

            # Use last valid date for rows without dates
            date_to_use = row_date if row_date else last_sms_date
            if not date_to_use:
                continue

            sms_type_raw = str(row.iloc[20]) if len(row) > 20 and pd.notna(row.iloc[20]) else ''  # U - SMS TYPE

            # Get total from current row or inherit from last valid total
            total_raw = row.iloc[21] if len(row) > 21 else None
            if pd.notna(total_raw) and str(total_raw).strip() and str(total_raw).strip() != 'nan':
                sms_total = int(parse_numeric(total_raw))
                last_sms_total = sms_total  # Update last valid total
            else:
                sms_total = last_sms_total  # Inherit from merged cell

            if sms_type_raw and sms_type_raw.strip() and sms_type_raw != 'nan' and sms_total > 0:
                # Normalize SMS type to title case to merge duplicates with different capitalization
                sms_type = sms_type_raw.strip().title()
                sms_data.append({
                    'date': date_to_use,
                    'agent_name': normalized_agent,
                    'sms_type': sms_type,
                    'sms_total': sms_total,  # Inherited from merged cell if empty
                    'sms_remarks': str(row.iloc[22]) if len(row) > 22 and pd.notna(row.iloc[22]) else '',  # W - REMARKS
                })

        running_ads_df = pd.DataFrame(running_ads_data) if running_ads_data else pd.DataFrame()
        creative_df = pd.DataFrame(creative_data) if creative_data else pd.DataFrame()
        sms_df = pd.DataFrame(sms_data) if sms_data else pd.DataFrame()

        return running_ads_df, creative_df, sms_df

    except Exception as e:
        st.warning(f"Could not load data for {agent_name}: {str(e)}")
        return None, None, None


def is_merged_header_row(row):
    """
    Check if a row is a malformed merged header row.
    These rows have concatenated data from merged cells.
    """
    if len(row) < 2:
        return False

    # Check multiple columns for signs of merged/concatenated data
    for i in range(min(4, len(row))):
        cell = str(row.iloc[i]) if pd.notna(row.iloc[i]) else ''
        # If cell contains multiple keywords that should be in separate cells
        keywords = ['Primary Text', 'Headline', 'Approved', 'TYPE', 'PRIMARY CONTENT', 'CONDITION']
        keyword_count = sum(1 for k in keywords if k in cell)
        if keyword_count >= 2:
            return True
        # If cell is extremely long (concatenated data)
        if len(cell) > 500:
            return True
    return False


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_agent_content_data(agent_name, sheet_name):
    """
    Load content data from agent's content sheet
    Content sheet structure: DATE, TYPE, PRIMARY CONTENT, CONDITION, STATUS, blank, REMARK/S
    Note: First row may be malformed header with merged/concatenated cells
    Dates may be in m/d format without year and empty for continuation rows
    """
    try:
        url = get_public_sheet_url(GOOGLE_SHEETS_ID, sheet_name)

        # Read all data without header - we'll parse manually due to malformed headers
        df = pd.read_csv(url, header=None)

        if df.empty:
            return None

        # Normalize agent name
        normalized_agent = normalize_agent_name(agent_name)

        content_data = []
        last_valid_date = None
        last_content_type = ''

        for idx, row in df.iterrows():
            # Skip malformed merged header rows (first few rows might be affected)
            if idx < 3 and is_merged_header_row(row):
                continue

            # Skip header row with keywords
            first_cell = str(row.iloc[0]) if len(row) > 0 and pd.notna(row.iloc[0]) else ''
            if 'DATE' in first_cell.upper() and idx < 2:
                continue

            # Parse date - will return None for empty cells or malformed data
            date = parse_date(row.iloc[0] if len(row) > 0 else None)

            # Track last valid date for rows without dates (headlines under primary text)
            if date:
                last_valid_date = date
            else:
                date = last_valid_date

            if not date:
                continue

            # Get content type - inherit from last row if empty
            content_type_raw = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ''
            if content_type_raw and content_type_raw.strip() and content_type_raw != 'nan':
                # Normalize content type (Primary Text, Headline)
                content_type_raw = content_type_raw.strip()
                if 'primary' in content_type_raw.lower():
                    last_content_type = 'Primary Text'
                elif 'headline' in content_type_raw.lower():
                    last_content_type = 'Headline'
                else:
                    last_content_type = content_type_raw.title()

            content_type = last_content_type

            primary_content = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ''

            # Skip if content looks like a header or is too long (concatenated)
            if 'PRIMARY CONTENT' in primary_content.upper():
                continue
            if len(primary_content) > 1000:  # Likely concatenated merged cell data
                continue

            if primary_content and primary_content.strip() and primary_content != 'nan':
                content_data.append({
                    'date': date,
                    'agent_name': normalized_agent,
                    'content_type': content_type,
                    'primary_content': primary_content.strip(),
                    'condition': str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else '',
                    'status': str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else '',
                    'primary_adjustment': str(row.iloc[5]).strip() if len(row) > 5 and pd.notna(row.iloc[5]) else '',
                    'remarks': str(row.iloc[6]).strip() if len(row) > 6 and pd.notna(row.iloc[6]) else '',
                })

        return pd.DataFrame(content_data) if content_data else pd.DataFrame()

    except Exception as e:
        st.warning(f"Could not load content data for {agent_name}: {str(e)}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_indian_promotion_content():
    """
    Load copywriting data from Indian Promotion sheet
    This sheet has all agents in one sheet with separate column groups.
    Only counts Primary Text entries.

    Returns: DataFrame with columns: date, agent_name, content_type, primary_content, condition, status
    """
    try:
        # Build URL with gid for specific sheet
        url = f"https://docs.google.com/spreadsheets/d/{INDIAN_PROMOTION_SHEET_ID}/gviz/tq?tqx=out:csv&gid={INDIAN_PROMOTION_GID}"

        # Read all data without header
        df = pd.read_csv(url, header=None)

        if df.empty:
            return pd.DataFrame()

        all_content = []

        for agent_name, cols in INDIAN_PROMOTION_AGENTS.items():
            last_valid_date = None

            for idx in range(1, len(df)):  # Skip header row
                # Get date (handle merged cells)
                date_val = df.iloc[idx, cols['date']] if pd.notna(df.iloc[idx, cols['date']]) else None
                parsed_date = parse_date(date_val)

                if parsed_date:
                    last_valid_date = parsed_date

                # Use last valid date for rows without dates
                current_date = parsed_date if parsed_date else last_valid_date

                if not current_date:
                    continue

                # Get type and content
                type_val = str(df.iloc[idx, cols['type']]) if pd.notna(df.iloc[idx, cols['type']]) else ''
                content_val = str(df.iloc[idx, cols['content']]) if pd.notna(df.iloc[idx, cols['content']]) else ''
                condition_val = str(df.iloc[idx, cols['condition']]) if pd.notna(df.iloc[idx, cols['condition']]) else ''
                status_val = str(df.iloc[idx, cols['status']]) if pd.notna(df.iloc[idx, cols['status']]) else ''

                # Only include Primary Text with actual content
                if 'Primary Text' in type_val and content_val not in ['', 'nan']:
                    all_content.append({
                        'date': current_date,
                        'agent_name': agent_name,
                        'content_type': 'Primary Text',
                        'primary_content': content_val.strip(),
                        'condition': condition_val.strip() if condition_val != 'nan' else '',
                        'status': status_val.strip() if status_val != 'nan' else '',
                        'source': 'Indian Promotion'
                    })

        return pd.DataFrame(all_content) if all_content else pd.DataFrame()

    except Exception as e:
        st.warning(f"Could not load Indian Promotion data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_facebook_ads_data():
    """
    Load Facebook Ads data from INDIVIDUAL KPI sheet using service account authentication.
    Single sheet contains all 8 persons with properly aligned dates.

    Persons (in order by column): JASON, RON, SHILA, ADRIAN, JOMAR, MIKA
    Column positions: 17, 27, 37, 47, 57, 77

    Returns: DataFrame with columns:
        date, person_name, spend, cost_php, result_ftd, register,
        reach, impressions, clicks, cpm, ctr, cpc, cost_per_register, cost_per_ftd
    """
    try:
        import gspread
        import json
        from google.oauth2.service_account import Credentials

        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        # Try environment variable first (for Railway/cloud deployment)
        google_creds_json = os.getenv('GOOGLE_CREDENTIALS')
        if google_creds_json:
            try:
                creds_dict = json.loads(google_creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                print("Using GOOGLE_CREDENTIALS environment variable")
            except json.JSONDecodeError as e:
                print(f"Error parsing GOOGLE_CREDENTIALS JSON: {e}")
                st.error(f"Error parsing GOOGLE_CREDENTIALS: {e}")
                return pd.DataFrame()
        else:
            # Fall back to credentials file (local development)
            creds_file = os.path.join(os.path.dirname(__file__), FACEBOOK_ADS_CREDENTIALS_FILE)
            if not os.path.exists(creds_file):
                print(f"Facebook Ads credentials file not found: {creds_file}")
                st.warning("No Google credentials found. Set GOOGLE_CREDENTIALS env var or add credentials.json file.")
                return pd.DataFrame()
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
            print("Using local credentials file")

        client = gspread.authorize(creds)

        spreadsheet = client.open_by_key(FACEBOOK_ADS_SHEET_ID)

        all_ads_data = []

        for sheet_info in FACEBOOK_ADS_SHEETS:
            sheet_name = sheet_info['name']
            try:
                ws = spreadsheet.worksheet(sheet_name)
                all_data = ws.get_all_values()

                if len(all_data) < FACEBOOK_ADS_DATA_START_ROW + 1:
                    continue

                # Row 2 (index 1) has person names in INDIVIDUAL KPI sheet
                names_row = all_data[FACEBOOK_ADS_NAMES_ROW] if len(all_data) > FACEBOOK_ADS_NAMES_ROW else []

                # Row 3 (index 2) has account IDs (fallback)
                account_ids_row = all_data[2] if len(all_data) > 2 else []

                # Extract person names for each column group
                person_names = {}
                account_names = {}
                for start_col in FACEBOOK_ADS_ACCOUNT_START_COLS:
                    # Get person name from names row
                    if start_col < len(names_row):
                        person_name = names_row[start_col].strip().upper()
                        if person_name:
                            person_names[start_col] = person_name

                    # Get account ID from Row 3 (as fallback/reference)
                    if start_col < len(account_ids_row):
                        acc_id = account_ids_row[start_col].replace('\n', ' / ').strip()
                        if acc_id and 'DATE' not in acc_id.upper():
                            account_names[start_col] = acc_id

                print(f"Found persons in {sheet_name}: {list(person_names.values())}")

                # Process data rows (starting from row 5, index 4)
                for row_idx in range(FACEBOOK_ADS_DATA_START_ROW, len(all_data)):
                    row = all_data[row_idx]

                    # Skip header rows (names row, account row, headers row)
                    if row_idx <= 3:
                        continue

                    # Process each person's column group
                    for start_col in FACEBOOK_ADS_ACCOUNT_START_COLS:
                        # Need person name
                        if start_col not in person_names:
                            continue

                        offsets = FACEBOOK_ADS_COLUMN_OFFSETS

                        # Get date
                        date_col = start_col + offsets['date']
                        date_val = row[date_col] if date_col < len(row) else ''
                        parsed_date = parse_date(date_val)

                        if not parsed_date:
                            continue

                        # Get spend
                        spend_col = start_col + offsets['spend']
                        spend_val = row[spend_col] if spend_col < len(row) else ''
                        spend = parse_numeric(spend_val.replace(',', '').replace('$', '')) if spend_val else 0

                        # Skip rows with no spend
                        if spend == 0:
                            continue

                        # Get other metrics
                        cost_php_col = start_col + offsets['cost_php']
                        cost_php = parse_numeric(row[cost_php_col].replace(',', '') if cost_php_col < len(row) and row[cost_php_col] else '0')

                        result_col = start_col + offsets['result_ftd']
                        result_ftd = int(parse_numeric(row[result_col].replace(',', '') if result_col < len(row) and row[result_col] else '0'))

                        register_col = start_col + offsets['register']
                        register = int(parse_numeric(row[register_col].replace(',', '') if register_col < len(row) and row[register_col] else '0'))

                        reach_col = start_col + offsets['reach']
                        reach = int(parse_numeric(row[reach_col].replace(',', '') if reach_col < len(row) and row[reach_col] else '0'))

                        impressions_col = start_col + offsets['impressions']
                        impressions = int(parse_numeric(row[impressions_col].replace(',', '') if impressions_col < len(row) and row[impressions_col] else '0'))

                        clicks_col = start_col + offsets['clicks']
                        clicks = int(parse_numeric(row[clicks_col].replace(',', '') if clicks_col < len(row) and row[clicks_col] else '0'))

                        # Calculate derived metrics
                        ctr = (clicks / impressions * 100) if impressions > 0 else 0
                        cpc = (spend / clicks) if clicks > 0 else 0
                        cpm = (spend / impressions * 1000) if impressions > 0 else 0
                        cost_per_register = (spend / register) if register > 0 else 0
                        cost_per_ftd = (spend / result_ftd) if result_ftd > 0 else 0

                        # Get person name
                        person_name = person_names.get(start_col, '')
                        account_id = account_names.get(start_col, '')

                        all_ads_data.append({
                            'date': parsed_date,
                            'person_name': person_name,
                            'account_name': account_id,
                            'spend': spend,
                            'cost_php': cost_php,
                            'result_ftd': result_ftd,
                            'register': register,
                            'reach': reach,
                            'impressions': impressions,
                            'clicks': clicks,
                            'ctr': round(ctr, 2),
                            'cpc': round(cpc, 2),
                            'cpm': round(cpm, 2),
                            'cost_per_register': round(cost_per_register, 2),
                            'cost_per_ftd': round(cost_per_ftd, 2),
                        })

                print(f"Loaded {len([d for d in all_ads_data])} rows from {sheet_name}")

            except Exception as e:
                print(f"Error loading {sheet_name}: {e}")
                import traceback
                traceback.print_exc()
                continue

        if all_ads_data:
            df = pd.DataFrame(all_ads_data)
            # Redistribute excluded persons' metrics across remaining agents
            if EXCLUDED_PERSONS and 'person_name' in df.columns:
                excluded_upper = [p.upper() for p in EXCLUDED_PERSONS]
                excluded_mask = df['person_name'].str.upper().isin(excluded_upper)
                excluded_df = df[excluded_mask]
                df = df[~excluded_mask]

                if not excluded_df.empty and not df.empty:
                    remaining_agents = df['person_name'].unique().tolist()
                    n_agents = len(remaining_agents)
                    numeric_cols = ['spend', 'cost_php', 'result_ftd', 'register', 'reach', 'impressions', 'clicks']

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
                            new_row['cost_per_ftd'] = round((new_row['spend'] / new_row['result_ftd']) if new_row['result_ftd'] > 0 else 0, 2)
                            redistributed_rows.append(new_row)

                    if redistributed_rows:
                        redistributed_df = pd.DataFrame(redistributed_rows)
                        df = pd.concat([df, redistributed_df], ignore_index=True)

                print(f"Excluded persons redistributed: {EXCLUDED_PERSONS}")
            return df
        return pd.DataFrame()

    except Exception as e:
        print(f"Error loading Facebook Ads data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


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

    # Load Indian Promotion content (additional copywriting data)
    progress_text.text("Loading Indian Promotion data...")
    indian_content_df = load_indian_promotion_content()
    if indian_content_df is not None and not indian_content_df.empty:
        all_content.append(indian_content_df)

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
