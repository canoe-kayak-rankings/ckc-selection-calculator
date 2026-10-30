import streamlit as st
import pandas as pd
import numpy as np
import os
import re

st.set_page_config(
    page_title="CKC National Team Selection Calculator",
    page_icon="🇨🇦",
    layout="wide"
)

def find_results_file(year_str):
    search_dirs = [
        os.path.join(os.path.dirname(__file__), "data", year_str),
        os.path.join(os.path.dirname(__file__), "data"),
        os.path.dirname(__file__)
    ]
    for d in search_dirs:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith(('.xlsx', '.csv')) and not f.startswith('~$'):
                        if year_str in f or year_str in os.path.basename(root):
                            return os.path.join(root, f)
    return None

year_folders = ["2027", "2026"]

with st.sidebar:
    st.title("🇨🇦 Navigation")
    selected_year = st.selectbox("📅 Select Competition Year", year_folders)
    st.markdown("---")

def has_50s_penalty(row, rc, all_cols):
    rc_str = str(rc).strip().upper()
    pen_col_name = f"{rc}_PEN50"
    if pen_col_name in row:
        val = row.get(pen_col_name)
        if pd.notna(val):
            val_str = str(val).strip().upper()
            if val_str not in ['NAN', 'NONE', '', '0', '0.0', 'FALSE']:
                return True
                
    for col in all_cols:
        col_u = str(col).strip().upper()
        if rc_str in col_u and any(k in col_u for k in ['PEN', 'FLAG', '50']):
            if col_u != rc_str:
                val = row.get(col)
                if pd.notna(val):
                    val_str = str(val).strip().upper()
                    if val_str not in ['NAN', 'NONE', '', '0', '0.0', 'FALSE']:
                        return True
    return False

def safe_fmt(val):
    if pd.isna(val) or val == '' or val is None:
        return "-"
    try:
        v = float(val)
        if v >= 900:
            return "DNS/DSQ"
        return f"{v:.2f}"
    except (ValueError, TypeError):
        return str(val)

def load_data_source(year_str):
    target_file = find_results_file(year_str)
    if target_file:
        st.caption(f"📁 Auto-loaded file: `{os.path.relpath(target_file, os.path.dirname(__file__))}`")
        if target_file.endswith('.xlsx'):
            xls = pd.ExcelFile(target_file)
            sheet_name = 'results' if 'results' in xls.sheet_names else xls.sheet_names[0]
            return pd.read_excel(target_file, sheet_name=sheet_name), target_file
        else:
            return pd.read_csv(target_file), target_file
    
    st.error(f"❌ No results spreadsheet found for {year_str}. Please ensure your `{year_str}` Excel file is placed in your repository folders.")
    return None, None

def load_mps_standards(target_file):
    mps_dict = {}
    status = "UNOFFICIAL"
    try:
        xls_full = pd.ExcelFile(target_file)
        if 'MPS' in xls_full.sheet_names:
            df_mps = pd.read_excel(target_file, sheet_name='MPS')
            full_text = df_mps.astype(str).to_string().upper()
            if 'OFFICIAL' in full_text and 'UNOFFICIAL' not in full_text: 
                status = "OFFICIAL"
            df_mps.columns = [str(c).strip().upper() for c in df_mps.columns]
            ev_c = next((c for c in df_mps.columns if 'EVENT' in c or 'DISC' in c), None)
            cat_c = next((c for c in df_mps.columns if 'CAT' in c or 'GROUP' in c), None)
            val_c = next((c for c in df_mps.columns if 'PCT' in c or 'VAL' in c or 'STANDARD' in c or 'MPS' in c), None)
            if ev_c and val_c:
                for _, row in df_mps.iterrows():
                    ev = str(row[ev_c]).strip().upper()
                    if not ev or ev == 'NAN': continue
                    cat_raw = str(row[cat_c]).strip().upper() if cat_c and pd.notna(row[cat_c]) else 'OPEN'
                    cat = 'U18' if 'U18' in cat_raw or 'JUNIOR' in cat_raw else ('U23' if 'U23' in cat_raw else 'OPEN')
                    try:
                        val = float(row[val_c])
                        if val < 2.0: 
                            val *= 100.0
                        mps_dict[(ev, cat)] = round(val, 3)
                    except: pass
    except: pass
    return mps_dict, status

