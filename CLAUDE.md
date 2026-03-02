# BINGO365 Daily Monitoring Dashboard

## Overview
- **Live URL**: https://bingo365-monitoring-bjruxaftqm6xq2jvfojn8r.streamlit.app/
- **Repo**: https://github.com/adimStrong/bingo365-monitoring.git (branch: main)
- **Deploy**: `git push origin main` (Streamlit Cloud auto-deploys)
- **Tech Stack**: Python + Streamlit 1.41 + Plotly + Pandas + gspread + google-auth
- **Local run**: `python -m streamlit run app.py`

## Data Sources

### Main Agent Sheet (daily tracking)
- **Sheet ID**: `1L4aYgFkv_aoqIUaZo7Zi4NHlNEQiThMKc_0jpIb-MfQ`
- Per-agent tabs with 3 sections: Running Ads (A-N), Creative Work (O-T), SMS (U-W)
- Loaded by `data_loader.py` via public CSV URLs

### Channel ROI Sheet (P-tabs - primary ads data)
- **Sheet ID**: `1P6GoOQUa7FdiGKPLJiytMzYvkRJwt7jPmqqHo0p0p0c`
- **Service Account**: `juan365-reporter@juan365-reporter.iam.gserviceaccount.com`
- **Credentials**: `credentials.json` (local) or `GOOGLE_CREDENTIALS` env var
- 8 P-tabs (P6-Mika through P13-Shila), each with:
  - Monthly summary (rows 3-6): Cost, Register, CPR, FTD, CPD, Conv Rate, Impressions, Clicks, CTR, ARPPU, ROAS
  - Daily data (rows 10+): same columns + ad account breakdowns every 5 cols from col 15
- Loaded by `channel_data_loader.py` → `load_agent_performance_data()`

### Facebook Ads Sheet (legacy - INDIVIDUAL KPI)
- **Sheet ID**: `13oDZjGctd8mkVik2_kUxSPpIQQUyC_iIuIHplIFWeUM`
- Previously used for individual KPI data, now superseded by P-tabs
- Still has `load_individual_kpi_data()` in code but NOT imported anywhere
- Updated Accounts tab (GID 1415492514) still used by page 10

### Indian Promotion Sheet
- **Sheet ID**: `1R505heWwSum89jzRNEfeLy9eNhXfYNMXziSFEj8jtsk`
- Copywriting/content data for 5 agents

## Agents
- **8 P-tab agents**: Mika, Adrian, Jomar, Derr (no data), Ron, Krissa, Jason, Shila
- **5 main sheet agents**: MIKA, ADRIAN, JOMAR, SHILA, KRISSA
- **Excluded**: DER, JD (boss accounts)
- SHEENA removed (resigned)

## Pages (14 total)
| # | Page | File | Description |
|---|------|------|-------------|
| - | Home | `app.py` | Executive dashboard (P-tab data): Running Ads, Creative Work, SMS |
| 1 | Agent Performance | `pages/1_Agent_Performance.py` | 5 tabs: Overview, Individual Overall, By Campaign, Creative Work, SMS |
| 2 | Content Analysis | `pages/2_Content_Analysis.py` | Content similarity detection |
| 3 | Team Overview | `pages/3_Team_Overview.py` | Team comparison charts, radar chart |
| 4 | Report Dashboard | `pages/4_Report_Dashboard.py` | Daily report with agent performance cards |
| 5 | Daily ROI | `pages/5_Daily_ROI.py` | FB vs Google daily ROI comparison |
| 6 | Roll Back | `pages/6_Roll_Back.py` | Roll back data view |
| 7 | Violet | `pages/7_Violet.py` | Violet data view |
| 8 | Counterpart | `pages/8_Counterpart_Performance.py` | FB vs Google counterpart performance |
| 9 | Team Channel | `pages/9_Team_Channel.py` | Team channel view |
| 10 | Updated Accounts | `pages/10_Updated_Accounts.py` | FB account inventory (3 groups) |
| 11 | Pages | `pages/11_Pages.py` | FB Pages data |
| 12 | BM | `pages/12_BM.py` | Business Manager data |
| 13 | KPI Monitoring | `pages/13_KPI_Monitoring.py` | KPI scoring dashboard (auto + manual) |

## KPI Monitoring (Page 13)

