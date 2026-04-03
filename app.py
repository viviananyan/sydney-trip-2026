import urllib.parse
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import folium
from streamlit_folium import st_folium
from geopy.geocoders import ArcGIS
import requests
import pandas as pd
import datetime
import itertools
import plotly.express as px

@st.cache_data(ttl=3600) 
def get_aud_to_hkd_rate():
    try:
        # Flipping the API so we get how much 1 AUD costs in HKD
        url = "https://open.er-api.com/v6/latest/AUD"
        data = requests.get(url).json()
        return data['rates']['HKD']
    except:
        return 5.15 # Safe fallback if the API is offline
# --- CONFIGURATION ---
trip_users = ["Sally🦕", "Suri🐶", "Bobo🍔"]
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

import google.generativeai as genai

# Configure Gemini
# Check if the key exists before configuring
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("🔑 AI Key missing! Please check your Streamlit Secrets.")
    model = None # Prevents the app from crashing later
model = genai.GenerativeModel('gemini-2.5-flash')

# --- TAB 1: PLANNER ---
with tab1:
    st.subheader("📍 Smart Itinerary")
    
    # 1. READ THE NEW GOOGLE SHEET SCHEMA
    try:
        df_plan = conn.read(spreadsheet=url, worksheet="Planner", ttl=60)
        
