import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from engine import process_selection_rankings, load_mps_lookup

st.set_page_config(
    page_title="CKC National Team Selection Calculator",
    page_icon="🇨🇦",
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
                
            potential_keywords = ['RACE', 'RUN', 'MH', 'OKC', 'DAY', 'SESSION']
            detected_races = [
                c for c in df_raw.columns 
                if any(k in str(c).upper() for k in potential_keywords) and 'RANK' not in str(c).upper() and 'PTS' not in str(c).upper()
            ]
            
            if len(detected_races) >= 6:
                selected_races = detected_races[:6]
            elif len(df_raw.columns) >= 6:
                selected_races = df_raw.columns.tolist()[-6:]
            else:
                selected_races = df_raw.columns.tolist()
                
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
            base_scores = rankings_dict.get('_BASE_SCORES', {})
            base_breakdowns = rankings_dict.get('_BASE_BREAKDOWNS', {})
            
            events_list = sorted([k for k in rankings_dict.keys() if not k.startswith('_')])
            if events_list:
                tabs_labels = [evt for evt in events_list] + ["Nominations Summary"]
                event_tabs = st.tabs(tabs_labels)
                
                # Render Individual Event Tabs
                for idx, evt_name in enumerate(events_list):
                    with event_tabs[idx]:
                        st.markdown("### 4-Boat Base Score Breakdown (MK1, WK1, MC1, WC1)")
                        base_table_data = []
                        
                        active_races_to_show = []
                        for i, rc in enumerate(selected_races):
                            race_idx = i + 1
                            if selection_year_int == 2026 and race_idx == 6:
                                continue
                            active_races_to_show.append(rc)
                            
                        for rc in active_races_to_show:
                            b_val = base_scores.get(rc, np.nan)
                            details = base_breakdowns.get(rc, {})
                            
                            row_data = {"Race Session": rc, "4-Boat Base Score": f"{b_val:.2f}" if pd.notna(b_val) else "N/A"}
                            for disc in ['MK1', 'WK1', 'MC1', 'WC1']:
                                d_info = details.get(disc)
                                if d_info:
                                    row_data[disc] = f"{d_info['athlete']} ({d_info['time']:.2f}s [from {d_info.get('race_col', rc)}])"
                                else:
                                    row_data[disc] = "No Time"
                            base_table_data.append(row_data)
                            
                        if base_table_data:
                            st.dataframe(pd.DataFrame(base_table_data), hide_index=True, use_container_width=True)
                        
                        st.markdown("---")
                        st.subheader(f"{selected_year} - {evt_name} Team Selection Standings")
                        
                        if is_official:
                            st.success("✅ **OFFICIAL SELECTION RANKINGS**: Approved and ratified by the Slalom High Performance Committee.")
                        else:
                            st.warning("⚠️ **UNOFFICIAL / PRELIMINARY DRAFT**: Subject to review and pending final approval by the Slalom High Performance Committee.")
                        
                        cat_tabs = st.tabs(["Open", "U23", "U18"])
                        categories = ['Open', 'U23', 'U18']
                        
                        event_u18_df = rankings_dict[evt_name].get('U18', pd.DataFrame())
                        valid_u18_athletes = set(event_u18_df[event_u18_df['MPS_SATISFIED_COUNT'] > 0].head(3)['ATHLETE'].tolist())
                        
                        event_u23_df = rankings_dict[evt_name].get('U23', pd.DataFrame())
                        valid_u23_pool = event_u23_df[event_u23_df['MPS_SATISFIED_COUNT'] > 0]
                        
                        for cat_idx, cat_name in enumerate(categories):
                            with cat_tabs[cat_idx]:
                                df_cat = rankings_dict[evt_name].get(cat_name, pd.DataFrame())
                                
                                if not df_cat.empty:
                                    race_time_cols = active_races_to_show
                                    pps_cols = [f"{rc}_PPS" for rc in active_races_to_show if f"{rc}_PPS" in df_cat.columns]
                                    
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
                                    format_dict = {col: "{:.2f}" for col in race_time_cols + pps_subset + ['AVG_BEST4_PPS']}
                                    
                                    styled_df = df_cat[available_disp].style.map(
                                        highlight_mps, 
                                        subset=pps_subset
                                    ).format(format_dict, na_rep="-")

                                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                                    st.caption(f"🟢 Highlighted cells indicate individual selection races satisfying the {cat_name} {evt_name} MPS threshold (≤ {cat_mps_val:.3f}%).")
                                    
                                    status_label = "Official" if is_official else "Provisional"
                                    
                                    if cat_name == 'U23':
                                        u23_nominees = valid_u23_pool.head(3)
                                        nominated_names = set(u23_nominees['ATHLETE'].tolist())
                                        overlap_athletes = nominated_names.intersection(valid_u18_athletes)
                                        
                                        st.markdown(f"**{status_label} Top 3 Nominations ({evt_name} - {cat_name}):**")
                                        if not u23_nominees.empty:
                                            for _, row in u23_nominees.iterrows():
                                                is_overlap = row['ATHLETE'] in valid_u18_athletes
                                                tag = " *(Also selected to Junior/U18 team)*" if is_overlap else ""
                                                st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | MPS Satisfied: {row['MPS_SATISFIED_COUNT']} | Avg PPS: {row['AVG_BEST4_PPS']:.2f}%{tag}")
                                            
                                            if overlap_athletes:
                                                remaining_pool = valid_u23_pool[~valid_u23_pool['ATHLETE'].isin(nominated_names)]
                                                if not remaining_pool.empty:
                                                    alternate_row = remaining_pool.iloc[0]
                                                    st.markdown(f"**🔄 U23 Team Alternate (Activated due to Junior team double-qualification):**")
                                                    st.write(f"- **{alternate_row['ATHLETE']}** ({alternate_row['PROVINCE']}) | Points: {alternate_row['TOTAL_POINTS']} | MPS Satisfied: {alternate_row['MPS_SATISFIED_COUNT']} | Avg PPS: {alternate_row['AVG_BEST4_PPS']:.2f}%")
                                        else:
                                            st.info("No athletes in this category met the minimum MPS satisfaction requirement for nomination.")
                                    else:
                                        valid_nominees = df_cat[df_cat['MPS_SATISFIED_COUNT'] > 0].head(3)
                                        st.markdown(f"**{status_label} Top 3 Nominations ({evt_name} - {cat_name}):**")
                                        if not valid_nominees.empty:
                                            for _, row in valid_nominees.iterrows():
                                                st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | MPS Satisfied: {row['MPS_SATISFIED_COUNT']} | Avg PPS: {row['AVG_BEST4_PPS']:.2f}%")
                                        else:
                                            st.info("No athletes in this category met the minimum MPS satisfaction requirement for nomination.")
                                        
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

                # Render "Nominations Summary" Tab (Without Status/Notes Column)
                with event_tabs[-1]:
                    st.subheader(f"{selected_year} National Team Nominations Summary")
                    
                    if is_official:
                        st.success("✅ **OFFICIAL SELECTION REPORT**: Approved and ratified by the Slalom High Performance Committee.")
                    else:
                        st.warning("⚠️ **UNOFFICIAL / PRELIMINARY DRAFT REPORT**: Subject to review and pending final approval by the Slalom High Performance Committee.")
                    
                    st.markdown("Comprehensive overview of all top 3 nominated athletes who have satisfied the minimum MPS threshold, separated by age category.")
                    
                    categories = ['Open', 'U23', 'U18']
                    
                    for cat_name in categories:
                        st.markdown(f"### {cat_name} Category Nominations")
                        cat_rows = []
                        
                        for evt_name in events_list:
                            df_u18 = rankings_dict[evt_name].get('U18', pd.DataFrame())
                            v_u18_names = set(df_u18[df_u18['MPS_SATISFIED_COUNT'] > 0].head(3)['ATHLETE'].tolist())
                            
                            df_cat = rankings_dict[evt_name].get(cat_name, pd.DataFrame())
                            if not df_cat.empty:
                                valid_pool = df_cat[df_cat['MPS_SATISFIED_COUNT'] > 0]
                                nominees = valid_pool.head(3)
                                
                                for _, row in nominees.iterrows():
                                    cat_rows.append({
                                        "Event": evt_name,
                                        "Rank": row['RANK'],
                                        "Athlete": row['ATHLETE'],
                                        "Province": row['PROVINCE'],
                                        "YOB": row['YOB_INT'],
                                        "Total Points": row['TOTAL_POINTS'],
                                        "MPS Satisfied": row['MPS_SATISFIED_COUNT']
                                    })
                                    
                                if cat_name == 'U23':
                                    nominee_names = set(nominees['ATHLETE'].tolist())
                                    if nominee_names.intersection(v_u18_names):
                                        remaining = valid_pool[~valid_pool['ATHLETE'].isin(nominee_names)]
                                        if not remaining.empty:
                                            alt_row = remaining.iloc[0]
                                            cat_rows.append({
                                                "Event": evt_name,
                                                "Rank": f"Alt ({alt_row['RANK']})",
                                                "Athlete": alt_row['ATHLETE'],
                                                "Province": alt_row['PROVINCE'],
                                                "YOB": alt_row['YOB_INT'],
                                                "Total Points": alt_row['TOTAL_POINTS'],
                                                "MPS Satisfied": alt_row['MPS_SATISFIED_COUNT']
                                            })
                                    
                        if cat_rows:
                            df_cat_summary = pd.DataFrame(cat_rows)
                            st.dataframe(df_cat_summary, use_container_width=True, hide_index=True)
                            
                            file_status_tag = "OFFICIAL" if is_official else "UNOFFICIAL"
                            cat_csv = df_cat_summary.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label=f"📥 Download {selected_year} {cat_name} Nominations Report ({file_status_tag})",
                                data=cat_csv,
                                file_name=f"CKC_{selected_year}_{cat_name}_Nominations_{file_status_tag}.csv",
                                mime="text/csv",
                                key=f"dl_summary_{cat_name}"
                            )
                        else:
                            st.info(f"No athletes met the criteria for nomination in the {cat_name} category.")
                        
                        st.markdown("---")
            else:
                st.warning("No valid event columns found in dataset.")
                        
        except Exception as e:
            st.error(f"Error processing file: {e}")
