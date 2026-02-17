"""Team - Combined Team Overview and Team Channel By Team"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SIDEBAR_HIDE_CSS

st.set_page_config(page_title="Team", page_icon="👥", layout="wide")

st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Import render functions
st._is_recharge_import = True
import importlib.util


def _load_render(filename):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(filename.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render_content


_team_overview_render = _load_render('26_Team_Overview.py')
_team_channel_render = _load_render('27_Team_Channel_By_Team.py')
del st._is_recharge_import

st.title("👥 Team Dashboard")

tab1, tab2 = st.tabs(["📡 Team Overview", "🏷️ Team Channel By Team"])

with tab1:
    _team_overview_render(key_prefix="tm_to")
with tab2:
    _team_channel_render(key_prefix="tm_tc")
