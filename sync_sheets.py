"""
Google Sheets Data Sync for BINGO365 Monitoring
Syncs data from Google Sheets to PostgreSQL database
"""
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import GOOGLE_SHEETS_ID, AGENTS, PERFORMANCE_COLUMNS, CONTENT_COLUMNS
from db_schema import get_session, Agent, AdPerformance, AdContent, init_database
from utils.nlp_analyzer import get_analyzer


def get_google_sheets_client():
    """
    Get authenticated Google Sheets client
    Uses service account credentials if available, otherwise public access
    """
    try:
        # Try service account first
        creds_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'credentials.json')
        if os.path.exists(creds_file):
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
            return gspread.authorize(creds)
    except Exception as e:
        print(f"Service account auth failed: {e}")

    # Fall back to public access (if sheet is publicly accessible)
    try:
        return gspread.service_account()
    except:
        print("Warning: No authentication available. Sheet must be publicly accessible.")
        return None


def parse_date(date_str):
    """Parse date from various formats"""
    if pd.isna(date_str) or date_str == '':
        return None

    # Handle various date formats
    formats = [
        '%m/%d/%Y',
        '%m/%d',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m-%d-%Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            # If no year, assume current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.date()
        except:
            continue

    # Try parsing as float (Excel date format)
    try:
        from datetime import timedelta
        excel_date = float(date_str)
        return (datetime(1899, 12, 30) + timedelta(days=excel_date)).date()
    except:
        pass

    return None


def parse_numeric(value, default=0):
    """Parse numeric value"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        # Remove any non-numeric characters except . and -
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c in '.-')
        return float(cleaned) if cleaned else default
    except:
        return default


def sync_performance_data(gc, spreadsheet, agent_config, session):
    """Sync performance data for an agent"""
    agent_name = agent_config['name']
    sheet_name = agent_config['sheet_performance']

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_values()

        if len(data) < 3:  # Need header rows + data
            print(f"  No data found for {agent_name} performance")
            return 0

        # Find header row (row 2 based on screenshot)
        headers = data[1] if len(data) > 1 else []

        # Get agent
        agent = session.query(Agent).filter_by(name=agent_name).first()
        if not agent:
            print(f"  Agent {agent_name} not found in database")
            return 0

        count = 0
        # Process data rows (starting from row 3)
        for row in data[2:]:
            if not row or len(row) < 2:
                continue

            date = parse_date(row[0]) if row[0] else None
            if not date:
                continue

            # Check if record exists
            existing = session.query(AdPerformance).filter_by(
                agent_id=agent.id,
                date=date
            ).first()

            if existing:
                # Update existing record
                record = existing
            else:
                # Create new record
                record = AdPerformance(agent_id=agent.id, date=date)

            # Map columns (adjust indices based on actual sheet structure)
            record.total_ad = int(parse_numeric(row[1] if len(row) > 1 else 0))
            record.campaign = row[2] if len(row) > 2 else None
            record.impressions = int(parse_numeric(row[3] if len(row) > 3 else 0))
            record.clicks = int(parse_numeric(row[4] if len(row) > 4 else 0))
            record.ctr_percent = parse_numeric(row[5] if len(row) > 5 else 0)
            record.cpc = parse_numeric(row[6] if len(row) > 6 else 0)
            record.conversion_rate = parse_numeric(row[7] if len(row) > 7 else 0)
            record.rejected_count = int(parse_numeric(row[8] if len(row) > 8 else 0))
            record.deleted_count = int(parse_numeric(row[9] if len(row) > 9 else 0))
            record.active_count = int(parse_numeric(row[10] if len(row) > 10 else 0))
            record.remarks = row[11] if len(row) > 11 else None
            record.creative_folder = row[12] if len(row) > 12 else None
            record.content_type = row[13] if len(row) > 13 else None
            record.content_summary = row[14] if len(row) > 14 else None

            if not existing:
                session.add(record)
            count += 1

        session.commit()
        print(f"  Synced {count} performance records for {agent_name}")
        return count

    except gspread.exceptions.WorksheetNotFound:
        print(f"  Worksheet '{sheet_name}' not found")
        return 0
    except Exception as e:
        print(f"  Error syncing {agent_name} performance: {e}")
        session.rollback()
        return 0


def sync_content_data(gc, spreadsheet, agent_config, session):
    """Sync content data for an agent"""
    agent_name = agent_config['name']
    sheet_name = agent_config['sheet_content']
    analyzer = get_analyzer()

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_values()

        if len(data) < 2:
            print(f"  No content data found for {agent_name}")
            return 0

        # Get agent
        agent = session.query(Agent).filter_by(name=agent_name).first()
        if not agent:
            print(f"  Agent {agent_name} not found in database")
            return 0

        count = 0
        # Process data rows (starting from row 2, row 1 is header)
        for row in data[1:]:
            if not row or len(row) < 3:
                continue

            date = parse_date(row[0]) if row[0] else None
            if not date:
                continue

            content_type = row[1] if len(row) > 1 else None
            primary_content = row[2] if len(row) > 2 else None

            if not primary_content:
                continue

            # Compute content hash
            content_hash = analyzer.compute_hash(primary_content)

            # Check if exact record exists (same agent, date, hash)
            existing = session.query(AdContent).filter_by(
                agent_id=agent.id,
                date=date,
                content_hash=content_hash
            ).first()

            if existing:
                continue  # Skip duplicates

            # Create new record
            record = AdContent(
                agent_id=agent.id,
                date=date,
                content_type=content_type,
                primary_content=primary_content,
                condition=row[3] if len(row) > 3 else None,
                status=row[4] if len(row) > 4 else None,
                primary_adjustment=row[5] if len(row) > 5 else None,
                remarks=row[6] if len(row) > 6 else None,
                content_hash=content_hash
            )

            session.add(record)
            count += 1

        session.commit()
        print(f"  Synced {count} content records for {agent_name}")
        return count

    except gspread.exceptions.WorksheetNotFound:
        print(f"  Worksheet '{sheet_name}' not found")
        return 0
    except Exception as e:
        print(f"  Error syncing {agent_name} content: {e}")
        session.rollback()
        return 0


def sync_all_data():
    """Sync all data from Google Sheets"""
    print(f"Starting sync at {datetime.now()}")
    print("=" * 50)

    # Initialize database
    init_database()

    # Get Google Sheets client
    gc = get_google_sheets_client()
    if not gc:
        print("Could not authenticate with Google Sheets")
        return

    try:
        spreadsheet = gc.open_by_key(GOOGLE_SHEETS_ID)
        print(f"Connected to spreadsheet: {spreadsheet.title}")
    except Exception as e:
        print(f"Could not open spreadsheet: {e}")
        return

    session = get_session()

    # Ensure agents exist
    from db_schema import seed_agents
    seed_agents()

    total_performance = 0
    total_content = 0

    # Sync each agent
    for agent_config in AGENTS:
        print(f"\nSyncing {agent_config['name']}...")

        # Sync performance data
        perf_count = sync_performance_data(gc, spreadsheet, agent_config, session)
        total_performance += perf_count

        # Sync content data
        content_count = sync_content_data(gc, spreadsheet, agent_config, session)
        total_content += content_count

    session.close()

    print("\n" + "=" * 50)
    print(f"Sync completed at {datetime.now()}")
    print(f"Total performance records: {total_performance}")
    print(f"Total content records: {total_content}")


def load_from_csv(performance_csv=None, content_csv=None):
    """
    Alternative: Load data from exported CSV files
    Export your Google Sheets as CSV and use this function
    """
    session = get_session()
    init_database()

    from db_schema import seed_agents
    seed_agents()

    if performance_csv and os.path.exists(performance_csv):
        print(f"Loading performance data from {performance_csv}")
        df = pd.read_csv(performance_csv)
        # Process and insert...

    if content_csv and os.path.exists(content_csv):
        print(f"Loading content data from {content_csv}")
        df = pd.read_csv(content_csv)
        # Process and insert...

    session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Sync BINGO365 data from Google Sheets')
    parser.add_argument('--csv', action='store_true', help='Load from CSV files instead')
    parser.add_argument('--performance-csv', type=str, help='Path to performance CSV')
    parser.add_argument('--content-csv', type=str, help='Path to content CSV')

    args = parser.parse_args()

    if args.csv:
        load_from_csv(args.performance_csv, args.content_csv)
    else:
        sync_all_data()
