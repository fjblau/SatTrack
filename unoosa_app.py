import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="UNOOSA Registry", layout="wide")

st.title("UNOOSA Space Object Registry")

csv_path = os.path.join(os.path.dirname(__file__), "unoosa_registry.csv")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

df = pd.read_csv(csv_path)
df_original = df.copy()

st.sidebar.header("Filters")

search_term = st.sidebar.text_input("Search by Registration Number or Object Name", "")

if search_term:
    df = df[
        df["Registration Number"].str.contains(search_term, case=False, na=False)
        | df["Object Name"].str.contains(search_term, case=False, na=False)
    ]

country_filter = st.sidebar.multiselect(
    "Filter by Country of Origin",
    options=sorted([x for x in df_original["Country of Origin"].unique() if pd.notna(x)]),
    default=None
)
if country_filter:
    df = df[df["Country of Origin"].isin(country_filter)]

function_filter = st.sidebar.multiselect(
    "Filter by Function",
    options=sorted([x for x in df_original["Function"].unique() if pd.notna(x)]),
    default=None
)
if function_filter:
    df = df[df["Function"].isin(function_filter)]

df_with_apogee = df_original[df_original["Apogee (km)"].notna()]
if len(df_with_apogee) > 0:
    apogee_min = int(df_with_apogee["Apogee (km)"].min())
    apogee_max = int(df_with_apogee["Apogee (km)"].max())
    if apogee_min < apogee_max:
        apogee_range = st.sidebar.slider(
            "Apogee Range (km)",
            apogee_min,
            apogee_max,
            (apogee_min, apogee_max)
        )
        df = df[(df["Apogee (km)"].isna()) | ((df["Apogee (km)"] >= apogee_range[0]) & (df["Apogee (km)"] <= apogee_range[1]))]

df_with_perigee = df_original[df_original["Perigee (km)"].notna()]
if len(df_with_perigee) > 0:
    perigee_min = int(df_with_perigee["Perigee (km)"].min())
    perigee_max = int(df_with_perigee["Perigee (km)"].max())
    if perigee_min < perigee_max:
        perigee_range = st.sidebar.slider(
            "Perigee Range (km)",
            perigee_min,
            perigee_max,
            (perigee_min, perigee_max)
        )
        df = df[(df["Perigee (km)"].isna()) | ((df["Perigee (km)"] >= perigee_range[0]) & (df["Perigee (km)"] <= perigee_range[1]))]

df_with_inclination = df_original[df_original["Inclination (degrees)"].notna()]
if len(df_with_inclination) > 0:
    inclination_min = float(df_with_inclination["Inclination (degrees)"].min())
    inclination_max = float(df_with_inclination["Inclination (degrees)"].max())
    if inclination_min < inclination_max:
        inclination_range = st.sidebar.slider(
            "Inclination Range (degrees)",
            inclination_min,
            inclination_max,
            (inclination_min, inclination_max)
        )
        df = df[
            (df["Inclination (degrees)"].isna()) | 
            ((df["Inclination (degrees)"] >= inclination_range[0]) & (df["Inclination (degrees)"] <= inclination_range[1]))
        ]

st.subheader(f"Results: {len(df)} objects")

display_cols = ['Registration Number', 'Object Name', 'Country of Origin', 'Date of Launch', 
                'Function', 'Status', 'Apogee (km)', 'Perigee (km)', 'Inclination (degrees)', 'Period (minutes)']
available_cols = [col for col in display_cols if col in df.columns]

col_table, col_select = st.columns([4, 1])

with col_table:
    st.dataframe(df[available_cols], use_container_width=True, height=400)

st.markdown("---")
st.subheader("Detailed Information")

obj_data = None

if len(df) > 0:
    df_for_selector = df[['Registration Number', 'Object Name']].copy()
    df_for_selector['display'] = df_for_selector['Object Name'].fillna('') + ' (' + df_for_selector['Registration Number'] + ')'
    
    selected_display = st.selectbox(
        "Click a row above, or select from this dropdown:",
        options=df_for_selector['display'].values,
        key="detail_select"
    )
    
    selected_idx = list(df_for_selector['display'].values).index(selected_display)
    selected_reg_num = df_for_selector.iloc[selected_idx]['Registration Number']
    
    matching_rows = df[df['Registration Number'] == selected_reg_num]
    if len(matching_rows) > 0:
        obj_data = matching_rows.iloc[0]

