import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

# --- 1. CONNECTION SETUP ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection failed! The real error is: {e}")
    st.stop()

# DON'T FORGET TO PASTE YOUR GOOGLE SHEET URL HERE!
url = "PASTE_YOUR_GOOGLE_SHEET_URL_HERE"

st.title("🇦🇺 Australia Trip Hub 2026")

# --- THE SMART MAP TRANSLATOR ---
@st.cache_data(show_spinner=False)
def get_coordinates(location_name):
    try:
        geolocator = Nominatim(user_agent="aus_trip_2026")
        # Ask it to find the location in Australia
        location = geolocator.geocode(f"{location_name}, Australia")
        if location:
            return [location.latitude, location.longitude]
        return None
    except:
        return None

# --- 2. CREATE THE TABS ---
tab1, tab2, tab3 = st.tabs(["🗓️ Planner & Map", "🎯 Missions", "💰 Expenses"])

# --- TAB 1: PLANNER & MAP ---
with tab1:
    st.subheader("Trip Itinerary")
    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner")
        
        # Clean the data
        df_plan = df_plan.dropna(how="all")
        df_plan = df_plan.fillna("") 
        
        edited_plan = st.data_editor(df_plan, num_rows="dynamic", width="stretch", key="plan_editor")
        
        if st.button("Save Plan"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan Saved!")

        st.divider()
        st.subheader("📍 Location Map")
        
        # Center map on Sydney by default
        m = folium.Map(location=[-33.8688, 151.2093], zoom_start=11)
        
        # Look at the 'Location' and 'Activity' columns in your planner
        if 'Location' in edited_plan.columns and 'Activity' in edited_plan.columns:
            for index, row in edited_plan.iterrows():
                loc_name = str(row['Location']).strip()
                act_name = str(row['Activity']).strip()
                
                # If the location isn't blank, translate it to a pin!
                if loc_name != "" and loc_name != "nan":
                    coords = get_coordinates(loc_name)
                    
                    if coords:
                        folium.Marker(
                            coords, 
                            popup=f"<b>{act_name}</b><br>{loc_name}", 
                            tooltip=act_name,
                            icon=folium.Icon(color="red", icon="info-sign")
                        ).add_to(m)

        st_folium(m, width="stretch", height=400)
        
    except Exception as e:
        st.error(f"Robot can't read the 'Planner' tab. The real error is: {e}")

# --- TAB 2: MISSIONS ---
with tab2:
    st.subheader("Trip Missions (To-Do)")
    try:
        df_miss = conn.read(spreadsheet=url, worksheet="Missions")
        
        # Clean the data
        df_miss = df_miss.dropna(how="all")
        df_miss = df_miss.fillna("")
        
        edited_miss = st.data_editor(df_miss, num_rows="dynamic", width="stretch", key="miss_editor")
        
        if st.button("Save Missions"):
            conn.update(spreadsheet=url, data=edited_miss, worksheet="Missions")
            st.success("Missions Updated!")
    except Exception as e:
        st.error(f"Robot can't read the 'Missions' tab. The real error is: {e}")

# --- TAB 3: EXPENSES ---
with tab3:
    st.subheader("Shared Expenses")
    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses")
        
        # Clean the data
        df_exp = df_exp.dropna(how="all")
        
        # Separate numbers from text
        if 'Cost' in df_exp.columns:
            df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce')
            
        for col in df_exp.columns:
            if col != 'Cost':
                df_exp[col] = df_exp[col].fillna("").astype(str)
        
        edited_exp = st.data_editor(
            df_exp, 
            num_rows="dynamic", 
            width="stretch", 
            key="exp_editor",
            column_config={
                "Cost": st.column_config.NumberColumn("Cost", format="$%.2f", min_value=0.0)
            }
        )
        
        if st.button("Save Expenses"):
            conn.update(spreadsheet=url, data=edited_exp, worksheet="Expenses")
            st.success("Expenses Saved!")
            
        # Quick Math
        if not df_exp.empty and 'Cost' in edited_exp.columns:
            total = edited_exp['Cost'].sum()
            st.metric("Total Trip Spend", f"${total:.2f} AUD")
            st.write(f"Each person owes: **${total/3:.2f}**")
            
    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. The real error is: {e}")
# --- 2. CREATE THE TABS ---
tab1, tab2, tab3 = st.tabs(["🗓️ Planner & Map", "🎯 Missions", "💰 Expenses"])

# --- TAB 1: PLANNER & MAP ---
with tab1:
    st.subheader("Trip Itinerary")
    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner")
        
        # 🧹 THE CLEANING STATION: Remove completely empty rows and turn NaNs into blank text
        df_plan = df_plan.dropna(how="all")
        df_plan = df_plan.fillna("") 
        
        # Now the editor knows it can accept text!
        edited_plan = st.data_editor(df_plan, num_rows="dynamic", width="stretch", key="plan_editor")
        
        if st.button("Save Plan"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan Saved!")

        st.divider()
        st.subheader("📍 Location Map")
        
        # Center map on Sydney by default
        m = folium.Map(location=[-33.8688, 151.2093], zoom_start=11)
        
        # Look at the 'Location' and 'Activity' columns in your planner
        if 'Location' in edited_plan.columns and 'Activity' in edited_plan.columns:
            # Loop through every row you typed
            for index, row in edited_plan.iterrows():
                loc_name = str(row['Location']).strip()
                act_name = str(row['Activity']).strip()
                
                # If the location isn't blank, translate it to a pin!
                if loc_name != "" and loc_name != "nan":
                    coords = get_coordinates(loc_name)
                    
                    if coords:
                        # Drop a pin with the Activity name as the popup
                        folium.Marker(
                            coords, 
                            popup=f"<b>{act_name}</b><br>{loc_name}", 
                            tooltip=act_name,
                            icon=folium.Icon(color="red", icon="info-sign")
                        ).add_to(m)

        st_folium(m, width="stretch", height=400)

# --- TAB 2: MISSIONS ---
with tab2:
    st.subheader("Trip Missions (To-Do)")
    try:
        df_miss = conn.read(spreadsheet=url, worksheet="Missions")
        edited_miss = st.data_editor(df_miss, num_rows="dynamic", width="stretch", key="miss_editor")
        
        if st.button("Save Missions"):
            conn.update(spreadsheet=url, data=edited_miss, worksheet="Missions")
            st.success("Missions Updated!")
    except Exception as e:
        st.error(f"Robot can't read the 'Missions' tab. The real error is: {e}")

# --- TAB 3: EXPENSES ---
with tab3:
    st.subheader("Shared Expenses")
    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses")
        
        # 1. CLEANING: Remove completely empty rows
        df_exp = df_exp.dropna(how="all")
        
        # 2. SEPARATE THE NUMBERS FROM THE TEXT
        if 'Cost' in df_exp.columns:
            # Force the 'Cost' column to be a strict math number
            df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce')
            
        # Force all OTHER columns to be clean text
        for col in df_exp.columns:
            if col != 'Cost':
                df_exp[col] = df_exp[col].fillna("").astype(str)
        
        # 3. THE MAGIC EDITOR (Now with strict column rules!)
        edited_exp = st.data_editor(
            df_exp, 
            num_rows="dynamic", 
            width="stretch", 
            key="exp_editor",
            column_config={
                # This tells Streamlit: "Treat this as a number and show a dollar sign!"
                "Cost": st.column_config.NumberColumn("Cost", format="$%.2f", min_value=0.0)
            }
        )
        
        if st.button("Save Expenses"):
            conn.update(spreadsheet=url, data=edited_exp, worksheet="Expenses")
            st.success("Expenses Saved!")
            
        # Quick Math: Calculate from the newly edited data
        if not df_exp.empty and 'Cost' in edited_exp.columns:
            total = edited_exp['Cost'].sum()
            st.metric("Total Trip Spend", f"${total:.2f} AUD")
            st.write(f"Each person owes: **${total/3:.2f}**")
            
    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. The real error is: {e}")
