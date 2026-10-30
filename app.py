import streamlit as st
import os

st.set_page_config(
    page_title="CKC National Team Selection Calculator",
    page_icon="🇨🇦",
    layout="wide"
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

year_folders = [f for f in sorted(os.listdir(DATA_DIR), reverse=True) if os.path.isdir(os.path.join(DATA_DIR, f))]

if not year_folders:
    st.warning(f"No year folders found in `{DATA_DIR}`. Create a folder like `data/2026/` or `data/2027/` and add your selection spreadsheet.")
else:
    with st.sidebar:
        st.title("🇨🇦 Navigation")
        selected_year = st.selectbox("📅 Select Competition Year", year_folders)
        st.markdown("---")

    if selected_year == "2027":
        import app_2027
    elif selected_year == "2026":
        import app_2026
    else:
        st.error(f"No application module configured for year: {selected_year}")
