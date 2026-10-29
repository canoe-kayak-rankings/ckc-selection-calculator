# Inside your category tab loop in app.py:
df_cat = rankings_dict[evt_name].get(cat_name, pd.DataFrame())

if not df_cat.empty:
    # 1. Display Sidebar Summary of MPS for this season
    with st.sidebar:
        st.subheader(f"📊 {selected_year} MPS Thresholds")
        if mps_dict:
            mps_df_display = pd.DataFrame([
                {"Event": ev, "Category": cat, "Max PPS (%)": f"{val}%"} 
                for (ev, cat), val in mps_dict.items()
            ])
            st.dataframe(mps_df_display, hide_index=True, use_container_width=True)
        else:
            st.info("No 'MPS' sheet found in Excel. Add an MPS sheet to display standards here.")

    # 2. Format and style table with green highlighting for MPS
    display_cols = ['RANK', 'ATHLETE', 'EVENT', 'YOB_INT', 'PROVINCE', 'TOTAL_POINTS', 'MPS_SATISFIED_COUNT', 'AVG_BEST4_PPS'] + [f"{rc}_PPS" for rc in selected_races if f"{rc}_PPS" in df_cat.columns]
    available_disp = [c for c in display_cols if c in df_cat.columns]
    
    # Optional styling function for Streamlit dataframe
    cat_mps_val = mps_dict.get((evt_name.upper(), cat_name.upper()), 105.0)
    
    def highlight_mps(val):
        """Highlights PPS values green if they meet or beat the MPS threshold."""
        try:
            v = float(val)
            if v <= cat_mps_val:
                return 'background-color: #d4edda; color: #155724;' # soft green
        except:
            pass
        return ''

    styled_df = df_cat[available_disp].style.applymap(
        highlight_mps, 
        subset=[c for c in available_disp if '_PPS' in c]
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    st.caption(f"🟢 Highlighted cells indicate selection races satisfying the {cat_name} {evt_name} MPS threshold (≤ {cat_mps_val}%).")
