import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

st.title("🇦🇺 Our Shared Travel Hub")

# --- 1. CONNECTION SETUP ---
try:
    secret_info = st.secrets["connections"]["gsheets"]
    conn = st.connection("gsheets", type=GSheetsConnection, **secret_info)
except Exception as e:
    st.error("Secrets not found!")
    st.stop()

url = "PASTE_YOUR_GOOGLE_SHEET_URL_HERE"

# --- 2. DATA LOAD & EDITOR ---
try:
    df = conn.read(spreadsheet=url, worksheet="Planner")
    
    st.subheader("🗓️ Trip Planner")
    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

    if st.button("Save Changes"):
        conn.update(spreadsheet=url, data=edited_df, worksheet="Planner")
        
        # Phase 5: The "Boom" Logic
        if "Zoo" in edited_df['Activity'].values:
            st.info("I've noted the Zoo! Remember to check the Mission list for tickets. 🎟️")
            
        st.success("Saved to Google Sheets! 🚀")
        st.balloons()

# --- 3. THE MAP SECTION ---
    st.divider()
    st.subheader("📍 Our Sydney/Melbourne Map")

    # Center on Sydney by default
    m = folium.Map(location=[-33.8688, 151.2093], zoom_start=12)

    # Simple test pin
    folium.Marker(
        [-33.8688, 151.2093], 
        popup="Sydney Central", 
        tooltip="We start here!"
    ).add_to(m)

    st_folium(m, width="stretch", height=400)

# THIS IS THE PART THAT WAS MISSING:
except Exception as e:
    st.error(f"Something went wrong: {e}")
