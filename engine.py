import pandas as pd
import numpy as np
import re

def normalize_columns(df):
    col_map = {}
    for col in df.columns:
        c_str = str(col).strip().upper()
        if c_str in ['EVENT', 'DISCIPLINE', 'LONG EVENT']:
            col_map[col] = 'EVENT'
        elif c_str in ['RACER', 'ATHLETE', 'NAME', 'FULL NAME']:
            col_map[col] = 'ATHLETE'
        elif c_str in ['CATEGORY', 'AGE GROUP', 'AGE_GROUP', 'CLASS']:
            col_map[col] = 'CATEGORY'
        elif c_str in ['PROVINCE', 'PROV', 'PRO']:
            col_map[col] = 'PROVINCE'
        elif c_str in ['YOB', 'BIRTHYEAR', 'YEAR OF BIRTH', 'BIRTHDATE (YYYY/MM/DD)', 'BIRTHDATE']:
            col_map[col] = 'YOB'
            
    df_renamed = df.rename(columns=col_map)
    
    if 'EVENT' not in df_renamed.columns:
        df_renamed['EVENT'] = ''
    if 'ATHLETE' not in df_renamed.columns:
        if 'First Name' in df_renamed.columns and 'Last Name' in df_renamed.columns:
            df_renamed['ATHLETE'] = df_renamed['First Name'].fillna('') + ' ' + df_renamed['Last Name'].fillna('')
        else:
            df_renamed['ATHLETE'] = 'Unknown'
    if 'PROVINCE' not in df_renamed.columns:
        df_renamed['PROVINCE'] = ''
    if 'YOB' not in df_renamed.columns:
        df_renamed['YOB'] = 2000
        
    return df_renamed

def extract_year(val):
    if pd.isna(val):
        return 2000
    match = re.search(r'(19\d{2}|20\d{2})', str(val))
    if match:
        return int(match.group(1))
    try:
        return int(float(val))
    except:
        return 2000

def calculate_four_boat_base(df_race_day):
    lowest_times = {}
    event_alias = {
        'MK1': ['MK1', 'K1M', "MEN'S K1", "MEN'S KAYAK"],
        'WK1': ['WK1', 'K1W', "WOMEN'S K1", "WOMEN'S KAYAK"],
        'MC1': ['MC1', 'C1M', "MEN'S C1", "MEN'S CANOE"],
        'WC1': ['WC1', 'C1W', "WOMEN'S C1", "WOMEN'S CANOE"]
    }
    
    for std_disc, aliases in event_alias.items():
        disc_rows = df_race_day[df_race_day['EVENT'].str.strip().str.upper().isin([a.upper() for a in aliases])]
        valid_times = pd.to_numeric(disc_rows['TIME'], errors='coerce').dropna()
        lowest_times[std_disc] = valid_times.min() if not valid_times.empty else np.nan
        
    valid_vals = [v for v in lowest_times.values() if pd.notna(v) and v > 0]
    if len(valid_vals) == 4:
        return round(sum(valid_vals) / 4.0, 2)
    return np.nan

