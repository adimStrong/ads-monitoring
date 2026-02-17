"""KPI - Combined KPI Monitoring and Team KPI"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SIDEBAR_HIDE_CSS

st.set_page_config(page_title="KPI", page_icon="📊", layout="wide")
st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Section-header CSS used by Team KPI tab
st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Import render functions via importlib to avoid double set_page_config
st._is_recharge_import = True
import importlib.util


def _load_render(filename):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(filename.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render_content


_kpi_monitoring_render = _load_render('24_KPI_Monitoring.py')
_team_kpi_render = _load_render('25_Team_KPI.py')
del st._is_recharge_import

st.title("📊 KPI Dashboard")

tab1, tab2 = st.tabs(["📊 KPI Monitoring", "🏆 Team KPI"])

with tab1:
    _kpi_monitoring_render(key_prefix="kpi_km")
with tab2:
    _team_kpi_render(key_prefix="kpi_tk")
