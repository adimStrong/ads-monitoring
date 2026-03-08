"""
Historical / Combined Data
Monthly report combining Roll Back + Violet data from Overall Channel,
with Cost from Daily Summary Advertising V2 (FB, up to Dec 2025) and Overall Channel (Google all, FB 2026+).
"""
import os
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_data_loader import get_google_client

# --- Constants ---
CHANNEL_ROI_SHEET_ID = "1P6GoOQUa7FdiGKPLJiytMzYvkRJwt7jPmqqHo0p0p0c"
OVERALL_CHANNEL_GID = 667960594

DAILY_SUMMARY_SHEET_ID = "1zgSsEIBNxeTRzV0YtD04sv0RZ94gaekA8_su_pF7QoU"
FB_ADS_V2_GID = 269760412

KPI_PHP_USD_RATE = 57.7  # PHP to USD conversion for ROAS calc

MONTH_ORDER = [
    'June 2025', 'July 2025', 'August 2025', 'September 2025',
    'October 2025', 'November 2025', 'December 2025',
    'January 2026', 'February 2026', 'March 2026',
    'April 2026', 'May 2026', 'June 2026',
    'July 2026', 'August 2026', 'September 2026',
    'October 2026', 'November 2026', 'December 2026',
]


def parse_currency(val):
    """Parse currency string like '$1,234.56' or '₱1,234' to float."""
    if not val or not str(val).strip():
        return 0.0
    s = str(val).strip().replace(',', '').replace('$', '').replace('₱', '').replace(' ', '')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def parse_int_val(val):
    """Parse integer string like '1,234' to int."""
    if not val or not str(val).strip():
        return 0
    s = str(val).strip().replace(',', '')
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


@st.cache_data(ttl=300)
def load_overall_channel():
    """Load Overall Channel tab - 3 sections each for Google (cols B-J) and FB (cols L-T)."""
    client = get_google_client()
    if client is None:
        return None, None

    ss = client.open_by_key(CHANNEL_ROI_SHEET_ID)
    ws = ss.get_worksheet_by_id(OVERALL_CHANNEL_GID)
    rows = ws.get_all_values()

    google_data = {}
    fb_data = {}

    # --- GOOGLE side (cols B=1 to J=9) ---
    # Daily ROI: rows 5-16 (header at row 4)
    # Roll Back: rows 21-32 (header at row 20)
    # Violet: rows 37-48 (header at row 36)

    # Google Daily ROI (rows 5-16): Month(1), Advertiser(2), Register(3), FTD(4), Deposit(5), ARPPU(6), Cost(7)
    for i in range(4, 16):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[1].strip()
        if not month or month in ('MONTH', ''):
            continue
        google_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        google_data[month]['cost'] = parse_currency(row[7])  # Cost col H

    # Google Roll Back (rows 21-32)
    for i in range(20, 32):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[1].strip()
        if not month or month in ('MONTH', ''):
            continue
        google_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        google_data[month]['register'] += parse_int_val(row[3])  # Register
        google_data[month]['ftd'] += parse_int_val(row[4])       # FTD
        google_data[month]['recharge'] += parse_currency(row[5])  # Deposit Amount

    # Google Violet (rows 37-48): Month(1), Advertiser(2), First Recharge(3), Recharge Amount(4), ARPPU(5), Cost(6)
    for i in range(36, 48):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[1].strip()
        if not month or month in ('MONTH', ''):
            continue
        google_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        # Violet has no register
        google_data[month]['ftd'] += parse_int_val(row[3])       # First Recharge (= FTD)
        google_data[month]['recharge'] += parse_currency(row[4])  # Recharge Amount

    # --- FACEBOOK side (cols L=11 to T=19) ---
    # FB Daily ROI: rows 5-16
    # FB Roll Back: rows 21-32
    # FB Violet: rows 37-48

    # FB Daily ROI - only need Cost for 2026
    for i in range(4, 16):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[11].strip() if len(row) > 11 else ''
        if not month or month in ('MONTH', ''):
            continue
        fb_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        # FB cost from Overall Channel only for 2026+
        if '2026' in month:
            fb_data[month]['cost'] = parse_currency(row[17])  # Cost col R

    # FB Roll Back (rows 21-32)
    for i in range(20, 32):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[11].strip() if len(row) > 11 else ''
        if not month or month in ('MONTH', ''):
            continue
        fb_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        fb_data[month]['register'] += parse_int_val(row[13])  # Register
        fb_data[month]['ftd'] += parse_int_val(row[14])       # FTD
        fb_data[month]['recharge'] += parse_currency(row[15])  # Deposit Amount

    # FB Violet (rows 37-48): cols L-T, First Recharge(13), Recharge Amount(14)
    for i in range(36, 48):
        if i >= len(rows):
            break
        row = rows[i]
        month = row[11].strip() if len(row) > 11 else ''
        if not month or month in ('MONTH', ''):
            continue
        fb_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
        fb_data[month]['ftd'] += parse_int_val(row[13])       # First Recharge
        fb_data[month]['recharge'] += parse_currency(row[14])  # Recharge Amount

    return google_data, fb_data


