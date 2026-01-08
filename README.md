# BINGO365 Daily Monitoring Dashboard

A comprehensive Streamlit dashboard for monitoring digital marketing performance and content analysis for BINGO365 team members.

## Features

- **Per-Agent Performance**: Individual dashboards for each team member (MIKA, SHEENA, ADRIAN, JOMAR, SHILA, KRISSA)
- **Content Similarity Analysis**: NLP-powered detection of similar/recycled content
- **Daily vs Monthly Comparison**: Compare today's content freshness vs monthly trends
- **Theme Detection**: Automatic categorization of content themes
- **Team Leaderboard**: Performance rankings across all agents

## Project Structure

```
bingo365_monitoring/
├── app.py                    # Main Streamlit application
├── config.py                 # Configuration settings
├── db_schema.py              # Database models (SQLAlchemy)
├── sync_sheets.py            # Google Sheets sync utility
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── pages/
│   ├── 1_Agent_Performance.py    # Individual agent view
│   ├── 2_Content_Analysis.py     # Content similarity & themes
│   └── 3_Team_Overview.py        # Team comparison
├── utils/
│   ├── db_utils.py           # Database query utilities
│   └── nlp_analyzer.py       # NLP content analysis
└── data/                     # Data exports directory
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run with Sample Data (No Database Required)

```bash
streamlit run app.py
```

The dashboard will run with sample data for demonstration.

### 3. (Optional) Set Up Database

For production use with PostgreSQL:

```bash
# Create .env file
cp .env.example .env

# Edit .env with your database credentials
DATABASE_URL=postgresql://user:pass@host:port/database

# Initialize database
python db_schema.py

# Sync data from Google Sheets
python sync_sheets.py
```

## Dashboard Pages

### 1. Overview (Main Page)
- Team-wide KPIs
- Performance trends
- Agent comparison charts

### 2. Agent Performance
- Select individual agent
- Detailed performance metrics
- CTR, CPC, conversion trends
- Ad status distribution

### 3. Content Analysis
- **Daily vs Monthly**: Compare today's content freshness
- **Similarity Check**: Find duplicate/similar content
- **Theme Detection**: Categorize content by theme

### 4. Team Overview
- Side-by-side agent comparison
- Performance radar chart
- Content freshness leaderboard
- Overall scoring

## Data Source

Google Sheet: `DAILY MONITORING BINGO365`
- 6 agents with performance tabs
- 6 agents with content tabs

## Key Metrics

### Performance Metrics
- Total Ads
- Impressions
- Clicks
- CTR %
- CPC
- Conversion Rate
- Active/Rejected/Deleted Count

### Content Metrics
- Total Posts
- Unique Content
- Content Freshness Score
- Theme Distribution
- Similarity Scores

## Tech Stack

- **Frontend**: Streamlit
- **Database**: PostgreSQL (optional)
- **Charts**: Plotly
- **NLP**: scikit-learn, sentence-transformers
- **Data Sync**: gspread (Google Sheets API)

## Environment Variables

```env
DATABASE_URL=postgresql://username:password@host:port/database
GOOGLE_SHEETS_ID=1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ
```

## License

Internal use only - BINGO365 Marketing Team
