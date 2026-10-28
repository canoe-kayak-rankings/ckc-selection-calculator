import pandas as pd
import numpy as np

def normalize_columns(df):
    """
    Standardizes column names regardless of case or common variations.
    """
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
            
    df_renamed = df.rename(columns=col_map)
    
    # Fill in missing default columns if absent
    if 'EVENT' not in df_renamed.columns:
        df_renamed['EVENT'] = ''
    if 'ATHLETE' not in df_renamed.columns:
        if 'First Name' in df_renamed.columns and 'Last Name' in df_renamed.columns:
            df_renamed['ATHLETE'] = df_renamed['First Name'].fillna('') + ' ' + df_renamed['Last Name'].fillna('')
        else:
            df_renamed['ATHLETE'] = 'Unknown'
    if 'CATEGORY' not in df_renamed.columns:
        df_renamed['CATEGORY'] = 'Open'
    if 'PROVINCE' not in df_renamed.columns:
        df_renamed['PROVINCE'] = ''
        
    return df_renamed

def calculate_four_boat_base(df_race_day):
    """
    Computes the 4-Boat Base Score for a single race session:
    (Lowest MK1 + Lowest WK1 + Lowest MC1 + Lowest WC1) / 4
    """
    disciplines = ['MK1', 'WK1', 'MC1', 'WC1']
    lowest_times = {}
    
    # Event mapping standardization
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
        base_score = sum(valid_vals) / 4.0
        return round(base_score, 2)
    return np.nan

def process_selection_rankings(df_raw, race_cols, age_category_filter=None):
    """
    Processes selection rankings with column normalization.
    """
    df = normalize_columns(df_raw)
    
    # Filter by age category if specified
    if age_category_filter and age_category_filter.lower() not in ['senior', 'all', 'open']:
        df = df[df['CATEGORY'].str.strip().str.upper() == age_category_filter.upper()].copy()
        
    if df.empty:
        return pd.DataFrame()

    def get_points_for_rank(rank):
        if rank == 1:
            return 0
        elif rank == 2:
            return 2
        elif rank >= 3:
            return rank
        return 999

    base_scores = {}
    for rc in race_cols:
        session_df = df[['EVENT', rc]].rename(columns={rc: 'TIME'})
        base_scores[rc] = calculate_four_boat_base(session_df)
        
    for rc in race_cols:
        b_score = base_scores.get(rc, np.nan)
        race_results = []
        
        for idx, row in df.iterrows():
            time_val = pd.to_numeric(row.get(rc), errors='coerce')
            
            if pd.isna(time_val) or time_val >= 900:
                race_results.append({'idx': idx, 'time': 999, 'pps': np.nan, 'pts': 999})
            else:
                pps = (time_val / b_score) * 100 if pd.notna(b_score) and b_score > 0 else np.nan
                race_results.append({'idx': idx, 'time': time_val, 'pps': pps, 'pts': np.nan})
                
        valid_res = [r for r in race_results if r['pts'] != 999]
        valid_res.sort(key=lambda x: x['time'])
        
        current_rank = 1
        for i, res in enumerate(valid_res):
            if i > 0 and valid_res[i]['time'] == valid_res[i-1]['time']:
                res['rank'] = valid_res[i-1]['rank']
                res['pts'] = valid_res[i-1]['pts']
            else:
                res['rank'] = current_rank
                res['pts'] = get_points_for_rank(current_rank)
            current_rank += 1
            
        pts_map = {r['idx']: r['pts'] for r in valid_res}
        pps_map = {r['idx']: r['pps'] for r in valid_res}
        
        df[f'{rc}_PTS'] = [pts_map.get(idx, 999) for idx in df.index]
        df[f'{rc}_PPS'] = [pps_map.get(idx, np.nan) for idx in df.index]

    total_points = []
    avg_best4_pps = []
    
    for idx, row in df.iterrows():
        r_pts = [row[f'{rc}_PTS'] for rc in race_cols]
        r_pps = [row[f'{rc}_PPS'] for rc in race_cols]
        
        r_pts_sorted = sorted(r_pts)
        best_4_pts = r_pts_sorted[:4] if len(r_pts_sorted) >= 4 else r_pts_sorted
        
        tot_p = sum(best_4_pts) if any(p < 900 for p in best_4_pts) else 999
        total_points.append(tot_p)
        
        valid_pps = [p for p in r_pps if pd.notna(p)]
        valid_pps.sort()
        best_4_pps = valid_pps[:4] if len(valid_pps) >= 4 else valid_pps
        avg_pps = sum(best_4_pps) / len(best_4_pps) if best_4_pps else np.nan
        avg_best4_pps.append(avg_pps)
        
    df['TOTAL_POINTS'] = total_points
    df['AVG_BEST4_PPS'] = avg_best4_pps
    
    df = df.sort_values(by=['TOTAL_POINTS', 'AVG_BEST4_PPS'], ascending=[True, True]).reset_index(drop=True)
    df['RANK'] = range(1, len(df) + 1)
    
    return df