def load_mps_lookup(target_file):
    mps_dict = {}
    status = "UNOFFICIAL"
    try:
        xls = pd.ExcelFile(target_file)
        matching_sheets = [s for s in xls.sheet_names if 'MPS' in s.upper()]
        if matching_sheets:
            df_mps = pd.read_excel(target_file, sheet_name=matching_sheets[0])
            
            full_text = df_mps.astype(str).to_string().upper()
            if 'OFFICIAL' in full_text and 'UNOFFICIAL' not in full_text:
                status = "OFFICIAL"
            elif 'STATUS: OFFICIAL' in full_text or 'STATUS = OFFICIAL' in full_text:
                status = "OFFICIAL"
                
            df_mps.columns = [str(c).strip().upper() for c in df_mps.columns]
            
            event_col = next((c for c in df_mps.columns if 'EVENT' in c or 'DISC' in c), None)
            cat_col = next((c for c in df_mps.columns if 'CAT' in c or 'GROUP' in c), None)
            val_col = next((c for c in df_mps.columns if 'PCT' in c or 'VAL' in c or 'STANDARD' in c or 'MPS' in c), None)
            
            if event_col and cat_col and val_col:
                for _, row in df_mps.iterrows():
                    ev = str(row[event_col]).strip().upper()
                    cat_raw = str(row[cat_col]).strip().upper()
                    
                    if ev == 'STATUS' or cat_raw == 'STATUS':
                        if 'OFFICIAL' in str(row[val_col]).upper():
                            status = "OFFICIAL"
                        continue
                    
                    cat = cat_raw
                    if 'U18' in cat_raw or 'JUNIOR' in cat_raw or 'U-18' in cat_raw:
                        cat = 'U18'
                    elif 'U23' in cat_raw or 'UNDER 23' in cat_raw or 'U-23' in cat_raw:
                        cat = 'U23'
                    elif 'OPEN' in cat_raw or 'SENIOR' in cat_raw:
                        cat = 'Open'
                        
                    try:
                        val = float(row[val_col])
                        if val < 2.0:
                            val = val * 100.0
                        mps_dict[(ev, cat)] = round(val, 2)
                    except:
                        pass
    except Exception as e:
        print(f"Could not load MPS sheet: {e}")
        
    return mps_dict, status

def get_points_for_rank(rank):
    if rank == 1: return 0
    elif rank == 2: return 2
    elif rank >= 3: return rank
    return 999