### Auto-calculated KPIs (from P-tab data)
| KPI | Weight | Formula | Scoring |
|-----|--------|---------|---------|
| CPA | 25% | `cost / ftd` | 4: $9-$9.9, 3: $10-$13, 2: $14-$15, 1: >$15 |
| ROAS | — | `ARPPU / 57.7 / CPD` | 4: >0.40x, 3: 0.20-0.39x, 2: 0.10-0.19x, 1: <0.10x |
| CVR | 15% | `FTD / Register * 100` | 4: 7-9%, 3: 4-6%, 2: 2-3%, 1: <2% |
| CTR | — | `Clicks / Impressions * 100` | 4: 3-4%, 3: 2-2.9%, 2: 1-1.9%, 1: <0.9% |

### Manual KPIs (scored via dropdowns on dashboard)
| KPI | Weight | KRs Group |
|-----|--------|-----------|
| Campaign Setup Accuracy | — | Campaign Efficiency |
| A/B Testing | — | Campaign Efficiency |
| Reporting Accuracy | 10% | Data & Reporting |
| Data-Driven Insights | — | Data & Reporting |
| Gmail/FB Account Dev | 10% | Account Management |
| Profile Development | — | Account Management |
| Collaboration | 10% | Teamwork |
| Communication | — | Teamwork |

### Important notes
- ROAS uses ARPPU from **daily** data (monthly ARPPU is empty in sheet)
- CTR is **calculated** from clicks/impressions (monthly sheet CTR formula is broken - shows 375% instead of 3.76%)
- CVR = FTD/Register (NOT the sheet's conv_rate which is FTD/Clicks)
- `KPI_PHP_USD_RATE = 57.7` in config.py
- Total weight: Auto 40% + Manual 30% = 70%
- Max weighted score: 2.80 (auto 1.60 + manual 1.20)

## Key Files
| File | Purpose |
|------|---------|
| `config.py` | All configuration: sheet IDs, agent lists, column mappings, KPI rubric |
| `data_loader.py` | Loads main sheet data (performance/content/SMS) via public CSV |
| `channel_data_loader.py` | Loads Channel ROI data via gspread service account. Key functions: `load_agent_performance_data()`, `calculate_kpi_scores()`, `score_kpi()` |
| `daily_report.py` | Generates daily reports (P-tab data only) |
| `send_daily_report.py` | APScheduler: reminders at 1:00/1:30/1:45 PM, report at 2:00 PM Manila time |
| `telegram_reporter.py` | Telegram bot integration (token + chat ID from Streamlit secrets) |
| `app.py` | Main Streamlit home page |

## Telegram Daily Report
- **Bot Token**: In `.streamlit/secrets.toml` or `TELEGRAM_BOT_TOKEN` env var
- **Chat ID**: KPI Ads group (from secrets or `TELEGRAM_CHAT_ID` env var)
- **Chat Listener API**: `https://humble-illumination-production-713f.up.railway.app` (API key: `juan365chat`)
- **Schedule**: 2:00 PM Manila time (reminders at 1:00, 1:30, 1:45 PM)
- **4 messages sent in order**:
  1. By Campaign (T+1) — per-agent ad account breakdowns from P-tab data
  2. Reporting Accuracy Summary — auto-scored from Chat Listener API (`/api/reporting`)
  3. A/B Testing Progress — per-agent primary texts + published ads + KPI score (from Text/AbTest tab)
  4. Account Dev Progress — per-agent Gmail/FB accounts created + KPI score (from Created Assets tab)
- **Long messages**: Auto-split at 4000 chars via `send_long_message()`
- **Run manually**: `python send_daily_report.py --run-now`
- **Run as daemon**: `python send_daily_report.py --daemon`
- **Key functions in send_daily_report.py**:
  - `build_reporting_summary()` — fetches from Chat Listener API
  - `build_ab_testing_summary()` — loads `load_ab_testing_data()` → `generate_ab_testing_section()`
  - `build_account_dev_summary()` — loads `load_created_assets_data()` → `generate_account_dev_section()`
- **Key functions in daily_report.py**:
  - `generate_by_campaign_section(ad_accounts_df, target_date)` — P-tab ad account breakdowns
  - `generate_ab_testing_section(ab_data)` — HTML `<pre>` table: Agent | Texts | Published | Score
  - `generate_account_dev_section(assets_df)` — HTML `<pre>` table: Agent | Gmail | FB Acct | Total | Score

## Conventions
- P-tab data uses lowercase column names: `agent`, `cost`, `ftd`, `register`, `cpr`, `cpd`, `conv_rate`, `impressions`, `clicks`, `ctr`, `arppu`, `roas`
- Agent names in P-tab are title case: Mika, Adrian, etc.
- Google Sheets scope is `spreadsheets.readonly`
- Streamlit secrets at `.streamlit/secrets.toml` (not committed)
- `GOOGLE_CREDENTIALS` env var for cloud deployment (JSON string)
