import pandas as pd
import numpy as np

def calculate_four_boat_base(df_race_day):
    """
    Computes the 4-Boat Base Score for a single race session:
    (Lowest MK1 + Lowest WK1 + Lowest MC1 + Lowest WC1) / 4
    """
    disciplines = ['MK1', 'WK1', 'MC1', 'WC1']
    lowest_times = {}
    
    for disc in disciplines:
        # Filter rows matching discipline
        disc_rows = df_race_day[df_race_day['EVENT'].str.upper() == disc]
        valid_times = pd.to_numeric(disc_rows['TIME'], errors='coerce').dropna()
        lowest_times[disc] = valid_times.min() if not valid_times.empty else np.nan
        
    if all(not np.isnan(v) for v in lowest_times.values()):
        base_score = sum(lowest_times.values()) / 4.0
        return round(base_score, 2)
    return np.nan

def process_selection_rankings(df_raw, race_cols, age_category_filter=None):
    """
    Processes athletes for a specific age category across 6 races:
    - Calculates 4-Boat base score per race session
    - Computes Paddler Percentage Score (PPS)
    - Assigns points based on rank within age category (1st=0, 2nd=2, 3rd=3, ...)
    - Selects Best 4 of 6 races
    - Applies tie-breaking using average best-4 PPS gaps
    """
    df = df_raw.copy()
    
    # Filter by age category if specified and not 'All' / 'Senior'
    if age_category_filter and age_category_filter.lower() not in ['senior', 'all', 'open']:
        df = df[df['CATEGORY'].str.strip().str.upper() == age_category_filter.upper()].copy()
        
    if df.empty:
        return pd.DataFrame()

    # Define standard points table mapping by rank index (0-indexed: rank 1 = 0 pts, rank 2 = 2 pts, etc.)
    def get_points_for_rank(rank):
        if rank == 1:
            return 0
        elif rank == 2:
            return 2
        elif rank >= 3:
            return rank  # 3rd = 3, 4th = 4, etc.
        return 999

    processed_races_data = []
    
    # 1. Calculate Daily 4-Boat Base Score & Assign Points per Race
    race_points_dict = {rc: [] for rc in race_cols}
    race_pps_dict = {rc: [] for rc in race_cols}
    
    # First, calculate 4-boat base score across all athletes for each race
    base_scores = {}
    for rc in race_cols:
        session_df = df[['EVENT', rc]].rename(columns={rc: 'TIME'})
        base_scores[rc] = calculate_four_boat_base(session_df)
        
    for rc in race_cols:
        b_score = base_scores.get(rc, np.nan)
        race_results = []
        
        for idx, row in df.iterrows():
            time_val = pd.to_numeric(row.get(rc), errors='coerce')
            
            # Check for DNF/DNS/Missing
            if pd.isna(time_val) or time_val >= 900:
                race_results.append({'idx': idx, 'time': 999, 'pps': np.nan, 'pts': 999})
            else:
                pps = (time_val / b_score) * 100 if pd.notna(b_score) and b_score > 0 else np.nan
                race_results.append({'idx': idx, 'time': time_val, 'pps': pps, 'pts': np.nan})
                
        # Rank valid athletes within this age category for this race
        valid_res = [r for r in race_results if r['pts'] != 999]
        valid_res.sort(key=lambda x: x['time'])
        
        # Assign ranks and points handling ties
        current_rank = 1
        for i, res in enumerate(valid_res):
            if i > 0 and valid_res[i]['time'] == valid_res[i-1]['time']:
                # Tie gets same rank and points
                res['rank'] = valid_res[i-1]['rank']
                res['pts'] = valid_res[i-1]['pts']
            else:
                res['rank'] = current_rank
                res['pts'] = get_points_for_rank(current_rank)
            current_rank += 1
            
        # Map back to dataframe order
        pts_map = {r['idx']: r['pts'] for r in valid_res}
        pps_map = {r['idx']: r['pps'] for r in valid_res}
        
        col_pts = []
        col_pps = []
        for idx in df.index:
            col_pts.append(pts_map.get(idx, 999))
            col_pps.append(pps_map.get(idx, np.nan))
            
        df[f'{rc}_PTS'] = col_pts
        df[f'{rc}_PPS'] = col_pps

    # 2. Select Best 4 of 6 Races for Points and PPS Average
    total_points = []
    avg_best4_pps = []
    
    for idx, row in df.iterrows():
        r_pts = [row[f'{rc}_PTS'] for rc in race_cols]
        r_pps = [row[f'{rc}_PPS'] for rc in race_cols]
        
        # Sort points ascending (lowest points are best)
        r_pts_sorted = sorted(r_pts)
        best_4_pts = r_pts_sorted[:4] if len(r_pts_sorted) >= 4 else r_pts_sorted
        
        # If all 4 are 999, total is 999
        tot_p = sum(best_4_pts) if any(p < 900 for p in best_4_pts) else 999
        total_points.append(tot_p)
        
        # Average best 4 PPS for tie-breaking
        valid_pps = [p for p in r_pps if pd.notna(p)]
        valid_pps.sort()
        best_4_pps = valid_pps[:4] if len(valid_pps) >= 4 else valid_pps
        avg_pps = sum(best_4_pps) / len(best_4_pps) if best_4_pps else np.nan
        avg_best4_pps.append(avg_pps)
        
    df['TOTAL_POINTS'] = total_points
    df['AVG_BEST4_PPS'] = avg_best4_pps
    
    # 3. Final Ranking & Tie-Breaking (Lower points win; if tie, lower avg PPS wins)
    df = df.sort_values(by=['TOTAL_POINTS', 'AVG_BEST4_PPS'], ascending=[True, True]).reset_index(drop=True)
    df['RANK'] = range(1, len(df) + 1)
    
    return df