@st.cache_data(ttl=300)
def load_fb_cost_daily_summary():
    """Load FB cost from Daily Summary Advertising V2 (monthly rows, up to Dec 2025)."""
    client = get_google_client()
    if client is None:
        return {}

    ss = client.open_by_key(DAILY_SUMMARY_SHEET_ID)
    ws = ss.get_worksheet_by_id(FB_ADS_V2_GID)
    rows = ws.get_all_values()

    # Monthly rows: row 4-12 (index 3-11)
    # Col A=Month name, Col B=Cost
    month_map = {
        'June': 'June 2025', 'July': 'July 2025', 'August': 'August 2025',
        'September': 'September 2025', 'October': 'October 2025',
        'November': 'November 2025', 'December': 'December 2025',
        'January': 'January 2026', 'February': 'February 2026',
        'March': 'March 2026',
    }

    fb_cost = {}
    for i in range(3, min(15, len(rows))):
        row = rows[i]
        month_name = row[0].strip()
        if month_name in month_map:
            full_month = month_map[month_name]
            # Only use cost up to December 2025
            if '2025' in full_month:
                fb_cost[full_month] = parse_currency(row[1])

    return fb_cost


def build_monthly_table(data, label):
    """Build a DataFrame from the monthly dict."""
    records = []
    for month in MONTH_ORDER:
        if month in data:
            d = data[month]
            if d['register'] == 0 and d['ftd'] == 0 and d['recharge'] == 0 and d['cost'] == 0:
                continue
            cost = d['cost']
            reg = d['register']
            ftd = d['ftd']
            recharge = d['recharge']
            cpr = cost / reg if reg > 0 else 0
            cpfd = cost / ftd if ftd > 0 else 0
            arppu = recharge / ftd if ftd > 0 else 0
            conv_rate = (ftd / reg * 100) if reg > 0 else 0
            # ROAS = Recharge(₱) / (Cost($) * PHP_USD_RATE)
            cost_php = cost * KPI_PHP_USD_RATE
            roas = (recharge / cost_php * 100) if cost_php > 0 else 0
            records.append({
                'Month': month,
                'Register': reg,
                'FTD': ftd,
                'Recharge (₱)': recharge,
                'Cost ($)': cost,
                'CPR ($)': cpr,
                'CPFD ($)': cpfd,
                'ARPPU (₱)': arppu,
                'Conv Rate (%)': conv_rate,
                'ROAS (%)': roas,
            })
    return pd.DataFrame(records)


def format_table(df):
    """Format the dataframe for display."""
    if df.empty:
        return df
    styled = df.copy()
    styled['Register'] = styled['Register'].apply(lambda x: f"{x:,}")
    styled['FTD'] = styled['FTD'].apply(lambda x: f"{x:,}")
    styled['Recharge (₱)'] = styled['Recharge (₱)'].apply(lambda x: f"₱{x:,.2f}")
    styled['Cost ($)'] = styled['Cost ($)'].apply(lambda x: f"${x:,.2f}")
    styled['CPR ($)'] = styled['CPR ($)'].apply(lambda x: f"${x:,.2f}")
    styled['CPFD ($)'] = styled['CPFD ($)'].apply(lambda x: f"${x:,.2f}")
    styled['ARPPU (₱)'] = styled['ARPPU (₱)'].apply(lambda x: f"₱{x:,.2f}")
    styled['Conv Rate (%)'] = styled['Conv Rate (%)'].apply(lambda x: f"{x:,.2f}%")
    styled['ROAS (%)'] = styled['ROAS (%)'].apply(lambda x: f"{x:,.2f}%")
    return styled


