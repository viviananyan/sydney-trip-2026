import urllib.parse
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import folium
from streamlit_folium import st_folium
from geopy.geocoders import ArcGIS
import requests
import pandas as pd
import datetime

@st.cache_data(ttl=3600) 
def get_aud_to_hkd_rate():
    try:
        # Flipping the API so we get how much 1 AUD costs in HKD
        url = "https://open.er-api.com/v6/latest/AUD"
        data = requests.get(url).json()
        return data['rates']['HKD']
    except:
        return 5.15 # Safe fallback if the API is offline
        # --- CONFIGURATION (UPDATE THESE WITH YOUR ACTUAL FRIENDS' NAMES!) ---
trip_users = ["Sally🦕", "Suri🐶", "Bobo🍔"]
expense_categories = ["🎟️ Activity", "🍔 Food", "🏠 Stay", "✈️ Flight", "🚗 Transport", "🛍️ Shopping", "💡 Other"]

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

with st.sidebar:
    st.header("⚙️ App Settings")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.info("Data is cached for 60s to avoid Google's speed limits. Use the button above to sync manually!")

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
tab1, tab2 = st.tabs(["🗓️ Planner & Map", "💰 Expenses"])

# --- TAB 1: PLANNER & MAP ---
with tab1:
    st.subheader("🗓️ Trip Itinerary")
    
    days = [f"Day {i}" for i in range(1, 15)]

    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner", ttl=60)
        
        required_planner_cols = [
            'Day', 'Start Time', 'End Time', 'Location', 'Activity', 'Needs Booking'
        ]
        
        for col in required_planner_cols:
            if col not in df_plan.columns:
                df_plan[col] = None
        
        df_plan = df_plan[required_planner_cols]
        df_plan = df_plan.dropna(how="all")
        df_plan['Needs Booking'] = df_plan['Needs Booking'].fillna(False).astype(bool)
        
        for col in ['Start Time', 'End Time', 'Day', 'Location', 'Activity']:
            df_plan[col] = df_plan[col].fillna("").astype(str)
            df_plan[col] = df_plan[col].replace("nan", "")
            
        df_plan = df_plan.sort_values(by=['Day', 'Start Time'], na_position='last')
        
        # 3. THE ADVANCED EDITOR
        edited_plan = st.data_editor(
            df_plan, 
            num_rows="dynamic", 
            width="stretch", 
            hide_index=True,  
            key="plan_editor_v6",
            column_config={
                "Day": st.column_config.SelectboxColumn("Day", options=days),
                "Start Time": st.column_config.TextColumn("Start Time (e.g. 09:00)"),
                "End Time": st.column_config.TextColumn("End Time (e.g. 11:30)"),
                "Location": st.column_config.TextColumn("Location"),
                "Activity": st.column_config.TextColumn("Activity"),
                "Needs Booking": st.column_config.CheckboxColumn("Needs Booking?")
            }
        )
        
        # --- THE NEW "ALL-IN-ONE" SAVE & SYNC BUTTON ---
        if st.button("💾 Save & Sync Plan"):
            # 1. Update the Planner tab
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            
            # 2. Run the Smart Sync immediately
            import pandas as pd
            # Use ttl=0 to force Streamlit to pull the freshest version of Expenses
            df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=0)
            
            existing_items = []
            if 'Item' in df_exp.columns:
                # Convert everything to lowercase to prevent duplicate errors
                existing_items = [str(x).strip().lower() for x in df_exp['Item'].fillna("").tolist()]

            new_expenses = []
            for index, row in edited_plan.iterrows():
                if row.get('Needs Booking') == True:
                    
                    item_name = str(row.get('Activity', '')).strip()
                    if not item_name or item_name.lower() == "nan":
                        item_name = str(row.get('Location', 'Unknown Booking')).strip()
                    
                    # Check in lowercase to match safely!
                    if item_name and item_name.lower() not in existing_items:
                        new_expenses.append({
                            'Date': '',
                            'Category': '🎟️ Activity',
                            'Item': item_name,
                            'Currency': 'AUD', # <-- NEW
                            'Cost': 0.0,
                            'Paid By': '',
                            'Split By': 'All',
                            'Settled': False,  # <-- NEW
                            'Remark': 'Auto-synced from Planner'
                        })
                        # Add to our lowercase checker list to prevent duplicates in the same batch
                        existing_items.append(item_name.lower())
                        
            if len(new_expenses) > 0:
                df_exp_new = pd.concat([df_exp, pd.DataFrame(new_expenses)], ignore_index=True)
                conn.update(spreadsheet=url, data=df_exp_new, worksheet="Expenses")
                st.success(f"✅ Plan saved AND automatically pushed {len(new_expenses)} new bookings to Expenses!")
            else:
                st.success("✅ Plan saved! (No new bookings needed syncing)")
                
            # Clear cache and refresh to show the clean state
            st.cache_data.clear()
            st.rerun()

        # --- PHASE 2: DYNAMIC GOOGLE MAPS ROUTING ---
        st.divider()
        st.subheader("🗺️ Daily Route Generator")
        st.write("Click a button to let Google Maps find the best route!")

        if not edited_plan.empty:
            planned_days = edited_plan['Day'].unique()
            
            for day in sorted([d for d in planned_days if str(d).strip() != ""]):
                day_schedule = edited_plan[edited_plan['Day'] == day].copy()
                valid_spots = day_schedule[day_schedule['Location'].str.strip() != ""]
                
                if len(valid_spots) > 1:
                    with st.expander(f"📍 View Routes for {day}", expanded=False):
                        for i in range(len(valid_spots) - 1):
                            start_row = valid_spots.iloc[i]
                            end_row = valid_spots.iloc[i+1]
                            
                            start_loc = str(start_row['Location'])
                            end_loc = str(end_row['Location'])
                            
                            start_enc = urllib.parse.quote(f"{start_loc}, Sydney, Australia")
                            end_enc = urllib.parse.quote(f"{end_loc}, Sydney, Australia")
                            
                            route_url = f"https://www.google.com/maps/dir/?api=1&origin={start_enc}&destination={end_enc}"
                            
                            col1, col2 = st.columns([3, 1])
                            col1.write(f"**{start_row.get('Activity', start_loc)}** ➡️ **{end_row.get('Activity', end_loc)}**")
                            col2.link_button("🗺️ Get Route", route_url)


        # 5. LOCATION MAP
        st.divider()
        st.subheader("📍 Location Map")
        m = folium.Map(location=[-33.8688, 151.2093], zoom_start=11)
        
        if 'Location' in edited_plan.columns and 'Activity' in edited_plan.columns:
            for index, row in edited_plan.iterrows():
                loc_name = str(row.get('Location', '')).strip()
                act_name = str(row.get('Activity', '')).strip()
                
                if loc_name != "" and loc_name.lower() != "nan" and loc_name.lower() != "none":
                    coords = get_coordinates(loc_name)
                    
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
        import requests

