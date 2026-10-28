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
    disciplines = ['MK1', 'WK1', 'MC1', 'WC1']
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

def process_selection_rankings(df_raw, race_cols, selection_year=2026):
    """
    Processes selection rankings supporting year-specific rules:
    - 2026: Excludes athletes born in 2012 or later (U14/cadets). Race 6 removed.
      Open counts Best 3 of 5; U23/U18 counts Best 3 of 4 (drops Race 1).
    - 2027: All categories count Best 4 of 6.
    """
    df = normalize_columns(df_raw.copy())
    df['YOB_INT'] = df['YOB'].apply(extract_year)
    
    # Exclude cadets / U14 (born 2012 or later) for 2026 selection rankings
    if selection_year == 2026:
        df = df[df['YOB_INT'] < 2012].copy()
    
    # Filter out Race 6 entirely for 2026
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

    base_scores = {}
    for rc in active_race_cols:
        session_df = df[['EVENT', rc']].rename(columns={rc: 'TIME'})
        base_scores[rc] = calculate_four_boat_base(session_df)

    def get_points_for_rank(rank):
        if rank == 1: return 0
        elif rank == 2: return 2
        elif rank >= 3: return rank
        return 999

    for rc in active_race_cols:
        b_score = base_scores.get(rc, np.nan)
        pps_list = []
        for _, row in df.iterrows():
            time_val = pd.to_numeric(row.get(rc), errors='coerce')
            if pd.isna(time_val) or time_val >= 900:
                pps_list.append(np.nan)
            else:
                pps = (time_val / b_score) * 100 if pd.notna(b_score) and b_score > 0 else np.nan
                pps_list.append(pps)
        df[f'{rc}_PPS'] = pps_list

    for event_name, event_group in df.groupby('EVENT'):
        for rc in active_race_cols:
            race_results = []
            for idx, row in event_group.iterrows():
                time_val = pd.to_numeric(row.get(rc), errors='coerce')
                if pd.isna(time_val) or time_val >= 900:
                    race_results.append({'idx': idx, 'time': 999, 'pts': 999})
                else:
                    race_results.append({'idx': idx, 'time': time_val, 'pts': np.nan})
                    
            valid_res = [r for r in race_results if r['pts'] != 999]
            valid_res.sort(key=lambda x: x['time'])
            
            current_rank = 1
            for i, res in enumerate(valid_res):
                if i > 0 and valid_res[i]['time'] == valid_res[i-1]['time']:
                    res['pts'] = valid_res[i-1]['pts']
                else:
                    res['pts'] = get_points_for_rank(current_rank)
                current_rank += 1
                
            pts_map = {r['idx']: r['pts'] for r in valid_res}
            df.loc[event_group.index, f'{rc}_PTS'] = [pts_map.get(idx, 999) for idx in event_group.index]

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

    for event_name, event_group in df.groupby('EVENT'):
        all_rankings[event_name] = {}
        
        for cat_name, cat_filter_func in categories.items():
            eg = cat_filter_func(event_group).copy()
            if eg.empty:
                all_rankings[event_name][cat_name] = pd.DataFrame()
                continue
                
            total_points = []
            avg_pps_list = []
            
            for _, row in eg.iterrows():
                r_pts = []
                r_pps = []
                
                for rc in active_race_cols:
                    race_orig_idx = race_cols.index(rc) + 1
                    if selection_year == 2026 and cat_name in ['U23', 'U18'] and race_orig_idx == 1:
                        continue 
                        
                    r_pts.append(row[f'{rc}_PTS'])
                    r_pps.append(row[f'{rc}_PPS'])
                
                r_pts_sorted = sorted(r_pts)
                count_limit = 3 if selection_year == 2026 else 4
                
                best_pts = r_pts_sorted[:count_limit] if len(r_pts_sorted) >= count_limit else r_pts_sorted
                
                tot_p = sum(best_pts) if any(p < 900 for p in best_pts) else 999
                total_points.append(tot_p)
                
                valid_pps = [p for p in r_pps if pd.notna(p)]
                valid_pps.sort()
                best_pps = valid_pps[:count_limit] if len(valid_pps) >= count_limit else valid_pps
                avg_pps = sum(best_pps) / len(best_pps) if best_pps else np.nan
                avg_pps_list.append(avg_pps)
                
            eg['TOTAL_POINTS'] = total_points
            eg['AVG_BEST4_PPS'] = avg_pps_list
            
            eg = eg.sort_values(by=['TOTAL_POINTS', 'AVG_BEST4_PPS'], ascending=[True, True]).reset_index(drop=True)
            eg['RANK'] = range(1, len(eg) + 1)
            all_rankings[event_name][cat_name] = eg

    return all_rankings
