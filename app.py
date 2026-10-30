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

    # ==========================================
    # 2026 SELECTION CALCULATOR MODULE
    # ==========================================
    def run_2026():
        st.title("🇨🇦 Canoe Kayak Canada - 2026 National Team Selection Calculator")
        st.markdown("2026 Season: Best 3 of 5/6 races, penalty fallback handling, and age category standings.")

        year_path = os.path.join(DATA_DIR, "2026")
        os.makedirs(year_path, exist_ok=True)
        year_files = [f for f in os.listdir(year_path) if f.endswith(('.xlsx', '.csv')) and not f.startswith('~$')]

        if not year_files:
            st.info("No results files found in `data/2026/`.")
            return

        target_file = os.path.join(year_path, year_files[0])
        st.caption(f"📁 Loading 2026 selection data from: `2026/{year_files[0]}`")
        
        try:
            if target_file.endswith('.xlsx'):
                xls = pd.ExcelFile(target_file)
                sheet_name = st.selectbox("Select Results Sheet", [s for s in xls.sheet_names if 'MPS' not in s.upper()], key="sheet_2026")
                df_raw = pd.read_excel(target_file, sheet_name=sheet_name)
            else:
                df_raw = pd.read_csv(target_file)
                
            df = df_raw.copy()
            col_map = {}
            for col in df.columns:
                c_str = str(col).strip().upper()
                if c_str in ['EVENT', 'DISCIPLINE', 'LONG EVENT']: col_map[col] = 'EVENT'
                elif c_str in ['RACER', 'ATHLETE', 'NAME', 'FULL NAME']: col_map[col] = 'ATHLETE'
                elif c_str in ['CATEGORY', 'AGE GROUP', 'AGE_GROUP', 'CLASS']: col_map[col] = 'CATEGORY'
                elif c_str in ['PROVINCE', 'PROV', 'PRO']: col_map[col] = 'PROVINCE'
                elif any(k in c_str for k in ['YOB', 'BIRTH', 'DOB', 'AGE']): col_map[col] = 'YOB'
            df = df.rename(columns=col_map)
            
            if 'EVENT' not in df.columns: df['EVENT'] = ''
            if 'ATHLETE' not in df.columns: df['ATHLETE'] = 'Unknown'
            if 'PROVINCE' not in df.columns: df['PROVINCE'] = ''
            if 'YOB' not in df.columns: df['YOB'] = 2000
            
            def extract_year(val):
                if pd.isna(val): return 2000
                match = re.search(r'(19\d{2}|20\d{2})', str(val))
                return int(match.group(1)) if match else 2000
                
            df['YOB'] = df['YOB'].apply(extract_year)
            
            potential_keywords = ['RACE', 'RUN', 'MH', 'OKC', 'DAY', 'SESSION']
            detected_races = [
                c for c in df.columns 
                if any(k in str(c).upper() for k in potential_keywords) and 'RANK' not in str(c).upper() and 'PTS' not in str(c).upper() and 'PEN' not in str(c).upper()
            ]
            active_race_cols = detected_races if detected_races else [c for c in df.columns if 'RACE' in c.upper() or 'RUN' in c.upper()]
            
            filtered_race_cols = []
            for i, rc in enumerate(active_race_cols):
                if i + 1 == 6: continue
                filtered_race_cols.append(rc)
            active_race_cols = filtered_race_cols

            mps_dict = {}
            status = "UNOFFICIAL"
            try:
                xls_full = pd.ExcelFile(target_file)
                mps_sheets = [s for s in xls_full.sheet_names if 'MPS' in s.upper()]
                if mps_sheets:
                    df_mps = pd.read_excel(target_file, sheet_name=mps_sheets[0])
                    full_text = df_mps.astype(str).to_string().upper()
                    if 'OFFICIAL' in full_text and 'UNOFFICIAL' not in full_text: status = "OFFICIAL"
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
                                if val < 2.0: val *= 100.0
                                mps_dict[(ev, cat)] = round(val, 3)
                            except: pass
            except: pass
            
            is_official = (status == "OFFICIAL")
            with st.sidebar:
                st.subheader("📊 2026 MPS Standards")
                if mps_dict:
                    st.dataframe(pd.DataFrame([{"Event": ev, "Category": cat, "Max PPS (%)": f"{val:.3f}%"} for (ev, cat), val in mps_dict.items()]), hide_index=True, use_container_width=True)
                st.markdown("---")
                st.success("🟢 OFFICIAL" if is_official else "🔴 UNOFFICIAL")

            def has_50s_penalty(row, rc):
                for suffix in ['_PEN50', '_PEN', '_FLAG']:
                    if f"{rc}{suffix}" in row and pd.notna(row[f"{rc}{suffix}"]):
                        if str(row[f"{rc}{suffix}"]).strip().upper() in ['50', 'Y', 'YES', 'TRUE', 'PEN50', 'X', '50.0']:
                            return True
                return False

            def get_base(df_all, day_cols):
                discs = ['MK1', 'WK1', 'MC1', 'WC1']
                alias = {'MK1': ['MK1', 'K1M'], 'WK1': ['WK1', 'K1W'], 'MC1': ['MC1', 'C1M'], 'WC1': ['WC1', 'C1W']}
                disc_best = {}
                for d in discs:
                    d_rows = df_all[df_all['EVENT'].str.strip().str.upper().isin([a.upper() for a in alias[d]])]
                    val_recs, clean_recs = [], []
                    for _, r in d_rows.iterrows():
                        for rc in day_cols:
                            if rc not in r: continue
                            t = pd.to_numeric(r.get(rc), errors='coerce')
                            if pd.notna(t) and t < 900:
                                rec = {'athlete': r.get('ATHLETE', 'Unknown'), 'time': t, 'race_col': rc}
                                val_recs.append(rec)
                                if not has_50s_penalty(r, rc): clean_recs.append(rec)
                    if clean_recs:
                        clean_recs.sort(key=lambda x: x['time'])
                        disc_best[d] = clean_recs[0]
                    elif val_recs:
                        val_recs.sort(key=lambda x: x['time'])
                        disc_best[d] = val_recs[0]
                    else: disc_best[d] = None
                times = [v['time'] for v in disc_best.values() if v is not None]
                return round(sum(times) / len(times), 2) if len(times) == 4 else np.nan, disc_best

            day_groups = {}
            if len(active_race_cols) >= 1: day_groups[active_race_cols[0]] = [active_race_cols[0]]
            if len(active_race_cols) >= 3:
                day_groups[active_race_cols[1]] = [active_race_cols[1], active_race_cols[2]]
                day_groups[active_race_cols[2]] = [active_race_cols[1], active_race_cols[2]]
            if len(active_race_cols) >= 5:
                day_groups[active_race_cols[3]] = [active_race_cols[3], active_race_cols[4]]
                day_groups[active_race_cols[4]] = [active_race_cols[3], active_race_cols[4]]
            for rc in active_race_cols:
                if rc not in day_groups: day_groups[rc] = [rc]

            base_scores, base_breakdowns = {}, {}
            for rc in active_race_cols:
                b, d = get_base(df, day_groups.get(rc, [rc]))
                base_scores[rc], base_breakdowns[rc] = b, d
                df[f'{rc}_PPS'] = df[rc].apply(lambda t: round((float(t)/b)*100, 3) if pd.notna(pd.to_numeric(t, errors='coerce')) and float(t)<900 and b else np.nan)

            categories = {'Open': lambda sub: sub, 'U23': lambda sub: sub[(2026 - sub['YOB']) <= 23], 'U18': lambda sub: sub[(2026 - sub['YOB']) <= 18]}
            
            events_list = sorted(df['EVENT'].dropna().unique())
            tabs = st.tabs(list(events_list) + ["Nominations Summary"])
            
            for idx, evt in enumerate(events_list):
                with tabs[idx]:
                    st.markdown(f"### 2026 - {evt} Base Score Breakdown")
                    b_data = []
                    for rc in active_race_cols:
                        bv = base_scores.get(rc, np.nan)
                        det = base_breakdowns.get(rc, {})
                        row = {"Race": rc, "Base Score": f"{bv:.2f}" if pd.notna(bv) else "N/A"}
                        for d in ['MK1', 'WK1', 'MC1', 'WC1']:
                            info = det.get(d)
                            row[d] = f"{info['athlete']} ({info['time']:.2f}s)" if info else "No Time"
                        b_data.append(row)
                    st.dataframe(pd.DataFrame(b_data), hide_index=True, use_container_width=True)
                    st.markdown("---")
                    
                    cat_tabs = st.tabs(["Open", "U23", "U18"])
                    evt_grp = df[df['EVENT'] == evt]
                    
                    for c_idx, c_name in enumerate(['Open', 'U23', 'U18']):
                        with cat_tabs[c_idx]:
                            sub_df = categories[c_name](evt_grp).copy()
                            if sub_df.empty:
                                st.info(f"No athletes in {c_name}.")
                                continue
                                
                            for rc in active_race_cols:
                                pts_map = {}
                                session_res = []
                                for i, r in sub_df.iterrows():
                                    if c_name in ['U23', 'U18'] and active_race_cols.index(rc) == 0:
                                        pts_map[i] = 999
                                        continue
                                    t = pd.to_numeric(r.get(rc), errors='coerce')
                                    if pd.isna(t) or t >= 900: pts_map[i] = 999
                                    else: session_res.append({'idx': i, 'time': t})
                                session_res.sort(key=lambda x: x['time'])
                                for r_i, sr in enumerate(session_res):
                                    pts_map[sr['idx']] = 0 if r_i==0 else (2 if r_i==1 else r_i+1)
                                sub_df[f'{rc}_PTS'] = [pts_map.get(i, 999) for i in sub_df.index]
                                
                            tot_pts, avg_pps, mps_cnt = [], [], []
                            for _, r in sub_df.iterrows():
                                pts, ppss, sat = [], [], 0
                                for rc in active_race_cols:
                                    if c_name in ['U23', 'U18'] and active_race_cols.index(rc) == 0: continue
                                    pts.append(r.get(f'{rc}_PTS', 999))
                                    pps_v = r.get(f'{rc}_PPS', np.nan)
                                    if pd.notna(pps_v):
                                        ppss.append(pps_v)
                                        if pps_v <= mps_dict.get((evt.upper(), c_name.upper()), 105.0): sat += 1
                                best_p = sorted(pts)[:3]
                                tot_pts.append(int(round(sum(best_p))) if any(p < 900 for p in best_p) else 999)
                                best_pps = sorted(ppss)[:3]
                                avg_pps.append(round(sum(best_pps)/len(best_pps), 2) if best_pps else np.nan)
                                mps_cnt.append(sat)
                                
                            sub_df['TOTAL_POINTS'] = tot_pts
                            sub_df['AVG_BEST4_PPS'] = avg_pps
                            sub_df['MPS_SATISFIED_COUNT'] = mps_cnt
                            sub_df = sub_df.sort_values(by=['TOTAL_POINTS', 'AVG_BEST4_PPS']).reset_index(drop=True)
                            sub_df['RANK'] = range(1, len(sub_df)+1)
                            
                            disp_cols = ['RANK', 'ATHLETE', 'EVENT', 'YOB', 'PROVINCE', 'TOTAL_POINTS', 'MPS_SATISFIED_COUNT', 'AVG_BEST4_PPS'] + active_race_cols
                            st.dataframe(sub_df[[c for c in disp_cols if c in sub_df.columns]], hide_index=True, use_container_width=True)

            with tabs[-1]:
                st.subheader("2026 Nominations Summary")
                st.info("Summary view available across event tabs.")

        except Exception as e:
            st.error(f"Error processing 2026 file: {e}")

    # ==========================================
    # 2027 SELECTION CALCULATOR MODULE
    # ==========================================
    def run_2027():
        st.title("🇨🇦 Canoe Kayak Canada - 2027 National Team Selection Calculator")
        st.markdown("2027 Season: Decoupled Open vs U23/U18 race series, best 4 of 6, and official ICF age-filtering rules.")

        year_path = os.path.join(DATA_DIR, "2027")
        os.makedirs(year_path, exist_ok=True)
        year_files = [f for f in os.listdir(year_path) if f.endswith(('.xlsx', '.csv')) and not f.startswith('~$')]

        if not year_files:
            st.info("No results files found in `data/2027/`.")
            return

        target_file = os.path.join(year_path, year_files[0])
        st.caption(f"📁 Loading 2027 selection data from: `2027/{year_files[0]}`")
        
        try:
            if target_file.endswith('.xlsx'):
                xls = pd.ExcelFile(target_file)
                sheet_names = [s for s in xls.sheet_names if 'MPS' not in s.upper()]
                sheet_name = st.selectbox("Select Results Sheet", sheet_names, key="sheet_2027") if len(sheet_names) > 1 else sheet_names[0]
                df_raw = pd.read_excel(target_file, sheet_name=sheet_name)
            else:
                df_raw = pd.read_csv(target_file)
                
            df = df_raw.copy()
            col_map = {}
            for col in df.columns:
                c_str = str(col).strip().upper()
                if c_str in ['EVENT', 'DISCIPLINE', 'LONG EVENT']: col_map[col] = 'EVENT'
                elif c_str in ['RACER', 'ATHLETE', 'NAME', 'FULL NAME']: col_map[col] = 'ATHLETE'
                elif c_str in ['CATEGORY', 'AGE GROUP', 'AGE_GROUP', 'CLASS']: col_map[col] = 'CATEGORY'
                elif c_str in ['PROVINCE', 'PROV', 'PRO']: col_map[col] = 'PROVINCE'
                elif any(k in c_str for k in ['YOB', 'BIRTH', 'DOB', 'AGE']): col_map[col] = 'YOB'
            df = df.rename(columns=col_map)
            
            if 'EVENT' not in df.columns: df['EVENT'] = ''
            if 'ATHLETE' not in df.columns: df['ATHLETE'] = 'Unknown'
            if 'PROVINCE' not in df.columns: df['PROVINCE'] = ''
            if 'YOB' not in df.columns: df['YOB'] = 2000
            
            def extract_year(val):
                if pd.isna(val): return 2000
                match = re.search(r'(19\d{2}|20\d{2})', str(val))
                return int(match.group(1)) if match else 2000
                
            df['YOB'] = df['YOB'].apply(extract_year)
            
            open_race_cols = [c for c in df.columns if 'OPEN_R' in c.upper() and 'RANK' not in c.upper() and 'PTS' not in c.upper() and 'PEN' not in c.