table_5_factors = {'MK1': 0.771, 'WK1': 0.745, 'MC1': 0.757, 'WC1': 0.726}

def run_selection_calculator(comp_year_int):
    year_str = str(comp_year_int)
    st.title(f"🇨🇦 Canoe Kayak Canada - {year_str} National Team Selection Calculator")
    st.markdown(f"{year_str} Season: ICF Age-Compliance (Minimum age 15), Table 5 Correction Factors, and Age Category Standings.")

    df_raw, target_file = load_data_source(year_str)
    if df_raw is None:
        return

    df = df_raw.copy()
    col_map = {}
    for col in df.columns:
        c_str = str(col).strip().upper()
        if c_str in ['EVENT', 'DISCIPLINE', 'LONG EVENT', 'CLASS', 'CATEGORY']: col_map[col] = 'EVENT'
        elif c_str in ['RACER', 'ATHLETE', 'NAME', 'FULL NAME', 'ATHLETE NAME']: col_map[col] = 'ATHLETE'
        elif c_str in ['PROVINCE', 'PROV', 'PRO', 'CLUB', 'TEAM']: col_map[col] = 'PROVINCE'
        elif any(k in c_str for k in ['YOB', 'BIRTH', 'DOB', 'AGE', 'YEAR OF BIRTH']): col_map[col] = 'YOB'
    df = df.rename(columns=col_map)

    if 'EVENT' not in df.columns: df['EVENT'] = 'MK1'
    if 'ATHLETE' not in df.columns: df['ATHLETE'] = 'Unknown'
    if 'PROVINCE' not in df.columns: df['PROVINCE'] = ''
    if 'YOB' not in df.columns: df['YOB'] = 2000

    def extract_year(val):
        if pd.isna(val): return 2000
        match = re.search(r'(19\d{2}|20\d{2})', str(val))
        return int(match.group(1)) if match else 2000

    df['YOB'] = df['YOB'].apply(extract_year)

    # Strictly enforce ICF minimum age rule: must turn at least 15 in the competition year
    max_yob_allowed = comp_year_int - 15
    df = df[df['YOB'] <= max_yob_allowed].copy()

    if df.empty:
        st.error(f"❌ No eligible athletes found for {year_str} meeting the minimum age requirement (turning 15 or older in {year_str}, i.e., YOB ≤ {max_yob_allowed}).")
        return

    event_standard_map = {
        'K1M': 'MK1', "MEN'S K1": 'MK1', "MEN'S KAYAK": 'MK1',
        'K1W': 'WK1', "WOMEN'S K1": 'WK1', "WOMEN'S KAYAK": 'WK1',
        'C1M': 'MC1', "MEN'S C1": 'MC1', "MEN'S CANOE": 'MC1',
        'C1W': 'WC1', "WOMEN'S C1": 'WC1', "WOMEN'S CANOE": 'WC1'
    }
    df['EVENT'] = df['EVENT'].apply(lambda ev: event_standard_map.get(str(ev).strip().upper(), str(ev).strip().upper()))

    potential_keywords = ['RACE', 'RUN', 'MH', 'OKC', 'DAY', 'SESSION', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']
    detected_races = [c for c in df.columns if any(k in str(c).upper() for k in potential_keywords) and not any(w in str(c).upper() for w in ['RANK', 'PTS', '_PEN', 'PENALTY', 'FLAG'])]
    active_race_cols = detected_races if detected_races else [c for c in df.columns if 'RACE' in c.upper() or 'RUN' in c.upper()]
    
    if comp_year_int == 2026:
        active_race_cols = [rc for i, rc in enumerate(active_race_cols) if i + 1 != 6]

    for rc in active_race_cols:
        if rc in df.columns:
            df[rc] = pd.to_numeric(df[rc].astype(str).str.replace('DNS', '999').str.replace('DSQ', '999'), errors='coerce').fillna(999)

    mps_dict, status = load_mps_standards(target_file)
    is_official = (status == "OFFICIAL")

    if is_official:
        st.success("🟢 **OFFICIAL SELECTION STANDINGS**: Approved and ratified by the Slalom High Performance Committee.")
    else:
        st
