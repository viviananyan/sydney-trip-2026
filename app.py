import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

# --- 1. CONNECTION SETUP ---
try:
    # Look how clean this is! Streamlit will automatically check your Secrets vault now.
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection failed! The real error is: {e}")
    st.stop()

# DON'T FORGET TO PASTE YOUR URL HERE AGAIN!
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=743694833#gid=743694833"

st.title("🇦🇺 Australia Trip Hub 2026")

# --- 2. CREATE THE TABS ---
tab1, tab2, tab3 = st.tabs(["🗓️ Planner & Map", "🎯 Missions", "💰 Expenses"])

# --- TAB 1: PLANNER & MAP ---
with tab1:
    st.subheader("Trip Itinerary")
    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner")
        edited_plan = st.data_editor(df_plan, num_rows="dynamic", width="stretch", key="plan_editor")
        
        if st.button("Save Plan"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan Saved!")

        st.divider()
        st.subheader("📍 Location Map")
        m = folium.Map(location=[-33.8688, 151.2093], zoom_start=12)
        st_folium(m, width="stretch", height=400)
        
    except Exception as e:
        st.error(f"Robot can't read the 'Planner' tab. The real error is: {e}")

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
        edited_exp = st.data_editor(df_exp, num_rows="dynamic", width="stretch", key="exp_editor")
        
        if st.button("Save Expenses"):
            conn.update(spreadsheet=url, data=edited_exp, worksheet="Expenses")
            st.success("Expenses Saved!")
            
        # Quick Math: Total Cost
        if not df_exp.empty and 'Cost' in df_exp.columns:
            total = df_exp['Cost'].sum()
            st.metric("Total Trip Spend", f"${total:.2f} AUD")
            st.write(f"Each person owes: **${total/3:.2f}**")
    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. The real error is: {e}")