# --- TAB 2: EXPENSES & DEBTS ---
with tab2:
    st.subheader("💸 Expense Tracker")
    
    aud_to_hkd = get_aud_to_hkd_rate()
    st.caption(f"💱 **Live Exchange Rate:** 1 AUD = {aud_to_hkd:.2f} HKD")

    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=60)
        
        required_exp_cols = [
            'Date', 'Category', 'Item', 'Currency', 'Cost', 
            'Paid By', 'Split By', 'Settled', 'Remark'
        ]
        
        for col in required_exp_cols:
            if col not in df_exp.columns:
                if col == 'Currency': df_exp[col] = "AUD"
                elif col == 'Settled': df_exp[col] = False
                elif col == 'Cost': df_exp[col] = 0.0
                else: df_exp[col] = None

        df_exp = df_exp[required_exp_cols]
        df_exp = df_exp.dropna(how="all")
        
        # FORMATTING DATA TYPES (This fixes the calendar widget!)
        df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
        df_exp['Settled'] = df_exp['Settled'].fillna(False).astype(bool)
        df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)
        df_exp['Currency'] = df_exp['Currency'].replace("", "AUD") 
        
        # Calculate HKD equivalent for EVERYTHING in the background
        def normalize_to_hkd(row):
            if row['Currency'] == 'AUD':
                return row['Cost'] * aud_to_hkd
            return row['Cost']
            
        df_exp['Cost_HKD'] = df_exp.apply(normalize_to_hkd, axis=1)

        # --- TRIP OVERVIEW METRICS ---
        total_trip_cost = df_exp['Cost_HKD'].sum()
        total_settled = df_exp[df_exp['Settled'] == True]['Cost_HKD'].sum()
        total_unsettled = total_trip_cost - total_settled
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Trip Cost", f"${total_trip_cost:,.2f} HKD")
        col2.metric("Unsettled Debts", f"${total_unsettled:,.2f} HKD")
        col3.metric("Already Settled", f"${total_settled:,.2f} HKD")
        st.divider()

        # --- THE EDITOR ---
        st.write("**Ledger**")
        
        # Toggle to show/hide the HKD conversion column for your friends
        show_hkd_column = st.toggle("Show HKD Conversions in Ledger", value=False)
        
        # Determine which columns to show in the editor
        display_cols = required_exp_cols + (['Cost_HKD'] if show_hkd_column else [])

        edited_exp = st.data_editor(
            df_exp[display_cols], 
            num_rows="dynamic", 
            width="stretch", 
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "Category": st.column_config.SelectboxColumn("Category", options=expense_categories),
                "Currency": st.column_config.SelectboxColumn("Currency", options=["AUD", "HKD"]),
                "Cost": st.column_config.NumberColumn("Cost", format="%.2f"),
                "Cost_HKD": st.column_config.NumberColumn("Est. HKD", format="%.2f", disabled=True), # Read-only!
                "Paid By": st.column_config.SelectboxColumn("Paid By", options=trip_users),
                "Split By": st.column_config.SelectboxColumn("Split By", options=["All"] + trip_users),
                "Settled": st.column_config.CheckboxColumn("Settled? ✅")
            }
        )
        
        if st.button("💾 Save Expenses"):
            # We strip out the temporary 'Cost_HKD' column before saving back to Google Sheets
            clean_save_df = edited_exp.drop(columns=['Cost_HKD'], errors='ignore')
            conn.update(spreadsheet=url, data=clean_save_df, worksheet="Expenses")
            st.success("Expenses Saved!")
            st.cache_data.clear()
            st.rerun()

        # --- SMART DEBT CALCULATOR ---
        st.divider()
        st.subheader("⚖️ Active Debts (in HKD)")
        
        active_debts = edited_exp[edited_exp['Settled'] == False].copy()
        
        if not active_debts.empty:
            # We enforce that all debt tracking is shown cleanly in HKD
            st.dataframe(
                active_debts[['Item', 'Paid By', 'Split By', 'Cost_HKD']],
                hide_index=True,
                column_config={
                    "Cost_HKD": st.column_config.NumberColumn("Amount (HKD)", format="$%.2f")
                }
            )
        else:
            st.success("🎉 All debts are settled! You guys are awesome.")
            
    except Exception as e:
         st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