if obj_data is not None:
    
    col1, col2, col3 = st.columns(3)
    
    def get_val(val):
        return 'N/A' if pd.isna(val) else str(val)
    
    with col1:
        st.write(f"**Registration Number:** {get_val(obj_data['Registration Number'])}")
        st.write(f"**International Designator:** {get_val(obj_data['International Designator'])}")
        st.write(f"**Country of Origin:** {get_val(obj_data['Country of Origin'])}")
        st.write(f"**Date of Launch:** {get_val(obj_data['Date of Launch'])}")
        st.write(f"**Status:** {get_val(obj_data['Status'])}")
    
    with col2:
        st.write(f"**Function:** {get_val(obj_data['Function'])}")
        st.write(f"**UN Registered:** {get_val(obj_data['UN Registered'])}")
        st.write(f"**GSO Location:** {get_val(obj_data['GSO Location'])}")
        st.write(f"**Date of Decay/Change:** {get_val(obj_data['Date of Decay or Change'])}")
    
    with col3:
        st.write("**Orbital Parameters:**")
        apogee = obj_data['Apogee (km)']
        perigee = obj_data['Perigee (km)']
        inclination = obj_data['Inclination (degrees)']
        period = obj_data['Period (minutes)']
        
        st.write(f"Apogee: {f'{float(apogee):.2f}' if pd.notna(apogee) else 'N/A'} km")
        st.write(f"Perigee: {f'{float(perigee):.2f}' if pd.notna(perigee) else 'N/A'} km")
        st.write(f"Inclination: {f'{float(inclination):.2f}' if pd.notna(inclination) else 'N/A'}°")
        st.write(f"Period: {f'{float(period):.2f}' if pd.notna(period) else 'N/A'} min")
    
    if pd.notna(obj_data['Registration Document']) and obj_data['Registration Document']:
        reg_doc = obj_data['Registration Document']
        st.write(f"**Registration Document URL:**")
        st.write(f"https://www.unoosa.org{reg_doc}")
    
    if pd.notna(obj_data['Secretariat Remarks']) and obj_data['Secretariat Remarks']:
        st.write(f"**Secretariat Remarks:**")
        st.write(obj_data['Secretariat Remarks'])
else:
    st.info("Click on a row in the table above to view detailed information")

st.sidebar.markdown("---")
st.sidebar.subheader("Import Data")

uploaded_file = st.sidebar.file_uploader("Upload CSV file to add more records", type="csv")
if uploaded_file is not None:
    if uploaded_file.size > 50 * 1024 * 1024:
        st.sidebar.error("File too large (max 50MB)")
    else:
        try:
            new_data = pd.read_csv(uploaded_file, on_bad_lines='skip')
            full_df = pd.read_csv(csv_path)
            
            keep_cols = ['Registration Number', 'Object Name', 'Launch Vehicle', 'Place of Launch',
                        'Date of Launch', 'Apogee (km)', 'Perigee (km)', 'Inclination (degrees)',
                        'Period (minutes)', 'Function', 'Country of Origin']
            
            new_data_clean = new_data[[col for col in keep_cols if col in new_data.columns]].copy()
            for col in keep_cols:
                if col not in new_data_clean.columns:
                    new_data_clean[col] = ''
            
            new_data_clean = new_data_clean[keep_cols]
            
            combined_df = pd.concat([full_df, new_data_clean], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['Registration Number'], keep='first')
            combined_df.to_csv(csv_path, index=False)
            st.sidebar.success(f"Added {len(new_data_clean)} new records!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Import error: {str(e)[:150]}")

st.sidebar.markdown("---")
original_df = pd.read_csv(csv_path)
st.sidebar.info(f"Total objects in registry: {len(original_df)}")
