import urllib.parse
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
    
    # New Configuration Lists
    days = [f"Day {i}" for i in range(1, 15)] # This dynamically creates Day 1 through Day 14!]
    transit_modes = ["🚶 Walk", "🚆 Train", "🚌 Bus", "🚕 Uber/Taxi", "⛴️ Ferry", "🚗 Drive"]

    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner", ttl=60)
        
        # 1. FORCE ALL REQUIRED COLUMNS
        required_planner_cols = [
            'Day', 'Start Time', 'End Time', 'Location', 'Activity', 
            'Transport', 'Needs Booking', 'Sent to Expenses'
        ]
        
        for col in required_planner_cols:
            if col not in df_plan.columns:
                df_plan[col] = None
        
        df_plan = df_plan[required_planner_cols]
                
        # 2. THE CLEANING STATION
        df_plan = df_plan.dropna(how="all")
        
        df_plan['Needs Booking'] = df_plan['Needs Booking'].fillna(False).astype(bool)
        df_plan['Sent to Expenses'] = df_plan['Sent to Expenses'].fillna(False).astype(bool)
        
        # BULLETPROOF TIME PARSER
        import pandas as pd
        for col in ['Start Time', 'End Time']:
            # Convert text to datetime, turning bad/empty data into NaT
            dt_col = pd.to_datetime(df_plan[col].astype(str), errors='coerce')
            # Extract time and convert NaT strictly to Python's 'None' to prevent Streamlit crashes
            df_plan[col] = dt_col.dt.time.apply(lambda x: x if pd.notna(x) else None)
            
        # Text columns
        for col in ['Day', 'Location', 'Activity', 'Transport']:
            df_plan[col] = df_plan[col].fillna("").astype(str)
            df_plan[col] = df_plan[col].replace("nan", "")
            
        # Sort the table chronologically
        df_plan = df_plan.sort_values(by=['Day', 'Start Time'], na_position='last')
        
        # 3. THE ADVANCED EDITOR
        edited_plan = st.data_editor(
            df_plan, 
            num_rows="dynamic", 
            width="stretch", 
            key="plan_editor_v3",
            column_config={
                "Day": st.column_config.SelectboxColumn("Day", options=days),
                "Start Time": st.column_config.TimeColumn("Start Time", format="HH:mm"),
                "End Time": st.column_config.TimeColumn("End Time", format="HH:mm"),
                "Location": st.column_config.TextColumn("Location"),
                "Activity": st.column_config.TextColumn("Activity"),
                "Transport": st.column_config.SelectboxColumn("Transport", options=transit_modes),
                "Needs Booking": st.column_config.CheckboxColumn("Needs Booking?"),
                "Sent to Expenses": st.column_config.CheckboxColumn("Synced?") 
            }
        )
        
        if st.button("Save Plan"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan Saved!")

        # --- PHASE 2: DYNAMIC GOOGLE MAPS ROUTING ---
        st.divider()
        st.subheader("🗺️ Daily Route Generator")
        st.write("Click a button to open Google Maps with your pre-loaded route!")

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
                            
                            transport_raw = str(end_row.get('Transport', ''))
                            gmaps_mode = "transit" 
                            if "Walk" in transport_raw: gmaps_mode = "walking"
                            elif "Uber" in transport_raw or "Drive" in transport_raw: gmaps_mode = "driving"
                            
                            # Safely encode the locations for a web URL
                            start_enc = urllib.parse.quote(f"{start_loc}, Sydney, Australia")
                            end_enc = urllib.parse.quote(f"{end_loc}, Sydney, Australia")
                            
                            # The CORRECT Official Google Maps API Link
                            route_url = f"https://www.google.com/maps/dir/?api=1&origin={start_enc}&destination={end_enc}&travelmode={gmaps_mode}"
                            
                            col1, col2 = st.columns([3, 1])
                            col1.write(f"**{start_row.get('Activity', start_loc)}** ➡️ **{end_row.get('Activity', end_loc)}**")
                            
                            btn_icon = transport_raw.split(" ")[0] if transport_raw else "🗺️"
                            col2.link_button(f"{btn_icon} Route", route_url)

        # 4. THE GATEKEEPER: SMART SYNC BUTTON
        st.divider()
        st.subheader("🤖 Smart Sync")
        st.write("Click below to send any checked 'Needs Booking' items to your Expenses tab.")
        
        if st.button("📥 Push Bookings to Expenses"):
            new_expenses = []
            for index, row in edited_plan.iterrows():
                if row['Needs Booking'] == True and row['Sent to Expenses'] == False:
                    
                    item_name = str(row.get('Activity', '')).strip()
                    if item_name == "" or item_name.lower() == "nan":
                        item_name = str(row.get('Location', 'Unknown Booking')).strip()
                        
                    new_expenses.append({
                        'Date': '',
                        'Category': '🎟️ Activity',
                        'Item': item_name,
                        'Cost': 0.0,
                        'Paid By': 'Sally🦕',
                        'Split By': 'All',
                        'Remark': 'Auto-synced from Planner'
                    })
                    edited_plan.at[index, 'Sent to Expenses'] = True
                    
            if len(new_expenses) > 0:
                conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=0)
                df_exp_new = pd.concat([df_exp, pd.DataFrame(new_expenses)], ignore_index=True)
                conn.update(spreadsheet=url, data=df_exp_new, worksheet="Expenses")
                
                st.success(f"🎉 Successfully pushed {len(new_expenses)} items to Expenses!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("Everything is up to date! No new bookings to sync.")
        # 5. LOCATION MAP
        st.divider()
        st.subheader("📍 Location Map")
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
# --- TAB 2: EXPENSES ---
with tab2:
    st.subheader("💰 Expense Manager")

    # 1. CONFIGURATION 
    users = ["Sally🦕", "Suri🐶", "Bobo🍔"] 
    categories = ["🍔 Food", "🚗 Transport", "🏨 Hotel", "🎟️ Activity", "🛍️ Shopping", "✨ Other"]

    # Auto-generate dropdown combinations for 3 people
    split_options = [
        "All", 
        users[0], users[1], users[2], 
        f"{users[0]}, {users[1]}", 
        f"{users[0]}, {users[2]}", 
        f"{users[1]}, {users[2]}"
    ]

    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=60)

        # 2. FORCE COLUMNS 
        required_cols = ['Date', 'Category', 'Item', 'Cost', 'Paid By', 'Split By', 'Remark']
        for col in required_cols:
            if col not in df_exp.columns:
                df_exp[col] = None

        df_exp = df_exp[required_cols]

        # 3. DATA CLEANING
        df_exp = df_exp.dropna(how="all")

        if 'Date' in df_exp.columns:
            df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
        if 'Cost' in df_exp.columns:
            df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)

        for col in ['Category', 'Item', 'Paid By', 'Split By', 'Remark']:
            df_exp[col] = df_exp[col].fillna("").astype(str)
            if col == 'Split By':
                df_exp[col] = df_exp[col].replace("", "All")

        # 4. THE EDITOR
        edited_exp = st.data_editor(
            df_exp, 
            num_rows="dynamic", 
            width="stretch", 
            key="exp_editor_v6", 
            column_config={
                "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "Category": st.column_config.SelectboxColumn("Category", options=categories),
                "Paid By": st.column_config.SelectboxColumn("Paid By", options=users),
                "Split By": st.column_config.SelectboxColumn("Split By", options=split_options),
                "Cost": st.column_config.NumberColumn("Cost ($)", format="$%.2f", min_value=0),
                "Remark": st.column_config.TextColumn("Remark"),
            }
        )

        if st.button("Save All Changes"):
            conn.update(spreadsheet=url, data=edited_exp, worksheet="Expenses")
            st.success("Expenses updated and synced!")

        # 5. THE NEW LINE-BY-LINE SETTLEMENT ENGINE
        st.divider()
        if not edited_exp.empty:
            total_spend = edited_exp['Cost'].sum()
            st.metric("Total Trip Spend", f"${total_spend:.2f} AUD")

            st.write("### 💸 Who Owes Who")

            # Setup tracking dictionaries
            balances = {u: 0.0 for u in users}
            total_paid = {u: 0.0 for u in users}

            # Read every single receipt one by one
            for index, row in edited_exp.iterrows():
                cost = float(row.get('Cost', 0.0))
                paid_by = str(row.get('Paid By', '')).strip()
                split_val = str(row.get('Split By', 'All')).strip()

                if cost > 0 and paid_by in users:
                    # Credit the person who paid out of pocket
                    total_paid[paid_by] += cost
                    balances[paid_by] += cost

                    # Figure out who shares this specific bill
                    if split_val == "All" or split_val == "None":
                        debtors = users
                    else:
                        # Find exactly which names are in the dropdown string
                        debtors = [u for u in users if u in split_val]
                        if not debtors: 
                            debtors = users

                    # Debit the fraction from everyone involved
                    split_cost = cost / len(debtors)
                    for d in debtors:
                        balances[d] -= split_cost

            # Display the final math
            summary_data = []
            for user in users:
                bal = balances[user]
                if bal > 0.01:
                    status = "🟢 To receive"
                elif bal < -0.01:
                    status = "🔴 To pay"
                else:
                    status = "⚪ Settled"

                summary_data.append({
                    "Person": user,
                    "Total Paid": f"${total_paid[user]:.2f}",
                    "Balance": f"${abs(bal):.2f}",
                    "Status": status
                })

            st.table(summary_data)

    except Exception as e:
        st.error(f"Financial Robot hit a snag: {e}")
