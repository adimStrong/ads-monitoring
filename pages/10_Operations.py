"""Operations - Combined view of Created Assets, AB Testing, Chat Monitor, Reporting Accuracy"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SIDEBAR_HIDE_CSS

st.set_page_config(page_title="Operations", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
    .section-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 15px; border-radius: 10px; margin: 20px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(SIDEBAR_HIDE_CSS, unsafe_allow_html=True)

# Import render functions - set flag so page modules don't auto-run main()
st._is_recharge_import = True
import importlib.util

def _load_render(filename):
    """Load render_content from a page file without triggering main()."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(filename.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render_content

_created_assets_render = _load_render('20_Created_Assets.py')
_ab_testing_render = _load_render('21_AB_Testing.py')
_chat_monitor_render = _load_render('22_Chat_Monitor.py')
_reporting_render = _load_render('23_Reporting_Accuracy.py')
del st._is_recharge_import

st.title("⚙️ Operations")

# Shared refresh in sidebar
with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Refresh All", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["🏗️ Created Assets", "🧪 A/B Testing", "💬 Chat Monitor", "📝 Reporting Accuracy"])

with tab1:
    _created_assets_render(key_prefix="ops_ca")
with tab2:
    _ab_testing_render(key_prefix="ops_ab")
with tab3:
    _chat_monitor_render(key_prefix="ops_cm")
with tab4:
    _reporting_render(key_prefix="ops_ra")
