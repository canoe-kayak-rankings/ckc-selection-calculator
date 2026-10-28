import streamlit as st
import pandas as pd
import numpy as np
import os
from engine import process_selection_rankings

st.set_page_config(
    page_title="CKC National Team Selection Calculator",
    page_icon="",
    layout="wide"
)

st.title("🇨🇦 Canoe Kayak Canada - National Team Selection Calculator")
st.markdown("Select your competition year and view automated Senior, U23, and Junior selection rankings.")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1. Discover available year folders in data/
year_folders = [f for f in sorted(os.listdir(DATA_DIR), reverse=True) if os.path.isdir(os.path.join(DATA_DIR, f))]

if not year_folders:
    st.warning(f"No year folders found in `{DATA_DIR}`. Please create a folder like `data/2026/` and add your selection spreadsheet.")
else:
    col_yr, col_info = st.columns([1, 2])
    with col_yr:
        selected_year = st.selectbox("📅 Select Competition Year", year_folders)
        
    year_path = os.path.join(DATA_DIR, selected_year)
    year_files = [f for f in os.listdir(year_path) if f.endswith(('.xlsx', '.csv')) and not f.startswith('~$')]
    
    if not year_files:
        st.info(f"No results files found in `{selected_year}/`. Please upload your selection spreadsheet into that folder.")
    else:
        target_file = os.path.join(year_path, year_files[0])
        st.caption(f"📁 Loading selection data for {selected_year} from: `{selected_year}/{year_files[0]}`")
        
        try:
            if target_file.endswith('.xlsx'):
                xls = pd.ExcelFile(target_file)
                sheet_name = st.selectbox("Select Results Sheet", xls.sheet_names)
                df_raw = pd.read_excel(target_file, sheet_name=sheet_name)
            else:
                df_raw = pd.read_csv(target_file)
                
            # Identify potential 6 selection race columns
            potential_races = [c for c in df_raw.columns if any(k in str(c).upper() for k in ['RACE', 'MH', 'OKC', 'DAY'])]
            selected_races = st.multiselect("Select the 6 Selection Race Columns", df_raw.columns.tolist(), default=potential_races[:6] if len(potential_races)>=6 else df_raw.columns.tolist()[-6:])
            
            if len(selected_races) > 0:
                # Category selection tabs
                tab_senior, tab_u23, tab_junior = st.tabs(["🏆 Senior Team Rankings", "🥈 U23 Team Rankings", "🥉 Junior (U18) Team Rankings"])
                
                categories = {
                    "Senior": (tab_senior, None),
                    "U23": (tab_u23, "U23"),
                    "Junior": (tab_junior, "U18")
                }
                
                for cat_name, (tab_obj, cat_filter) in categories.items():
                    with tab_obj:
                        st.subheader(f"{selected_year} {cat_name} Selection Standings (Best 4 of 6)")
                        
                        ranked_df = process_selection_rankings(df_raw, selected_races, cat_filter)
                        
                        if not ranked_df.empty:
                            display_cols = ['RANK', 'ATHLETE', 'EVENT', 'CATEGORY', 'PROVINCE', 'TOTAL_POINTS', 'AVG_BEST4_PPS'] + selected_races
                            available_disp = [c for c in display_cols if c in ranked_df.columns]
                            
                            st.dataframe(ranked_df[available_disp], use_container_width=True, hide_index=True)
                            
                            top_3 = ranked_df.head(3)
                            st.markdown(f"**🌟 Provisional Top 3 {cat_name} Nominations ({selected_year}):**")
                            for _, row in top_3.iterrows():
                                st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['EVENT']} - {row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | Avg PPS: {row['AVG_BEST4_PPS']:.2f}%")
                        else:
                            st.info(f"No athletes found for category: {cat_name}")
                            
        except Exception as e:
            st.error(f"Error processing file: {e}")