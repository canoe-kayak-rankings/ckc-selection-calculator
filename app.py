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
                            val *= 100.0  # e.g., 0.983 -> 98.3%
                        mps_dict[(ev, cat)] = round(val, 3)
                    except: pass
    except: pass
    return mps_dict, status

# ==========================================
# 2026 SELECTION CALCULATOR MODULE
# ==========================================
def run_2026():
    st.title("🇨🇦 Canoe Kayak Canada - 2026 National Team Selection Calculator")
    st.markdown("2026 Season: Best 3 of 5 races, 50s penalty fallback handling, and age category standings.")

    df_raw, target_file = load_data_source("2026")
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

    potential_keywords = ['RACE', 'RUN', 'MH', 'OKC', 'DAY', 'SESSION', 'R1', 'R2', 'R3', 'R4', 'R5']
    detected_races = [c for c in df.columns if any(k in str(c).upper() for k in potential_keywords) and not any(w in str(c).upper() for w in ['RANK', 'PTS', '_PEN', 'PENALTY', 'FLAG'])]
    active_race_cols = detected_races if detected_races else [c for c in df.columns if 'RACE' in c.upper() or 'RUN' in c.upper()]
    active_race_cols = [rc for i, rc in enumerate(active_race_cols) if i + 1 != 6]

    for rc in active_race_cols:
        if rc in df.columns:
            df[rc] = pd.to_numeric(df[rc].astype(str).str.replace('DNS', '999').str.replace('DSQ', '999'), errors='coerce').fillna(999)

    mps_dict, status = load_mps_standards(target_file)
    is_official = (status == "OFFICIAL")

    if is_official:
        st.success("🟢 **OFFICIAL SELECTION STANDINGS**: Approved and ratified by the Slalom High Performance Committee.")
    else:
        st.warning("⚠️ **UNOFFICIAL / DRAFT SELECTION STANDINGS**: Preliminary results subject to HPC ratification.")

    with st.sidebar:
        st.subheader("📊 2026 MPS Standards")
        if mps_dict:
            st.dataframe(pd.DataFrame([{"Event": ev, "Category": cat, "Max PPS (%)": f"{val:.3f}%"} for (ev, cat), val in mps_dict.items()]), hide_index=True, use_container_width=True)
        st.markdown("---")
        st.success("🟢 OFFICIAL" if is_official else "🔴 UNOFFICIAL")

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
                        if not has_50s_penalty(r, rc, df_all.columns): clean_recs.append(rec)
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
    if not events_list:
        st.error("No event categories found in spreadsheet.")
        return

    # Base Score Breakdown Table First
    st.markdown("### 📊 2026 4-Boat Base Score Breakdown")
    b_data = []
    for rc in active_race_cols:
        bv = base_scores.get(rc, np.nan)
        det = base_breakdowns.get(rc, {})
        row = {"Race": rc, "Base Score": f"{bv:.2f}" if pd.notna(bv) else "N/A"}
        for d in ['MK1', 'WK1', 'MC1', 'WC1']:
            info = det.get(d)
            row[d] = f"{info['athlete']} ({info['time']:.2f}s) [{info['race_col']}]" if info else "No Time"
        b_data.append(row)
    st.dataframe(pd.DataFrame(b_data), hide_index=True, use_container_width=True)
    st.markdown("---")

    tabs = st.tabs(list(events_list) + ["Nominations Summary"])
    processed_rankings = {}

    for idx, evt in enumerate(events_list):
        processed_rankings[evt] = {}
        with tabs[idx]:
            st.markdown(f"### 2026 - {evt} Team Selection Standings")
            cat_tabs = st.tabs(["Open", "U23", "U18"])
            evt_grp = df[df['EVENT'] == evt]
            
            for c_idx, c_name in enumerate(['Open', 'U23', 'U18']):
                with cat_tabs[c_idx]:
                    sub_df = categories[c_name](evt_grp).copy()
                    if sub_df.empty:
                        st.info(f"No athletes in {c_name}.")
                        processed_rankings[evt][c_name] = pd.DataFrame()
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
                    cat_mps = mps_dict.get((evt.upper(), c_name.upper()), 105.0)
                    for _, r in sub_df.iterrows():
                        pts, ppss, sat = [], [], 0
                        for rc in active_race_cols:
                            if c_name in ['U23', 'U18'] and active_race_cols.index(rc) == 0: continue
                            pts.append(r.get(f'{rc}_PTS', 999))
                            pps_v = r.get(f'{rc}_PPS', np.nan)
                            if pd.notna(pps_v):
                                ppss.append(pps_v)
                                if pps_v <= cat_mps: sat += 1
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
                    processed_rankings[evt][c_name] = sub_df
                    
                    pps_cols = [f"{rc}_PPS" for rc in active_race_cols if f"{rc}_PPS" in sub_df.columns]
                    disp_cols = ['RANK', 'ATHLETE', 'EVENT', 'YOB', 'PROVINCE', 'TOTAL_POINTS', 'MPS_SATISFIED_COUNT', 'AVG_BEST4_PPS'] + active_race_cols + pps_cols
                    available_disp = [c for c in disp_cols if c in sub_df.columns]
                    
                    def highlight_mps(val):
                        try:
                            v = float(val)
                            if v <= cat_mps:
                                return 'background-color: #d4edda; color: #155724;'
                        except:
                            pass
                        return ''

                    pps_subset = [c for c in pps_cols if c in available_disp]
                    fmt_map = {col: safe_fmt for col in active_race_cols + pps_subset + ['AVG_BEST4_PPS']}
                    
                    styled_df = sub_df[available_disp].style.map(
                        highlight_mps, 
                        subset=pps_subset
                    ).format(fmt_map, na_rep="-")

                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    st.caption(f"🟢 Highlighted cells indicate individual selection races satisfying the {c_name} {evt} MPS threshold (≤ {cat_mps:.3f}%).")
                    
                    status_label = "Official" if is_official else "Provisional"
                    valid_nominees = sub_df[sub_df['MPS_SATISFIED_COUNT'] > 0].head(3)
                    st.markdown(f"**{status_label} Top 3 Nominations ({evt} - {c_name}):**")
                    if not valid_nominees.empty:
                        if c_name == 'U23':
                            u18_df = processed_rankings[evt].get('U18', pd.DataFrame())
                            valid_u18 = set(u18_df[u18_df['MPS_SATISFIED_COUNT'] > 0].head(3)['ATHLETE'].tolist()) if not u18_df.empty else set()
                            valid_u23_pool = sub_df[sub_df['MPS_SATISFIED_COUNT'] > 0]
                            u23_nominees = valid_u23_pool.head(3)
                            nom_names = set(u23_nominees['ATHLETE'].tolist())
                            overlap = nom_names.intersection(valid_u18)
                            
                            for _, row in u23_nominees.iterrows():
                                is_ov = row['ATHLETE'] in valid_u18
                                tag = " *(Also selected to Junior/U18 team)*" if is_ov else ""
                                st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | MPS Satisfied: {row['MPS_SATISFIED_COUNT']} | Avg PPS: {safe_fmt(row['AVG_BEST4_PPS'])}%{tag}")
                            
                            if overlap:
                                rem_pool = valid_u23_pool[~valid_u23_pool['ATHLETE'].isin(nom_names)]
                                if not rem_pool.empty:
                                    alt = rem_pool.iloc[0]
                                    st.markdown(f"**🔄 U23 Team Alternate (Activated due to Junior team double-qualification):**")
                                    st.write(f"- **{alt['ATHLETE']}** ({alt['PROVINCE']}) | Points: {alt['TOTAL_POINTS']} | MPS Satisfied: {alt['MPS_SATISFIED_COUNT']} | Avg PPS: {safe_fmt(alt['AVG_BEST4_PPS'])}%")
                        else:
                            for _, row in valid_nominees.iterrows():
                                st.write(f"- **{row['RANK']}. {row['ATHLETE']}** ({row['PROVINCE']}) | Points: {row['TOTAL_POINTS']} | MPS Satisfied: {row['MPS_SATISFIED_COUNT']} | Avg PPS: {safe_fmt(row['AVG_BEST4_PPS'])}%")
                    else:
                        st.info("No athletes in this category met the minimum MPS satisfaction requirement for nomination.")

    with tabs[-1]:
        st.subheader("2026 National Team Nominations Summary")
        for c_name in ['Open', 'U23', 'U18']:
            st.markdown(f"#### {c_name} Category Nominations")
            nom_rows = []
            for evt in events_list:
                df_c = processed_rankings.get(evt, {}).get(c_name, pd.DataFrame())
                if not df_c.empty:
                    valid_n = df_c[df_c['MPS_SATISFIED_COUNT'] > 0].head(3)
                    for _, r in valid_n.iterrows():
                        nom_rows.append({
                            "Event": evt, "Rank": r['RANK'], "Athlete": r['ATHLETE'],
                            "Province": r['PROVINCE'], "YOB": r['YOB'],
                            "Total Points": r['TOTAL_POINTS'], "MPS Count": r['MPS_SATISFIED_COUNT']
                        })
            if nom_rows:
                st.dataframe(pd.DataFrame(nom_rows), hide_index=True, use_container_width=True)
            else:
                st.info(f"No athletes met MPS requirements for {c_name} nomination.")

# ==========================================
# 2027 SELECTION CALCULATOR MODULE
# ==========================================
def run_2027():
    st.title("🇨🇦 Canoe Kayak Canada - 2027 National Team Selection Calculator")
    st.markdown("2027 Season: Decoupled Open vs U2