# The new super-columns including the checkbox
        required_cols = ['Day', 'End Day', 'Time', 'Item', 'Category', 'Status', 'Cost', 'Push to Expenses', 'Lat', 'Lon', 'Remark']
        for col in required_cols:
            if col not in df_plan.columns:
                if col == 'Cost': df_plan[col] = 0.0
                elif col == 'Push to Expenses': df_plan[col] = False
                else: df_plan[col] = None
                
        df_plan = df_plan[required_cols] 
        df_plan = df_plan.dropna(how="all")
        
        df_plan['Cost'] = pd.to_numeric(df_plan['Cost'], errors='coerce').fillna(0.0)
        df_plan['Lat'] = pd.to_numeric(df_plan['Lat'], errors='coerce')
        df_plan['Lon'] = pd.to_numeric(df_plan['Lon'], errors='coerce')
        
        # Force the checkbox column to be boolean (True/False)
        df_plan['Push to Expenses'] = df_plan['Push to Expenses'].astype(str).str.upper().map({'TRUE': True}).fillna(False)
        
        for col in ['Day', 'End Day', 'Time', 'Item', 'Category', 'Status', 'Remark']:
            df_plan[col] = df_plan[col].fillna("").astype(str)
            
    except Exception as e:
        st.error(f"Robot can't read the 'Planner' tab. Error: {e}")
        df_plan = pd.DataFrame(columns=['Day', 'End Day', 'Time', 'Item', 'Category', 'Status', 'Cost', 'Lat', 'Lon', 'Remark'])

    # --- CREATE SUB-TABS ---
    tab_edit, tab_visual = st.tabs(["📝 Edit Itinerary", "📅 Visual Timeline"])

    # ==========================================
    # SUB-TAB 1: THE DATA EDITOR & AI TOOL
    # ==========================================
    with tab_edit:
        # --- AI ASSISTANT SECTION ---
        with st.expander("✨ AI Quick Add (Spots, Flights, Stays)", expanded=True):
            col_input, col_btn = st.columns([4, 1])
            new_item = col_input.text_input("What are we doing or booking?", placeholder="e.g. Qantas Flight to SYD, Bondi Beach, QT Bondi 3 nights")
            
            if col_btn.button("Magic Add") and new_item:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("🔑 AI Key missing! Check your Streamlit Secrets.")
                else:
                    with st.spinner(f"Gemini is researching {new_item}..."):
                        current_plan_str = df_plan[['Day', 'Item']].to_string() if not df_plan.empty else "Empty"
                        
                        prompt = f"""
                        I am planning a trip to Australia. 
                        New Item: {new_item}
                        Current Plan: {current_plan_str}

                        Task:
                        1. Determine the category (e.g., ✈️ Flight, 🏨 Stay, 🍴 Food, 🏖️ Nature, 🏛️ Landmark).
                        2. Look at the Current Plan. If this is a location, group it with close items. 
                        3. If you aren't sure which day, assign 'TBD'. Otherwise assign 'Day X'.
                        4. If this is a hotel/stay, try to infer the checkout day based on the text (e.g., "3 nights"). If you don't know, leave end_day blank. For normal spots, leave end_day blank.
                        5. Suggest a logical Time (e.g., 10:00 AM) or leave blank.
                        6. Find the exact GPS Latitude and Longitude for this place.

                        Return ONLY a JSON object exactly like this:
                        {{"category": "emoji + category", "day": "Day X or TBD", "end_day": "Day Y or blank", "time": "HH:MM AM", "lat": float, "lon": float, "reason": "why this group?"}}
                        """
                        
                        try:
                            import json
                            response = model.generate_content(prompt)
                            res_text = response.text.replace("```json", "").replace("```", "").strip()
                            ai_data = json.loads(res_text)
                            
                            new_row = pd.DataFrame([{
                                "Day": ai_data['day'],
                                "End Day": ai_data.get('end_day', ''),
                                "Time": ai_data.get('time', ''),
                                "Item": new_item,
                                "Category": ai_data['category'],
                                "Status": "Planned",
                                "Cost": 0.0,
                                "Lat": ai_data.get('lat', None),
                                "Lon": ai_data.get('lon', None),
                                "Remark": f"AI: {ai_data.get('reason', '')}"
                            }])
                            
                            updated_df = pd.concat([df_plan, new_row], ignore_index=True)
                            conn.update(spreadsheet=url, data=updated_df, worksheet="Planner")
                            st.success(f"Added {new_item}!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI was a bit confused: {e}")

        # --- THE SPREADSHEET ---
        st.divider()
        day_options = ["TBD", ""] + [f"Day {i}" for i in range(1, 15)]
        
        edited_plan = st.data_editor(
            df_plan,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Day": st.column_config.SelectboxColumn("Start Day", options=day_options, width="small"),
                "End Day": st.column_config.SelectboxColumn("End Day (Stays)", options=day_options, width="small"),
                "Time": st.column_config.TextColumn("Time", width="small"),
                "Item": st.column_config.TextColumn("Item / Spot", required=True),
             "Category": st.column_config.SelectboxColumn(
    "Category", 
    options=[
        "✈️ Flight", "🏨 Stay", "🍴 Food", "🏖️ Nature", 
        "🏛️ Landmark", "🛍️ Shopping", "🚗 Transport", 
        "🎭 Entertainment", "💡 Other"
    ]
),
                "Status": st.column_config.SelectboxColumn("Status", options=["Planned", "Booked", "Done"]),
               # ... existing configs ...
            "Cost": st.column_config.NumberColumn("Est. Cost", format="$%.2f"),
            "Push to Expenses": st.column_config.CheckboxColumn("Push 💸", default=False), # NEW CHECKBOX
            "Lat": st.column_config.NumberColumn("Latitude", disabled=True),
            # ... existing configs ...
                "Lon": st.column_config.NumberColumn("Longitude", disabled=True)
            }
        )

        if st.button("💾 Save Planner Changes"):
            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
            st.success("Plan saved!")
            st.cache_data.clear()
            st.rerun()

    # --- FINANCIAL SYNC (SELECTIVE) ---
        st.divider()
        st.write("### 💸 Financial Sync")
        st.caption("Check the 'Push 💸' box on any items you want to send to your Expenses sheet.")
        
        if st.button("🔄 Sync Selected to Expenses"):
            with st.spinner("Syncing selected items..."):
                try:
                    # 1. Filter ONLY for items where the checkbox is ticked
                    sync_items = edited_plan[edited_plan['Push to Expenses'] == True]
                    
                    if sync_items.empty:
                        st.warning("Please check the 'Push 💸' box next to the items you want to sync!")
                    else:
                        # 2. Read the Expenses sheet
                        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=0)
                        if 'Item' not in df_exp.columns: df_exp['Item'] = ""
                        
                        existing_items = df_exp['Item'].astype(str).tolist()
                        new_expenses = []
                        
                        for _, row in sync_items.iterrows():
                            if str(row['Item']) not in existing_items:
                                new_expenses.append({
                                    "Date": row['Day'], 
                                    "Category": row['Category'],
                                    "Item": row['Item'],
                                    "Amount": row['Cost'],
                                    "Paid By": "TBD" 
                                })
                        
                        # 3. Push to Expenses tab
                        if new_expenses:
                            updated_exp = pd.concat([df_exp, pd.DataFrame(new_expenses)], ignore_index=True)
                            conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                            
                            # 4. RESET PLANNER CHECKBOXES: Uncheck them so they don't sync again!
                            edited_plan['Push to Expenses'] = False
                            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                            
                            st.success(f"Successfully synced {len(new_expenses)} items! Checkboxes have been reset.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.info("These items are already in your Expenses sheet. No duplicates added!")
                            # Reset checkboxes anyway
                            edited_plan['Push to Expenses'] = False
                            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                            st.cache_data.clear()
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"Failed to sync. Error: {e}")

    # ==========================================
    # SUB-TAB 2: THE VISUAL TIMELINE
    # ==========================================
    with tab_visual:
        if df_plan.empty:
            st.info("Your itinerary is empty! Use the AI Quick Add to get started.")
        else:
            # --- 1. THE BUCKET LIST (TBD) ---
            tbd_items = df_plan[df_plan['Day'] == 'TBD']
            if not tbd_items.empty:
                st.write("### 📌 Bucket List (Unscheduled)")
                # Show TBD items as cool little cards
                cols = st.columns(3)
                for i, row in tbd_items.iterrows():
                    with cols[i % 3]:
                        st.info(f"**{row['Category']} {row['Item']}**\n\n*Cost: ${row['Cost']}*")
                st.divider()

            # --- 2. THE SCHEDULED DAYS ---
            st.write("### 📅 Your Schedule")
            
            # Helper function to sort 'Day 1', 'Day 2', 'Day 10' properly
            def extract_day_num(day_str):
                try:
                    return int(str(day_str).lower().replace('day', '').strip())
                except:
                    return 999

            # Filter out TBD and blanks, then sort
            scheduled_df = df_plan[(df_plan['Day'] != 'TBD') & (df_plan['Day'] != '')].copy()
            scheduled_df['Day_Num'] = scheduled_df['Day'].apply(extract_day_num)
            scheduled_df = scheduled_df.sort_values(by=['Day_Num', 'Time'])

            # Group by Day and display
            days = scheduled_df['Day'].unique()
            
            for day in days:
                with st.expander(f"📍 {day}", expanded=True):
                    day_items = scheduled_df[scheduled_df['Day'] == day]
                    
                    for _, row in day_items.iterrows():
                        time_str = f"**{row['Time']}**" if row['Time'] else "*(Anytime)*"
                        end_str = f" ➡️ *(Ends: {row['End Day']})*" if row['End Day'] else ""
                        status_emoji = "✅" if row['Status'] in ['Booked', 'Done'] else "⏳"
                        
                        st.markdown(f"{time_str} | {row['Category']} **{row['Item']}** {end_str} | {status_emoji} {row['Status']}")
                        
                        if row['Remark']:
                            st.caption(f"↳ {row['Remark']}")
                            
