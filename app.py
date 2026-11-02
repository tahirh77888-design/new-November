import io
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Pepsi Sales Penetration Dashboard",
    page_icon="🥤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Styling
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: 700; color: #0C2340; margin-bottom: 5px; }
    .sub-header { font-size: 13px; color: #555; margin-bottom: 15px; }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border-left: 5px solid #004B93;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .metric-val { font-size: 22px; font-weight: 700; color: #004B93; }
    .metric-lbl { font-size: 12px; color: #666; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🥤 PepsiCo Sales Penetration Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Route, PSR, Pack & SKU Performance Analytics</div>', unsafe_allow_html=True)

# Default Fallback Targets
DEFAULT_TARGETS = {
    '1000 ML PET-7-UP': 0.60,
    '1000 ML PET-M.DEW': 0.50,
    '1000 ML PET-PEPSI': 0.60,
    '1500 ML PET-7-UP': 0.60,
    '1500 ML PET-M.DEW': 0.50,
    '1500 ML PET-PEPSI': 0.60,
    '2000 ML PET 6BT-M.DEW': 0.40,
    '2000 ML PET 6BT-7-UP': 0.50,
    '2000 ML PET 6BT-PEPSI': 0.50,
    '250 ML RB-M.DEW': 0.50,
    '250 ML RB-7-UP': 0.70,
    '250 ML RB-PEPSI': 0.70,
    '500 ML PET Sting-STING - BB': 0.35,
    '500 ML PET AF-Aquafina': 0.35,
    '1500 ML PET AF-Aquafina': 0.35,
    '500 ML PET (CSD Combined)': 0.35,
    '300 ML PET Revive (Combined)': 0.40
}

# Accurate Product Mapping
def map_product_group(pname):
    p = str(pname).strip()
    if '300 ML' in p and 'Revive' in p:
        return '300 ML PET Revive (Combined)'
    if '500 ML PET' in p and not ('1500' in p or '2500' in p) and not any(k in p for k in ['Sting', 'Aquafina', 'AF']):
        return '500 ML PET (CSD Combined)'
    return p

ESSENTIAL_COLS = [
    'Dist_Name', 'SDM/SDO/SDS', 'BOOKER_Name', 'PJP_Name', 
    'Outlet_Code', 'Outlet_Name', 'HANDLER', 'INVOICE_NUMBER', 
    'Product NAME', 'PKG_NAME', 'Sales_Raw Cases'
]

# 1. Independent Fast Target Loader
def load_target_data(target_bytes):
    targets_dict = DEFAULT_TARGETS.copy()
    if target_bytes is not None:
        try:
            df_t = pd.read_excel(io.BytesIO(target_bytes))
            p_col = [c for c in df_t.columns if any(k in str(c).lower() for k in ['product', 'sku', 'name'])][0]
            t_col = [c for c in df_t.columns if 'target' in str(c).lower()][0]
            for _, row in df_t.iterrows():
                val = row[t_col]
                prod_name = str(row[p_col]).strip()
                if pd.notna(val):
                    val = float(val) if float(val) <= 1.0 else float(val) / 100.0
                    if prod_name == '500 ML PET':
                        targets_dict['500 ML PET (CSD Combined)'] = val
                    elif 'Revive' in prod_name:
                        targets_dict['300 ML PET Revive (Combined)'] = 0.40
                    else:
                        targets_dict[prod_name] = val
        except Exception as e:
            st.sidebar.error(f"Target file error: {e}")
    targets_dict['300 ML PET Revive (Combined)'] = 0.40
    return targets_dict

# 2. Independent Sales Loader
@st.cache_data(show_spinner="Sales Raw Data process ho raha hai...")
def load_sales_data(sales_bytes):
    df_head = pd.read_excel(io.BytesIO(sales_bytes), header=None, nrows=10)
    header_idx = 3
    for i, row in df_head.iterrows():
        row_str = " ".join([str(v) for v in row.values if pd.notna(v)])
        if "Outlet_Code" in row_str and "Sales_Raw Cases" in row_str:
            header_idx = i
            break

    df = pd.read_excel(io.BytesIO(sales_bytes), skiprows=header_idx)
    df.columns = [str(c).strip() for c in df.columns]

    cols_to_use = [c for c in ESSENTIAL_COLS if c in df.columns]
    df = df[cols_to_use].copy()

    if 'Sales_Raw Cases' in df.columns:
        df['Sales_Raw Cases'] = pd.to_numeric(df['Sales_Raw Cases'], errors='coerce').fillna(0)
    else:
        df['Sales_Raw Cases'] = 0.0

    df['Target_Product_Group'] = df['Product NAME'].apply(map_product_group)
    
    for cat_col in ['Dist_Name', 'SDM/SDO/SDS', 'BOOKER_Name', 'PJP_Name', 'Target_Product_Group', 'PKG_NAME']:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].astype('category')

    return df

# Sidebar
st.sidebar.header("📁 Data Source Files")
uploaded_sales = st.sidebar.file_uploader("1. Sales Raw Data (.xlsx)", type=["xlsx"])
uploaded_target = st.sidebar.file_uploader("2. Targets File (.xlsx)", type=["xlsx"])

if uploaded_sales is not None:
    sales_bytes = uploaded_sales.getvalue()
    target_bytes = uploaded_target.getvalue() if uploaded_target is not None else None
    
    df_sales = load_sales_data(sales_bytes)
    target_mapping = load_target_data(target_bytes)

    if uploaded_target is not None:
        st.sidebar.success(f"✅ Target file loaded ({len(target_mapping)} SKUs)")
    else:
        st.sidebar.info("ℹ️ Default targets active")

    # Hierarchy Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Hierarchy Filters")

    dist_list = ["All"] + sorted([str(x) for x in df_sales['Dist_Name'].dropna().unique()])
    sel_dist = st.sidebar.selectbox("Distributor", dist_list)

    f_df = df_sales if sel_dist == "All" else df_sales[df_sales['Dist_Name'] == sel_dist]

    sdm_list = ["All"] + sorted([str(x) for x in f_df['SDM/SDO/SDS'].dropna().unique()])
    sel_sdm = st.sidebar.selectbox("SDM / SDS", sdm_list)
    if sel_sdm != "All":
        f_df = f_df[f_df['SDM/SDO/SDS'] == sel_sdm]

    booker_list = ["All"] + sorted([str(x) for x in f_df['BOOKER_Name'].dropna().unique()])
    sel_booker = st.sidebar.selectbox("Booker (PSR)", booker_list)
    if sel_booker != "All":
        f_df = f_df[f_df['BOOKER_Name'] == sel_booker]

    pjp_list = ["All"] + sorted([str(x) for x in f_df['PJP_Name'].dropna().unique()])
    sel_pjp = st.sidebar.selectbox("Route (PJP)", pjp_list)
    if sel_pjp != "All":
        f_df = f_df[f_df['PJP_Name'] == sel_pjp]

    # Overall Summary Metrics
    total_outlets = f_df['Outlet_Code'].nunique()
    total_invoices = f_df['INVOICE_NUMBER'].nunique() if 'INVOICE_NUMBER' in f_df.columns else 0
    
    # Calculate Overall SKU Per Bill
    if total_invoices > 0 and 'INVOICE_NUMBER' in f_df.columns:
        avg_sku_per_bill = f_df.groupby('INVOICE_NUMBER')['Product NAME'].nunique().mean()
    else:
        avg_sku_per_bill = 0.0

    # Pre-aggregate SKU metrics for Target Calculations
    sku_agg = f_df.groupby('Target_Product_Group', observed=True).agg(
        Active_Outlets=('Outlet_Code', 'nunique'),
        Total_Cases=('Sales_Raw Cases', 'sum')
    ).to_dict(orient='index')

    # Calculate Total Targets Achieved (Hit Count)
    hit_count = 0
    close_count = 0
    far_count = 0
    sku_records = []

    for prod_group, target_pct in target_mapping.items():
        data = sku_agg.get(prod_group, {'Active_Outlets': 0, 'Total_Cases': 0.0})
        buying_outlets = data['Active_Outlets']
        cases_sold = data['Total_Cases']

        actual_pen = (buying_outlets / total_outlets) if total_outlets > 0 else 0.0
        gap_pct = actual_pen - target_pct
        
        if gap_pct >= 0:
            status = "Hit 🎯 😊"
            hit_count += 1
        elif gap_pct >= -0.05:
            status = "Close ⚠️ 😕"
            close_count += 1
        else:
            status = "Far 😡"
            far_count += 1

        sku_records.append({
            "SKU / Group Name": prod_group,
            "Target %": f"{target_pct*100:.0f}%",
            "Actual Outlets": buying_outlets,
            "Actual Pen %": f"{actual_pen*100:.1f}%",
            "Gap %": f"{gap_pct*100:+.1f}%",
            "Total Cases": round(cases_sold, 1),
            "Status": status
        })

    df_sku_rep = pd.DataFrame(sku_records)

    # Top KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="metric-val">{total_outlets:,}</div><div class="metric-lbl">Buying Outlets</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-val">{avg_sku_per_bill:.2f}</div><div class="metric-lbl">Avg SKU Per Bill</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-val">{hit_count} / {len(target_mapping)}</div><div class="metric-lbl">Target Achieved SKUs 🎯</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-val">{(hit_count / len(target_mapping) * 100):.1f}%</div><div class="metric-lbl">SKU Hit Rate %</div></div>', unsafe_allow_html=True)

    st.write("")

    # Navigation Tabs
    tab1, tab_pack, tab2, tab3, tab4 = st.tabs([
        "🎯 SKU Target & Penetration", 
        "📦 Pack-Wise Penetration",
        "👤 Booker (PSR) Scorecard", 
        "🛣️ Route Analysis",
        "⚠️ Non-Buying Outlets"
    ])

    with tab1:
        st.subheader("Target vs Actual SKU Penetration")
        st.caption(f"Summary: **{hit_count} Hit 🎯** | **{close_count} Close ⚠️** | **{far_count} Far 😡** (Total {len(target_mapping)} SKUs)")

        def color_status_rows(row):
            st_val = str(row['Status'])
            if "Hit" in st_val:
                return ['background-color: #d4edda; color: #155724; font-weight: 500;'] * len(row)
            elif "Close" in st_val:
                return ['background-color: #fff3cd; color: #856404; font-weight: 500;'] * len(row)
            else:
                return ['background-color: #f8d7da; color: #721c24; font-weight: 500;'] * len(row)

        styled_sku_df = df_sku_rep.style.apply(color_status_rows, axis=1)
        st.dataframe(styled_sku_df, use_container_width=True, height=520)

    with tab_pack:
        st.subheader("📦 Overall Pack-Wise Penetration (All Flavours Combined)")
        if 'PKG_NAME' in f_df.columns:
            pack_agg = f_df.groupby('PKG_NAME', observed=True).agg(
                Billed_Outlets=('Outlet_Code', 'nunique'),
                Total_Cases=('Sales_Raw Cases', 'sum'),
                Invoices=('INVOICE_NUMBER', 'nunique')
            ).reset_index()

            pack_agg['Penetration %'] = ((pack_agg['Billed_Outlets'] / total_outlets) * 100).round(1).astype(str) + "%"
            pack_agg['Drop Size (Cases)'] = (pack_agg['Total_Cases'] / pack_agg['Billed_Outlets']).round(2)
            pack_agg = pack_agg.sort_values(by='Billed_Outlets', ascending=False)

            st.dataframe(pack_agg, use_container_width=True, height=500)
        else:
            st.info("Sales file me 'PKG_NAME' column dastiyab nahi hai.")

    # TAB 3: BOOKER SCORECARD (SKU PER BILL & TARGET ACHIEVEMENT ONLY)
    with tab2:
        st.subheader("👤 Booker / Pre-Seller Scorecard")
        st.caption("Performance based on Productivity (SKU/Bill) & SKU Target Hit Rate.")

        booker_rows = []
        for b_name, b_df in f_df.groupby('BOOKER_Name', observed=True):
            b_outlets = b_df['Outlet_Code'].nunique()
            if b_outlets == 0:
                continue
            
            # SKU per Bill for this Booker
            b_sku_per_bill = b_df.groupby('INVOICE_NUMBER')['Product NAME'].nunique().mean()
            
            # Target Hit Count for this Booker
            b_achieved = 0
            b_sku_grp = b_df.groupby('Target_Product_Group', observed=True)['Outlet_Code'].nunique()
            for sku_name, tgt in target_mapping.items():
                if (b_sku_grp.get(sku_name, 0) / b_outlets) >= tgt:
                    b_achieved += 1

            dist = b_df['Dist_Name'].iloc[0] if 'Dist_Name' in b_df.columns else ""
            sdm = b_df['SDM/SDO/SDS'].iloc[0] if 'SDM/SDO/SDS' in b_df.columns else ""

            booker_rows.append({
                'Distributor': dist,
                'SDM': sdm,
                'Booker Name': b_name,
                'Billed Outlets': b_outlets,
                'SKU Per Bill': round(b_sku_per_bill, 2),
                'Targets Achieved': f"{b_achieved} / {len(target_mapping)}",
                'Hit Rate %': round((b_achieved / len(target_mapping)) * 100, 1),
                'Status': "Star ⭐" if b_achieved >= 10 else ("Good 👍" if b_achieved >= 6 else "Needs Focus ⚠️")
            })

        df_booker_score = pd.DataFrame(booker_rows).sort_values(by='Hit Rate %', ascending=False)
        
        def color_booker(row):
            hr = row['Hit Rate %']
            if hr >= 50.0:
                return ['background-color: #d4edda; color: #155724; font-weight: 500;'] * len(row)
            elif hr >= 30.0:
                return ['background-color: #fff3cd; color: #856404; font-weight: 500;'] * len(row)
            else:
                return ['background-color: #f8d7da; color: #721c24; font-weight: 500;'] * len(row)

        st.dataframe(df_booker_score.style.apply(color_booker, axis=1), use_container_width=True, height=500)

    with tab3:
        st.subheader("Route (PJP) Wise Penetration Breakdown")
        pjp_grp = f_df.groupby(['PJP_Name', 'BOOKER_Name'], observed=True).agg(
            Active_Outlets=('Outlet_Code', 'nunique'),
            Total_Volume=('Sales_Raw Cases', 'sum')
        ).reset_index()
        st.dataframe(pjp_grp.sort_values(by='Active_Outlets', ascending=False), use_container_width=True)

    with tab4:
        st.subheader("Identify Non-Buying Outlets by SKU")
        selected_sku = st.selectbox("Select Target SKU:", list(target_mapping.keys()))
        
        buyers = set(f_df[f_df['Target_Product_Group'] == selected_sku]['Outlet_Code'].unique())
        all_meta = f_df[['Outlet_Code', 'Outlet_Name', 'PJP_Name', 'BOOKER_Name']].drop_duplicates('Outlet_Code')
        non_buyers = all_meta[~all_meta['Outlet_Code'].isin(buyers)]

        st.warning(f"**{len(non_buyers)}** outlets did NOT purchase **{selected_sku}**")
        st.dataframe(non_buyers, use_container_width=True)

    # Excel Export
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_sku_rep.to_excel(writer, sheet_name='SKU Penetration', index=False)
        if 'PKG_NAME' in f_df.columns:
            pack_agg.to_excel(writer, sheet_name='Pack Penetration', index=False)
        df_booker_score.to_excel(writer, sheet_name='Booker Scorecard', index=False)
        pjp_grp.to_excel(writer, sheet_name='Route Analysis', index=False)

    st.download_button(
        label="📥 Download Full Report (Excel)",
        data=output.getvalue(),
        file_name="Pepsi_Penetration_Fast_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👈 Baraye meharbani sidebar se Sales Raw Data aur Target File upload karein.")