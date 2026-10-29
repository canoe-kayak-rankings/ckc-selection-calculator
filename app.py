import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from engine import process_selection_rankings, load_mps_lookup

st.set_page_config(
    page_title="CKC National Team Selection Calculator",
    page_icon="🚣",
    layout="wide"
)

st.title("🇨🇦 Canoe Kayak Canada - National Team Selection Calculator")
st.markdown("Select competition year, view event leaderboards by age category (Open, U23, U18 based on YOB), track MPS compliance, and download official nomination reports.")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

year_folders = [f for f in sorted(os.listdir(DATA_DIR), reverse=True) if os.path.isdir(os.path.join(DATA_DIR, f))]

if not year_folders:
    st.warning(f"No year folders found in `{DATA_DIR}`. Create a folder like `data/2026/` and add your selection spreadsheet.")
else:
    col_yr, _ = st.columns([1, 2])
    with col_yr:
        selected_year = st.selectbox("📅 Select Competition Year", year_folders)
        
    year_path = os.path.join(DATA_DIR, selected_year)
    year_files = [f for f in os.listdir(year_path) if f.endswith(('.xlsx', '.csv')) and not f.startswith('~$')]
    
    if not year_files:
        st.info(f"No results files found in `{selected_year}/`.")
    else:
        target_file = os.path.join(year_path, year_files[0])
        st.caption(f"📁 Loading selection data for {selected_year} from: `{selected_year}/{year_files[0]}`")
        
        try:
            if target_file.endswith('.xlsx'):
                xls = pd.ExcelFile(target_file)
                sheet_name = st.selectbox("Select Results Sheet", [s for s in xls.sheet_names if 'MPS' not in s.upper()])
                df_raw = pd.read_excel(target_file, sheet_name=sheet_name)
            else:
                df_raw = pd.read_csv(target_file)
                
            potential_races = [c for c in df_raw.columns if any(k in str(c).upper() for k in ['RACE', 'MH', 'OKC', 'DAY'])]
            selected_races = st.multiselect("Select the 6 Selection Race Columns", df_raw.columns.tolist(), default=potential_races[:6] if len(potential_races)>=6 else df_raw.columns.tolist()[-6:])
            
            if len(selected_races) > 0:
                selection_year_int = int(selected_year)
                
                mps_dict, file_status = load_mps_lookup(target_file)
                is_official = (file_status == "OFFICIAL")
                
                with st.sidebar:
                    st.subheader(f"📊 {selected_year} MPS Standards")
                    if mps_dict:
                        mps_df_display = pd.DataFrame([
                            {"Event": ev, "Category": cat, "Max PPS (%)": f"{val:.3f}%"} 
                            for (ev, cat), val in mps_dict.items()
                        ])
                        st.dataframe(mps_df_display, hide_index=True, use_container_width=True)
                    else:
                        st.info("No 'MPS' sheet found in Excel workbook.")
                        
                    st.markdown("---")
                    st.subheader("📌 Publication Status")
                    if is_official:
                        st.success("🟢 OFFICIAL (Ratified)")
                    else:
                        st.warning("🔴 UNOFFICIAL (Draft)")

                rankings_dict = process_selection_rankings(df_raw, selected_races, selection_year=selection_year_int, mps_dict=mps_dict)
                
                events_list = sorted(list(rankings_dict.keys()))
                if events_list:
                    event_tabs = st.tabs([f"🚣 {evt}" for evt in events_list])
                    
                    for evt_name, evt_tab in zip(events_list, event_tabs):
                        with evt_tab:
                            st.subheader(f"{selected_year} - {evt_name} Team Selection Standings")
                            
                            if is_official:
                                st.success("✅ **OFFICIAL SELECTION RANKINGS**: Approved and ratified by the Slalom High Performance Committee.")
                            else:
                                st.warning("⚠️ **UNOFFICIAL / PRELIMINARY DRAFT**: Subject to review and pending final approval by the Slalom High Performance Committee.")
                            
                            cat_tabs = st.tabs(["🏆 Open (Senior)", "🥈 U23", "🥉 U18 (Junior)"])
                            categories = ['Open', 'U23', 'U18']
                            
                            for cat_name, cat_tab in zip(categories, cat_tabs):
                                with cat_tab:
                                    df_cat = rankings_dict[evt_name].get(cat_name, pd.DataFrame())
                                    
                                    if not df_cat.empty:
                                        race_time_cols = selected_races
                                        pps_cols = [f"{rc}_PPS" for rc in selected_races if f"{rc}_PPS" in df_cat.columns]
                                        
                                        display_cols = ['RANK', 'ATHLETE', 'EVENT', 'YOB_INT', 'PROVINCE', 'TOTAL_POINTS', 'MPS_SATISFIED_COUNT', 'AVG_BEST4_PPS'] + race_time_cols + pps_cols
                                        available_disp = [c for c in display_cols if c in df_cat.columns]
                                        
                                        cat_mps_val = mps_dict.get((evt_name.upper(), cat_name.upper()), 105.0)
                                        
                                        def highlight_mps(val):
                                            try:
                                                v = float(val)
                                                if v <= cat_mps_val:
                                                    return 'background-color: #d4edda; color: #155724;'
                                            except:
                                                pass
                                            return ''

                                        pps_subset = [c for c in pps_cols if c in available_disp]
                                        
                                        # Format float columns to 2 decimal places for clean display
                                        format_dict = {col: "{:.2f}" for col in race_time_cols + pps_subset + ['AVG_BEST4_PPS']}
                                        
                                        styled_df = df_cat[available_disp].style.map(
                                            highlight_mps, 
                                            subset=pps_subset
                                        ).format(format_dict, na_rep="-")

                                        st.dataframe(styled_df, use_container_width=True, hide_index=True)
                                        st.caption(f"🟢 Highlighted cells indicate individual selection races satisfying the {cat_name} {evt_name} MPS threshold (≤ {cat_mps_val:.3f}%).")
                                        
                                        top_3 = df_cat.head(3)
                                        status_label = "Official" if is_official else "Provisional"
                                        st.markdown(f"**🌟 {status_label} Top 3 Nominations ({evt_name} - {cat_name}):**")
                                        for _, row in top_3.iterrows():
                                            st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | MPS Satisfied: {row['MPS_SATISFIED_COUNT']} | Avg PPS: {row['AVG_BEST4_PPS']:.2f}%")
                                            
                                        file_status_tag = "OFFICIAL" if is_official else "UNOFFICIAL"
                                        csv_filename = f"CKC_{selected_year}_{evt_name}_{cat_name}_{file_status_tag}_rankings.csv"
                                        
                                        csv_data = df_cat[available_disp].to_csv(index=False).encode('utf-8')
                                        st.download_button(
                                            label=f"📥 Download {selected_year} {evt_name} {cat_name} Report ({file_status_tag})",
                                            data=csv_data,
                                            file_name=csv_filename,
                                            mime="text/csv",
                                            key=f"dl_{evt_name}_{cat_name}_{selected_year}_{file_status_tag}"
                                        )
                                    else:
                                        st.info(f"No eligible athletes found for {evt_name} in category {cat_name}.")
                else:
                    st.warning("No valid event columns found in dataset.")
                            
        except Exception as e:
            st.error(f"Error processing file: {e}")