# --- TAB 2: EXPENSES & DEBTS ---
with tab2:
    st.subheader("💸 Expense Tracker")
    
    aud_to_hkd = get_aud_to_hkd_rate()
    
    # --- GLOBAL VIEW SETTINGS ---
    col1, col2 = st.columns([1, 1])
    with col1:
        st.caption(f"💱 **Live Exchange Rate:** 1 AUD = {aud_to_hkd:.2f} HKD")
    with col2:
        target_currency = st.radio("Display Trip Overview in:", ["HKD", "AUD"], horizontal=True)

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
                elif col == 'Split By': df_exp[col] = "All"
                else: df_exp[col] = None

        df_exp = df_exp[required_exp_cols]
        df_exp = df_exp.dropna(how="all")
        
        df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
        df_exp['Settled'] = df_exp['Settled'].fillna(False).astype(bool)
        df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)
        df_exp['Currency'] = df_exp['Currency'].replace("", "AUD") 
        df_exp['Split By'] = df_exp['Split By'].replace("", "All")

        # --- 1. BACKGROUND MATH (Always calculates everything) ---
        def get_hkd(row):
            return row['Cost'] * aud_to_hkd if row['Currency'] == 'AUD' else row['Cost']
        def get_aud(row):
            return row['Cost'] / aud_to_hkd if row['Currency'] == 'HKD' else row['Cost']
            
        def get_split_count(split_str):
            s = str(split_str).strip()
            if s == 'All':
                return len(trip_users)
            involved = [u.strip() for u in s.split(',') if u.strip() in trip_users]
            return len(involved) if involved else len(trip_users)

        df_exp['Cost_HKD'] = df_exp.apply(get_hkd, axis=1)
        df_exp['Cost_AUD'] = df_exp.apply(get_aud, axis=1)
        
        df_exp['Split_Count'] = df_exp['Split By'].apply(get_split_count)
        df_exp['Per_Person_Cost'] = df_exp['Cost'] / df_exp['Split_Count']
        df_exp['Per_Person_HKD'] = df_exp['Cost_HKD'] / df_exp['Split_Count']
        df_exp['Per_Person_AUD'] = df_exp['Cost_AUD'] / df_exp['Split_Count']

        calc_col = 'Cost_HKD' if target_currency == "HKD" else 'Cost_AUD'

        # --- 2. FRONT-END DISPLAY MATH (Blanks out redundant conversions) ---
        df_exp['Display_Total_HKD'] = df_exp.apply(lambda r: r['Cost_HKD'] if r['Currency'] == 'AUD' else None, axis=1)
        df_exp['Display_Total_AUD'] = df_exp.apply(lambda r: r['Cost_AUD'] if r['Currency'] == 'HKD' else None, axis=1)
        df_exp['Display_Person_HKD'] = df_exp.apply(lambda r: r['Per_Person_HKD'] if r['Currency'] == 'AUD' else None, axis=1)
        df_exp['Display_Person_AUD'] = df_exp.apply(lambda r: r['Per_Person_AUD'] if r['Currency'] == 'HKD' else None, axis=1)

        # --- 2A: TRIP OVERVIEW ---
        st.write("### 📊 Trip Overview")
        total_trip_cost = df_exp[calc_col].sum()
        total_settled = df_exp[df_exp['Settled'] == True][calc_col].sum()
        total_unsettled = total_trip_cost - total_settled
        
        met1, met2, met3 = st.columns(3)
        met1.metric("Total Trip Cost", f"${total_trip_cost:,.2f} {target_currency}")
        met2.metric("Unsettled Debts", f"${total_unsettled:,.2f} {target_currency}")
        met3.metric("Already Settled", f"${total_settled:,.2f} {target_currency}")
        
        st.write("##### 🧑‍🤝‍🧑 Personal Expense Breakdown")
        user_shares = {user: 0.0 for user in trip_users}
        user_cat_shares = {user: {cat: 0.0 for cat in expense_categories} for user in trip_users}
        total_cat_shares = {cat: 0.0 for cat in expense_categories}
        
        for idx, row in df_exp.iterrows():
            cost = float(row[calc_col])
            cat = row['Category']
            if pd.isna(cat) or cat not in total_cat_shares:
                cat = "💡 Other" 
                
            if cost > 0:
                total_cat_shares[cat] += cost
                split_str = str(row['Split By']).strip()
                if split_str == 'All':
                    involved = trip_users
                else:
                    involved = [u.strip() for u in split_str.split(',') if u.strip() in trip_users]
                    if not involved: 
                        involved = trip_users
                        
                split_amount = cost / len(involved)
                for person in involved:
                    user_shares[person] += split_amount
                    user_cat_shares[person][cat] += split_amount
                    
        share_cols = st.columns(len(trip_users))
        for i, user in enumerate(trip_users):
            with share_cols[i]:
                st.info(f"**{user}**\n\n${user_shares[user]:,.2f} {target_currency}")

        # --- THE CUTE PIE CHARTS ---
        show_charts = st.toggle("📈 Show Category Breakdown Charts", value=False)
        if show_charts:
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.write("**Total Trip Breakdown**")
                df_total_pie = pd.DataFrame(list(total_cat_shares.items()), columns=['Category', 'Amount'])
                df_total_pie = df_total_pie[df_total_pie['Amount'] > 0] 
                
                if not df_total_pie.empty:
                    fig_total = px.pie(df_total_pie, values='Amount', names='Category', hole=0.4)
                    fig_total.update_traces(textposition='inside', textinfo='percent+label')
                    fig_total.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig_total, use_container_width=True)
                else:
                    st.caption("No expenses recorded yet!")
                    
            with chart_col2:
                st.write("**Personal Breakdown**")
                selected_user = st.selectbox("View chart for:", trip_users, label_visibility="collapsed")
                df_user_pie = pd.DataFrame(list(user_cat_shares[selected_user].items()), columns=['Category', 'Amount'])
                df_user_pie = df_user_pie[df_user_pie['Amount'] > 0]
                
                if not df_user_pie.empty:
                    fig_user = px.pie(df_user_pie, values='Amount', names='Category', hole=0.4)
                    fig_user.update_traces(textposition='inside', textinfo='percent+label')
                    fig_user.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig_user, use_container_width=True)
                else:
                    st.caption(f"No expenses recorded for {selected_user} yet!")

        st.divider()

        # --- 2B: THE CLEAN LEDGER ---
        st.write("### 📝 Ledger")
        show_conversion = st.toggle(f"Show {target_currency} conversion in Ledger", value=False)
        
        split_options = ["All"]
        for r in range(1, len(trip_users)):
            for combo in itertools.combinations(trip_users, r):
                split_options.append(", ".join(combo))
                
        base_display_cols = ['Date', 'Category', 'Item', 'Currency', 'Cost', 'Per_Person_Cost', 'Paid By', 'Split By', 'Settled', 'Remark']
        
        if show_conversion:
            if target_currency == "HKD":
                display_cols = base_display_cols[:6] + ['Display_Total_HKD', 'Display_Person_HKD'] + base_display_cols[6:]
            else:
                display_cols = base_display_cols[:6] + ['Display_Total_AUD', 'Display_Person_AUD'] + base_display_cols[6:]
        else:
            display_cols = base_display_cols

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
                "Per_Person_Cost": st.column_config.NumberColumn("Per Person", format="%.2f", disabled=True),
                
                # These columns will show as blank/un-editable when the currency matches
                "Display_Total_HKD": st.column_config.NumberColumn("Est. Total HKD", format="%.2f", disabled=True),
                "Display_Total_AUD": st.column_config.NumberColumn("Est. Total AUD", format="%.2f", disabled=True),
                "Display_Person_HKD": st.column_config.NumberColumn("Est. Person HKD", format="%.2f", disabled=True),
                "Display_Person_AUD": st.column_config.NumberColumn("Est. Person AUD", format="%.2f", disabled=True),
                
                "Paid By": st.column_config.SelectboxColumn("Paid By", options=trip_users),
                "Split By": st.column_config.SelectboxColumn("Split By", options=split_options),
                "Settled": st.column_config.CheckboxColumn("Settled? ✅")
            }
        )
        
        if st.button("💾 Save Expenses"):
            # Drop all math AND display columns so we don't pollute your database
            clean_save_df = edited_exp.drop(
                columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 
                         'Display_Total_HKD', 'Display_Total_AUD', 'Display_Person_HKD', 'Display_Person_AUD'], 
                errors='ignore'
            )
            conn.update(spreadsheet=url, data=clean_save_df, worksheet="Expenses")
            st.success("Expenses Saved!")
            st.cache_data.clear()
            st.rerun()

        # --- 2C: SMART SETTLEMENT ENGINE ---
        st.divider()
        st.subheader("⚖️ Unified Net Balances")
        st.write("Settle up in whichever currency you prefer! (Green = You are owed money / Red = You owe money)")
        
        active_debts = edited_exp[edited_exp['Settled'] == False].copy()
        
        if not active_debts.empty:
            balances_aud = {user: 0.0 for user in trip_users}
            
            for idx, row in active_debts.iterrows():
                raw_cost = float(row['Cost'])
                currency = row['Currency']
                
                if currency == 'HKD':
                    cost_in_aud = raw_cost / aud_to_hkd
                else:
                    cost_in_aud = raw_cost
                    
                payer = str(row['Paid By']).strip()
                split_str = str(row['Split By']).strip()
                
                if cost_in_aud > 0 and payer in balances_aud:
                    if split_str == 'All':
                        involved = trip_users
                    else:
                        involved = [u.strip() for u in split_str.split(',') if u.strip() in trip_users]
                        if not involved: 
                            involved = trip_users
                            
                    split_amount = cost_in_aud / len(involved)
                    
                    balances_aud[payer] += cost_in_aud
                    for person in involved:
                        balances_aud[person] -= split_amount

            cols = st.columns(len(trip_users))
            for i, user in enumerate(trip_users):
                with cols[i]:
                    st.write(f"**{user}**")
                    net_aud = balances_aud[user]
                    net_hkd = net_aud * aud_to_hkd 
                    
                    if net_aud > 0.01:
                        st.success(f"+ ${net_aud:.2f} AUD\n\n(+ ${net_hkd:.2f} HKD)")
                    elif net_aud < -0.01:
                        st.error(f"- ${abs(net_aud):.2f} AUD\n\n(- ${abs(net_hkd):.2f} HKD)")
                    else:
                        st.write("All Settled!")

        else:
            st.success("🎉 All debts are settled!")
            
    except Exception as e:
         st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