def make_bar_chart(df, metric_col, title, color, prefix=''):
    """Create a bar chart for a metric."""
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['Month'],
        y=df[metric_col],
        marker_color=color,
        text=df[metric_col].apply(lambda x: f"{prefix}{x:,.0f}" if x >= 1 else f"{prefix}{x:,.2f}"),
        textposition='outside',
        textfont=dict(size=11),
    ))
    fig.update_layout(
        title=title,
        xaxis_title='Month',
        yaxis_title=metric_col,
        template='plotly_white',
        height=400,
        margin=dict(t=50, b=50),
        xaxis=dict(tickangle=-45),
    )
    return fig


def render_channel_view(data, channel_name, color_primary, color_secondary):
    """Render a single channel view with table + charts."""
    df = build_monthly_table(data, channel_name)

    if df.empty:
        st.warning(f"No {channel_name} data available.")
        return

    # Summary metrics
    total_register = df['Register'].sum()
    total_ftd = df['FTD'].sum()
    total_recharge = df['Recharge (₱)'].sum()
    total_cost = df['Cost ($)'].sum()

    avg_cpr = total_cost / total_register if total_register > 0 else 0
    avg_cpfd = total_cost / total_ftd if total_ftd > 0 else 0
    avg_arppu = total_recharge / total_ftd if total_ftd > 0 else 0
    overall_conv = (total_ftd / total_register * 100) if total_register > 0 else 0
    total_cost_php = total_cost * KPI_PHP_USD_RATE
    overall_roas = (total_recharge / total_cost_php * 100) if total_cost_php > 0 else 0

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("Total Register", f"{total_register:,}")
    r1c2.metric("Total FTD", f"{total_ftd:,}")
    r1c3.metric("Total Recharge", f"₱{total_recharge:,.2f}")
    r1c4.metric("Total Cost", f"${total_cost:,.2f}")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    r2c1.metric("Avg CPR", f"${avg_cpr:,.2f}")
    r2c2.metric("Avg CPFD", f"${avg_cpfd:,.2f}")
    r2c3.metric("Avg ARPPU", f"₱{avg_arppu:,.2f}")
    r2c4.metric("Conv Rate", f"{overall_conv:,.2f}%")
    r2c5.metric("ROAS", f"{overall_roas:,.2f}%")

    # Table
    st.dataframe(format_table(df), use_container_width=True, hide_index=True)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        fig = make_bar_chart(df, 'Register', f'{channel_name} - Monthly Register', color_primary)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        fig = make_bar_chart(df, 'Recharge (₱)', f'{channel_name} - Monthly Recharge', color_secondary, '₱')
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = make_bar_chart(df, 'FTD', f'{channel_name} - Monthly FTD', color_primary)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        fig = make_bar_chart(df, 'Cost ($)', f'{channel_name} - Monthly Cost', color_secondary, '$')
        if fig:
            st.plotly_chart(fig, use_container_width=True)


# --- Main ---
st.set_page_config(page_title="Historical Combined Data", page_icon="📊", layout="wide")
st.title("📊 Historical / Combined Data")
st.markdown("Monthly report: Roll Back + Violet combined | Register, FTD, Recharge, Cost")

with st.spinner("Loading data..."):
    google_data, fb_data = load_overall_channel()
    fb_cost_old = load_fb_cost_daily_summary()

if google_data is None or fb_data is None:
    st.error("Failed to load data. Check Google credentials.")
    st.stop()

# Merge FB cost from Daily Summary (up to Dec 2025) into fb_data
for month, cost in fb_cost_old.items():
    fb_data.setdefault(month, {'register': 0, 'ftd': 0, 'recharge': 0, 'cost': 0})
    fb_data[month]['cost'] = cost

# Two tabs
tab_fb, tab_google = st.tabs(["🔵 Facebook Ads", "🟢 Google Ads"])

with tab_fb:
    st.subheader("Facebook Ads - Monthly (Roll Back + Violet)")
    render_channel_view(fb_data, "Facebook", "#3b82f6", "#60a5fa")

with tab_google:
    st.subheader("Google Ads - Monthly (Roll Back + Violet)")
    render_channel_view(google_data, "Google", "#22c55e", "#4ade80")

st.caption("Data: Roll Back + Violet from Overall Channel | FB Cost (≤Dec 2025) from Daily Summary Advertising V2")