def process_selection_rankings(df_raw, race_cols, selection_year=2026, mps_dict=None):
    df = normalize_columns(df_raw.copy())
    df['YOB_INT'] = df['YOB'].apply(extract_year)
    
    if selection_year == 2026:
        df = df[df['YOB_INT'] < 2012].copy()
    
    active_race_cols = []
    for i, rc in enumerate(race_cols):
        race_idx = i + 1
        if selection_year == 2026 and race_idx == 6:
            continue
        active_race_cols.append(rc)
    
    event_standard_map = {
        'K1M': 'MK1', "MEN'S K1": 'MK1', "MEN'S KAYAK": 'MK1',
        'K1W': 'WK1', "WOMEN'S K1": 'WK1', "WOMEN'S KAYAK": 'WK1',
        'C1M': 'MC1', "MEN'S C1": 'MC1', "MEN'S CANOE": 'MC1',
        'C1W': 'WC1', "WOMEN'S C1": 'WC1', "WOMEN'S CANOE": 'WC1'
    }
    df['EVENT'] = df['EVENT'].apply(lambda ev: event_standard_map.get(str(ev).strip().upper(), str(ev).strip().upper()))

    # Calculate base scores for each race session
    base_scores = {}
    for rc in active_race_cols:
        session_df = df[['EVENT', rc]].rename(columns={rc: 'TIME'})
        base_scores[rc] = calculate_four_boat_base(session_df)

    # Calculate PPS for all athletes across all active races
    for rc in active_race_cols:
        b_score = base_scores.get(rc, np.nan)
        pps_list = []
        for _, row in df.iterrows():
            time_val = pd.to_numeric(row.get(rc), errors='coerce')
            if pd.isna(time_val) or time_val >= 900:
                pps_list.append(np.nan)
            else:
                pps = (time_val / b_score) * 100 if pd.notna(b_score) and b_score > 0 else np.nan
                pps_list.append(round(pps, 2))
        df[f'{rc}_PPS'] = pps_list

    # Define category filters
    if selection_year == 2026:
        categories = {
            'Open': lambda df_sub: df_sub,
            'U23': lambda df_sub: df_sub[(df_sub['YOB_INT'] >= 2003) & (df_sub['YOB_INT'] <= 2011)],
            'U18': lambda df_sub: df_sub[(df_sub['YOB_INT'] >= 2008) & (df_sub['YOB_INT'] <= 2011)]
        }
    else:
        categories = {
            'Open': lambda df_sub: df_sub,
            'U23': lambda df_sub: df_sub[(selection_year - df_sub['YOB_INT']) < 23],
            'U18': lambda df_sub: df_sub[(selection_year - df_sub['YOB_INT']) < 18]
        }

    all_rankings = {}
    mps_dict = mps_dict or {}

    for event_name, event_group in df.groupby('EVENT'):
        all_rankings[event_name] = {}
        
        for cat_name, cat_filter_func in categories.items():
            eg = cat_filter_func(event_group).copy()
            if eg.empty:
                all_rankings[event_name][cat_name] = pd.DataFrame()
                continue
                
            cat_mps = mps_dict.get((event_name.upper(), cat_name.upper()), 105.0)
            
            # Compute category-specific race points for each active race column
            cat_race_pts_cols = []
            for rc in active_race_cols:
                pts_col = f'{rc}_PTS'
                cat_race_pts_cols.append(pts_col)
                
                race_pts_map = {}
                # Extract valid times for this category in this race session
                session_res = []
                for idx, row in eg.iterrows():
                    race_orig_idx = race_cols.index(rc) + 1
                    # Drop Race 1 for U23/U18 in 2026 rule set
                    if selection_year == 2026 and cat_name in ['U23', 'U18'] and race_orig_idx == 1:
                        race_pts_map[idx] = 999
                        continue
                        
                    time_val = pd.to_numeric(row.get(rc), errors='coerce')
                    if pd.isna(time_val) or time_val >= 900:
                        race_pts_map[idx] = 999
                    else:
                        session_res.append({'idx': idx, 'time': time_val})
                
                # Sort category athletes by time for this race session
                session_res.sort(key=lambda x: x['time'])
                current_rank = 1
                for i, res in enumerate(session_res):
                    if i > 0 and session_res[i]['time'] == session_res[i-1]['time']:
                        res['pts'] = session_res[i-1]['pts']
                    else:
                        res['pts'] = get_points_for_rank(current_rank)
                    race_pts_map[res['idx']] = res['pts']
                    current_rank += 1
                
                eg[pts_col] = [race_pts_map.get(idx, 999) for idx in eg.index]

            total_points = []
            avg_pps_list = []
            mps_satisfied_counts = []
            
            for _, row in eg.iterrows():
                r_pts = []
                r_pps = []
                satisfied_count = 0
                
                for rc in active_race_cols:
                    race_orig_idx = race_cols.index(rc) + 1
                    if selection_year == 2026 and cat_name in ['U23', 'U18'] and race_orig_idx == 1:
                        continue 
                        
                    r_pts.append(row[f'{rc}_PTS'])
                    pps_val = row[f'{rc}_PPS']
                    r_pps.append(pps_val)
                    
                    if pd.notna(pps_val) and pps_val <= cat_mps:
                        satisfied_count += 1
                
                r_pts_sorted = sorted(r_pts)
                count_limit = 3 if selection_year == 2026 else 4
                
                best_pts = r_pts_sorted[:count_limit] if len(r_pts_sorted) >= count_limit else r_pts_sorted
                
                tot_p = int(round(sum(best_pts))) if any(p < 900 for p in best_pts) else 999
                total_points.append(tot_p)
                
                valid_pps = [p for p in r_pps if pd.notna(p)]
                valid_pps.sort()
                best_pps = valid_pps[:count_limit] if len(valid_pps) >= count_limit else valid_pps
                avg_pps = sum(best_pps) / len(best_pps) if best_pps else np.nan
                avg_pps_list.append(round(avg_pps, 2) if pd.notna(avg_pps) else np.nan)
                mps_satisfied_counts.append(satisfied_count)
                
            eg['TOTAL_POINTS'] = total_points
            eg['AVG_BEST4_PPS'] = avg_pps_list
            eg['MPS_SATISFIED_COUNT'] = mps_satisfied_counts
            
            eg = eg.sort_values(by=['TOTAL_POINTS', 'AVG_BEST4_PPS'], ascending=[True, True]).reset_index(drop=True)
            eg['RANK'] = range(1, len(eg) + 1)
            all_rankings[event_name][cat_name] = eg

    return all_rankings
