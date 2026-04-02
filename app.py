import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import ArcGIS

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

# --- 1. CONNECTION SETUP ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection failed! The real error is: {e}")
    st.stop()

# DON'T FORGET TO PASTE YOUR GOOGLE SHEET URL HERE!
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=743694833#gid=743694833"

st.title("🇦🇺 Australia Trip Hub 2026")

# --- THE SMART MAP TRANSLATOR (ArcGIS Version) ---
@st.cache_data(show_spinner=False)
def get_coordinates(location_name):
    try:
        # We swapped Nominatim for ArcGIS!
        geolocator = ArcGIS()
        
        # Ask it to find the location in Australia
        location = geolocator.geocode(f"{location_name}, Australia", timeout=10)
        
        if location:
            return [location.latitude, location.longitude]
        else:
            return None
            
    except Exception as e:
        st.error(f"ArcGIS crashed on '{location_name}'! The error: {e}")
        return None

# --- 2. CREATE THE TABS ---
tab1, tab2, tab3 = st.tabs(["🗓️ Planner & Map", "🎯 Missions", "💰 Expenses"])

# --- TAB 1: PLANNER & MAP ---
with tab1:
    st.subheader("🗓️ Trip Itinerary")
    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner")
        
        # 1. THE AGGRESSIVE CLEANING STATION
        df_plan = df_plan.dropna(how="all")
        
        # FORCE everything to be text so you can type "3/8" or emojis
        for col in df_plan.columns:
            df_plan[col] = df_plan[col].fillna("").astype(str)
        
        # 2. THE EDITOR
        edited_plan = st.data_editor(
            df_plan, 
            num_rows="dynamic", 
            width="stretch", 
            key="plan_editor"
        )
        
        if st.button("Save Plan"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan Saved!")

        st.divider()
        st.subheader("📍 Location Map")
        
        # (The rest of your map code remains the same...)
        st.write("🕵️ **Robot's Thought Process:**")
        m = folium.Map(location=[-33.8688, 151.2093], zoom_start=11)
        
        if 'Location' in edited_plan.columns and 'Activity' in edited_plan.columns:
            for index, row in edited_plan.iterrows():
                loc_name = str(row.get('Location', '')).strip()
                act_name = str(row.get('Activity', '')).strip()
                
                if loc_name != "" and loc_name.lower() != "nan" and loc_name.lower() != "none":
                    coords = get_coordinates(loc_name)
                    st.write(f"- Searching for '{loc_name}'... Coordinates: `{coords}`")
                    
                    if coords:
                        folium.Marker(
                            coords, 
                            popup=f"<b>{act_name}</b><br>{loc_name}", 
                            tooltip=act_name if act_name else loc_name,
                            icon=folium.Icon(color="red", icon="info-sign")
                        ).add_to(m)

        st_folium(m, width="stretch", height=400, key="trip_map")
        
    except Exception as e:
        st.error(f"Robot can't read the 'Planner' tab. Error: {e}")

# --- TAB 2: MISSIONS ---
with tab2:
    st.subheader("🎯 Trip Missions (To-Do)")
    try:
        df_miss = conn.read(spreadsheet=url, worksheet="Missions")
        
        # 1. THE CLEANING STATION
        df_miss = df_miss.dropna(how="all")
        
        # Ensure 'Done' column exists and is True/False (Boolean)
        # Make sure your Google Sheet has a column named exactly 'Done'
        if 'Done' in df_miss.columns:
            df_miss['Done'] = df_miss['Done'].fillna(False).astype(bool)
        
        # Fill all other empty cells with blank text
        for col in df_miss.columns:
            if col != 'Done':
                df_miss[col] = df_miss[col].fillna("").astype(str)
        
        # 2. THE MISSION EDITOR
        edited_miss = st.data_editor(
            df_miss, 
            num_rows="dynamic", 
            width="stretch", 
            key="miss_editor",
            column_config={
                # This turns the 'Done' column into clickable checkboxes!
                "Done": st.column_config.CheckboxColumn("Done?", default=False)
            }
        )
        
        if st.button("Save Missions"):
            conn.update(spreadsheet=url, data=edited_miss, worksheet="Missions")
            st.success("Missions Updated!")

    except Exception as e:
        st.error(f"Robot can't read the 'Missions' tab. The real error is: {e}")

# --- TAB 3: EXPENSES ---
with tab3:
    st.subheader("💰 Expense Manager")
    
    # Update these names to match your travel group!
    users = ["Sally", "Suri", "Bobo"] 
    categories = ["🍔 Food", "🚗 Transport", "🏨 Hotel", "🎟️ Activity", "🛍️ Shopping", "✨ Other"]

    try:
        # Read live data (ttl=0 avoids the "old photo" problem)
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=0)
        
        # 1. FORCE COLUMNS (Ensures new columns show up immediately)
        required_cols = ['Date', 'Category', 'Item', 'Cost', 'Paid By', 'Remark']
        for col in required_cols:
            if col not in df_exp.columns:
                df_exp[col] = None
        
        # Keep only our required columns in order
        df_exp = df_exp[required_cols]

        # 2. DATA CLEANING & TYPE CONVERSION
        df_exp = df_exp.dropna(how="all")
        
        # Convert Date string to a Calendar object
        if 'Date' in df_exp.columns:
            df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
            
        # Convert Cost to a number
        if 'Cost' in df_exp.columns:
            df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)
            
        # Ensure text columns are actually strings
        for col in ['Category', 'Item', 'Paid By', 'Remark']:
            df_exp[col] = df_exp[col].fillna("").astype(str)

        # 3. THE ADVANCED EDITOR
        edited_exp = st.data_editor(
            df_exp, 
            num_rows="dynamic", 
            width="stretch", 
            key="exp_editor_final", 
            column_config={
                "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "Category": st.column_config.SelectboxColumn("Category", options=categories),
                "Paid By": st.column_config.SelectboxColumn("Paid By", options=users),
                "Cost": st.column_config.NumberColumn("Cost ($)", format="$%.2f", min_value=0),
                "Remark": st.column_config.TextColumn("Remark"),
            }
        )
        
        if st.button("Save All Changes"):
            conn.update(spreadsheet=url, data=edited_exp, worksheet="Expenses")
            st.success("Expenses updated and synced!")

        # 4. FINANCIAL OVERVIEW & SETTLEMENT
        st.divider()
        if not edited_exp.empty:
            total_spend = edited_exp['Cost'].sum()
            
            col1, col2 = st.columns(2)
            col1.metric("Total Trip Spend", f"${total_spend:.2f} AUD")
            col2.metric("Per Person", f"${total_spend/len(users):.2f} AUD")

            st.write("### 💸 Who Owes Who")
            
            # Calculate what each person PAID
            paid_summary = edited_exp.groupby('Paid By')['Cost'].sum().reindex(users, fill_value=0)
            
            # What each person SHOULD HAVE paid
            fair_share = total_spend / len(users)
            
            summary_data = []
            for user in users:
                amount_paid = paid_summary[user]
                balance = amount_paid - fair_share
                
                # Green if they overpaid (owe them money), Red if they underpaid
                status = "🟢 To receive" if balance > 0 else "🔴 To pay"
                
                summary_data.append({
                    "Person": user,
                    "Total Paid": f"${amount_paid:.2f}",
                    "Balance": f"${abs(balance):.2f}",
                    "Status": status
                })
            
            st.table(summary_data)
            
    except Exception as e:
        st.error(f"Financial Robot hit a snag: {e}")
