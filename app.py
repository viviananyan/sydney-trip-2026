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

        # Removed Cost, changed Map Link to Link
        required_cols = ['Day', 'End Day', 'Time', 'Item', 'Area', 'Category', 'Status', 'Push to Expenses', 'Link', 'Remark']
        for col in required_cols:
            if col not in df_plan.columns:
                if col == 'Push to Expenses': df_plan[col] = False
                else: df_plan[col] = None

        df_plan = df_plan[required_cols] 
        df_plan = df_plan.dropna(how="all")

        df_plan['Push to Expenses'] = df_plan['Push to Expenses'].astype(str).str.upper().map({'TRUE': True}).fillna(False)

        for col in ['Day', 'End Day', 'Time', 'Item', 'Area', 'Category', 'Status', 'Link', 'Remark']:
            df_plan[col] = df_plan[col].fillna("").astype(str)

    except Exception as e:
        st.error(f"Robot can't read the 'Planner' tab. Error: {e}")
        df_plan = pd.DataFrame(columns=['Day', 'End Day', 'Time', 'Item', 'Area', 'Category', 'Status', 'Push to Expenses', 'Link', 'Remark'])

    # --- CREATE SUB-TABS ---
    tab_edit, tab_visual = st.tabs(["📝 Edit Itinerary", "📅 Visual Timeline"])

    # ==========================================
    # SUB-TAB 1: THE DATA EDITOR & AI TOOLS
    # ==========================================
    with tab_edit:

        col_left, col_right = st.columns(2)

        # --- TOOL 1: AI QUICK ADD ---
        with col_left:
            with st.expander("✨ AI Quick Add", expanded=True):
                new_item = st.text_input("Add a new spot, tour, or booking:", placeholder="e.g. Blue Mountains Day Tour")
                if st.button("Magic Add") and new_item:
                    if "GEMINI_API_KEY" not in st.secrets:
                        st.error("🔑 AI Key missing!")
                    else:
                        with st.spinner("Researching..."):
                            current_plan_str = df_plan[['Day', 'Item']].to_string() if not df_plan.empty else "Empty"

                            prompt = f"""
                            Task: Add "{new_item}" to this Australian trip plan.
                            Current Plan: {current_plan_str}

                            1. Category: Exactly one of [✈️ Flight, 🏨 Stay, 🍴 Food, 🏖️ Nature, 🏛️ Landmark, 🛍️ Shopping, 🚗 Transport, 🎭 Entertainment, 💡 Other].
                            2. Day: Group with close items. If unsure, assign 'TBD'.
                            3. End Day: If it's a stay, infer checkout. Otherwise blank.
                            4. Time: BEST time to visit. CRITICAL: strictly use English 24-hour (e.g. 15:00) or AM/PM (e.g. 03:00 PM). NO localized text (e.g., no '下午').
                            5. Area: General neighborhood (if applicable, else blank).
                            5. Area: General neighborhood. IF it is a flight or train, format it as "Origin ✈️ Destination" (e.g., "SYD ✈️ MEL").
                            6. Link: A highly relevant URL (Google Maps for spots, Wikipedia for landmarks, etc).
                            7. Remark: Maximum 3 words, or blank.

                            Return ONLY JSON:
                            {{"category": "...", "day": "Day X or TBD", "end_day": "...", "time": "...", "area": "...", "link": "...", "remark": "..."}}
                            """
                            try:
                                import json
                                response = model.generate_content(prompt)
                                res_text = response.text.replace("```json", "").replace("```", "").strip()
                                ai_data = json.loads(res_text)

                                new_row = pd.DataFrame([{
                                    "Day": ai_data['day'], "End Day": ai_data.get('end_day', ''),
                                    "Time": ai_data.get('time', ''), "Item": new_item, "Area": ai_data.get('area', ''),
                                    "Category": ai_data['category'], "Status": "Planned", 
                                    "Push to Expenses": False, "Link": ai_data.get('link', ''), "Remark": ai_data.get('remark', '')
                                }])
                                updated_df = pd.concat([df_plan, new_row], ignore_index=True)
                                conn.update(spreadsheet=url, data=updated_df, worksheet="Planner")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # --- TOOL 2: TBD AUTO-SCHEDULER ---
        with col_right:
            with st.expander("🗂️ TBD Auto-Scheduler", expanded=True):
                tbd_items = df_plan[df_plan['Day'] == 'TBD']['Item'].tolist()
                if not tbd_items:
                    st.info("No 'TBD' items! Add some to your Bucket List.")
                else:
                    selected_tbds = st.multiselect("Select Bucket List items to schedule:", tbd_items)
                    if st.button("🤖 Let AI Schedule These") and selected_tbds:
                        with st.spinner("AI is analyzing your itinerary..."):
                            scheduled_only = df_plan[df_plan['Day'] != 'TBD'][['Day', 'Time', 'Item', 'Area']].to_string()

                            schedule_prompt = f"""
                            I need to schedule these items: {selected_tbds}.
                            Here is my current schedule: {scheduled_only}
                            
                            Task: Find the most logical Day and Time for EACH item based on geography and existing plans. 
                            Time MUST strictly be in English 24-hour (15:00) or AM/PM (03:00 PM). NO localized text.
                            
                            Return ONLY a JSON list of objects:
                            [ {{"item": "exact name", "day": "Day X", "time": "..."}} ]
                            """
                            try:
                                import json
                                response = model.generate_content(schedule_prompt)
                                res_text = response.text.replace("```json", "").replace("```", "").strip()
                                ai_updates = json.loads(res_text)

                                # Update the dataframe
                                for update in ai_updates:
                                    idx = df_plan.index[df_plan['Item'] == update['item']].tolist()
                                    if idx:
                                        df_plan.at[idx[0], 'Day'] = update['day']
                                        df_plan.at[idx[0], 'Time'] = update['time']

                                conn.update(spreadsheet=url, data=df_plan, worksheet="Planner")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # --- THE SPREADSHEET ---
        st.divider()
        day_options = ["TBD", ""] + [f"Day {i}" for i in range(1, 15)]

        # --- MOBILE-FRIENDLY ADD & AI POLISH ---
col_mob, col_ai = st.columns(2)

with col_mob:
    with st.expander("📱 Mobile-Friendly Add", expanded=False):
        with st.form("mobile_add_plan"):
            m_item = st.text_input("Item Name (e.g., Sydney Opera House)")
            m_day = st.selectbox("Day", ["TBD"] + [f"Day {i}" for i in range(1, 15)])
            m_cat = st.selectbox("Category", ["✈️ Flight", "🏨 Stay", "🍴 Food", "🏖️ Nature", "🏛️ Landmark", "💡 Other"])
            m_time = st.text_input("Time (HH:MM or blank)")
            if st.form_submit_button("Add to Plan"):
                new_row = pd.DataFrame([{"Day": m_day, "Time": m_time, "Item": m_item, "Category": m_cat, "Area": "", "Link": "", "Status": "Planned", "Push to Expenses": False, "Remark": ""}])
                updated_df = pd.concat([df_plan, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Planner")
                st.cache_data.clear()
                st.rerun()

with col_ai:
    with st.expander("🪄 AI Magic Polish", expanded=False):
        st.write("Fixes sloppy names and missing areas!")
        if st.button("Polish Existing Entries"):
            with st.spinner("AI is researching locations..."):
                # Pass a simplified list to AI to save tokens
                items_to_fix = df_plan[['Item', 'Area']].to_dict('records')
                prompt = f"""
                Task: Standardize these travel items.
                Input: {items_to_fix}
                1. If 'Item' is casual (e.g., 'opera house'), change to official ('Sydney Opera House').
                2. If 'Area' is empty or wrong, provide the correct city/neighborhood. If a flight, use 'Origin ✈️ Dest'.
                Return ONLY JSON: [ {{"old_item": "...", "new_item": "...", "new_area": "..."}} ]
                """
                try:
                    import json
                    res = model.generate_content(prompt)
                    updates = json.loads(res.text.replace("```json", "").replace("```", "").strip())
                    
                    for u in updates:
                        idx = df_plan.index[df_plan['Item'] == u['old_item']].tolist()
                        if idx:
                            df_plan.at[idx[0], 'Item'] = u['new_item']
                            df_plan.at[idx[0], 'Area'] = u['new_area']
                    conn.update(spreadsheet=url, data=df_plan, worksheet="Planner")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        edited_plan = st.data_editor(
            df_plan,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Day": st.column_config.SelectboxColumn("Start", options=day_options, width="small"),
                "End Day": st.column_config.SelectboxColumn("End", options=day_options, width="small"),
                "Time": st.column_config.TextColumn("Time", width="small"),
                "Item": st.column_config.TextColumn("Item / Spot", required=True),
                "Area": st.column_config.TextColumn("Area", width="small"),
                "Category": st.column_config.SelectboxColumn(
                    "Category", 
                    options=[
                        "✈️ Flight", "🏨 Stay", "🍴 Food", "🏖️ Nature", 
                        "🏛️ Landmark", "🛍️ Shopping", "🚗 Transport", 
                        "🎭 Entertainment", "💡 Other"
                    ]
                ),
                "Status": st.column_config.SelectboxColumn("Status", options=["Planned", "Booked", "Done"]),
                "Push to Expenses": st.column_config.CheckboxColumn("Push 💸", default=False),
                "Link": st.column_config.LinkColumn("URL/Link", display_text="🔗 Open")
            }
        )

        col_save, col_sync = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save Planner Changes", use_container_width=True):
                conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                st.success("Plan saved!")
                st.cache_data.clear()
                st.rerun()

        with col_sync:
            if st.button("🔄 Sync 'Push 💸' to Expenses", use_container_width=True):
                with st.spinner("Syncing..."):
                    sync_items = edited_plan[edited_plan['Push to Expenses'] == True]
                    if sync_items.empty:
                        st.warning("Check the 'Push 💸' boxes first!")
                    else:
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
                                    "Amount": 0.0,  # Defaults to 0 so you can fill it in later!
                                    "Paid By": "TBD" 
                                })

                        if new_expenses:
                            updated_exp = pd.concat([df_exp, pd.DataFrame(new_expenses)], ignore_index=True)
                            conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                            edited_plan['Push to Expenses'] = False
                            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                            st.rerun()
                        else:
                            st.info("Already synced!")
                            edited_plan['Push to Expenses'] = False
                            conn.update(spreadsheet=url, data=edited_plan, worksheet="Planner")
                            st.rerun()

    # ==========================================
    # SUB-TAB 2: THE VISUAL TIMELINE
    # ==========================================
    with tab_visual:
        if df_plan.empty:
            st.info("Your itinerary is empty! Use the AI Quick Add to get started.")
        else:
            # --- THE BUCKET LIST (TBD) ---
            tbd_items = df_plan[df_plan['Day'] == 'TBD']
            if not tbd_items.empty:
                st.write("### 📌 Bucket List (Unscheduled)")
                cols = st.columns(3)
                for i, row in tbd_items.iterrows():
                    with cols[i % 3]:
                        area_str = f"\n*🏙️ {row['Area']}*" if row['Area'] else ""
                        link_str = f"\n[🔗 Link]({row['Link']})" if row['Link'] else ""
                        st.info(f"**{row['Category']} {row['Item']}**{area_str}{link_str}")
                st.divider()

            # --- THE SCHEDULED DAYS ---
            st.write("### 📅 Your Schedule")

            def extract_day_num(day_str):
                try:
                    return int(str(day_str).lower().replace('day', '').strip())
                except:
                    return 999

            scheduled_df = df_plan[(df_plan['Day'] != 'TBD') & (df_plan['Day'] != '')].copy()
            scheduled_df['Day_Num'] = scheduled_df['Day'].apply(extract_day_num)
            scheduled_df = scheduled_df.sort_values(by=['Day_Num', 'Time'])

            days = scheduled_df['Day'].unique()

            for day in days:
                with st.expander(f"📍 {day}", expanded=True):
                    day_items = scheduled_df[scheduled_df['Day'] == day]

                    for _, row in day_items.iterrows():
                        time_str = f"**{row['Time']}**" if row['Time'] else "*(Anytime)*"
                        end_str = f" ➡️ *(Ends: {row['End Day']})*" if row['End Day'] else ""
                        status_emoji = "✅" if row['Status'] in ['Booked', 'Done'] else "⏳"

                        area_str = f" | 🏙️ *{row['Area']}*" if row['Area'] else ""
                        link_str = f" | [🔗 Link]({row['Link']})" if row['Link'] else ""

                        st.markdown(f"{time_str} | {row['Category']} **{row['Item']}** {end_str}{area_str}{link_str} | {status_emoji} {row['Status']}")

                        if row['Remark']:
                            st.caption(f"↳ {row['Remark']}")

# --- TAB 2: EXPENSES & DEBTS ---
with tab2:
    st.subheader("💸 Expense Tracker")

    aud_to_hkd = get_aud_to_hkd_rate()

    with st.expander("📱 Add Expense (Mobile Friendly)", expanded=False):
    with st.form("mobile_add_exp"):
        e_date = st.date_input("Date")
        e_item = st.text_input("What did you buy?")
        e_cost = st.number_input("Cost", min_value=0.0, format="%.2f")
        e_curr = st.selectbox("Currency", ["AUD", "HKD"])
        e_payer = st.selectbox("Paid By", trip_users)
        e_split = st.selectbox("Split By", split_options)
        e_cat = st.selectbox("Category", expense_categories)
        
        if st.form_submit_button("Add Expense"):
            new_exp = pd.DataFrame([{"Date": e_date, "Category": e_cat, "Item": e_item, "Currency": e_curr, "Cost": e_cost, "Paid By": e_payer, "Split By": e_split, "Remark": ""}])
            # Use drop to ensure we don't accidentally push math columns back to the sheet
            clean_save_df = edited_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 'Display_Total_HKD', 'Display_Total_AUD', 'Display_Person_HKD', 'Display_Person_AUD'], errors='ignore')
            updated_exp = pd.concat([clean_save_df, new_exp], ignore_index=True)
            conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
            st.cache_data.clear()
            st.rerun()

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
            'Paid By', 'Split By', 'Remark'
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
        # --- 1. BACKGROUND MATH ---
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
        # --- 2. FRONT-END DISPLAY MATH ---
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
        # --- THE PIE CHARTS ---
        show_charts = st.toggle("📈 Show Category Breakdown Charts", value=False)
        if show_charts:
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.write("**Total Trip Breakdown**")
                df_total_pie = pd.DataFrame(list(total_cat_shares.items()), columns=['Category', 'Amount'])
                df_total_pie = df_total_pie[df_total_pie['Amount'] > 0] 

                if not df_total_pie.empty:
                    import plotly.express as px
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

        with st.expander("📱 Add Expense (Mobile Friendly)", expanded=False):
            with st.form("mobile_add_exp"):
                e_date = st.date_input("Date")
                e_item = st.text_input("What did you buy?")
                e_cost = st.number_input("Cost", min_value=0.0, format="%.2f")
                e_curr = st.selectbox("Currency", ["AUD", "HKD"])
                e_payer = st.selectbox("Paid By", trip_users)
                e_split = st.selectbox("Split By", split_options)
                e_cat = st.selectbox("Category", expense_categories)
                
                if st.form_submit_button("Add Expense"):
                    new_exp = pd.DataFrame([{
                        "Date": e_date, "Category": e_cat, "Item": e_item, 
                        "Currency": e_curr, "Cost": e_cost, "Paid By": e_payer, 
                        "Split By": e_split, "Remark": ""
                    }])
                    # Use drop to ensure we don't accidentally push math columns back to the sheet
                    clean_save_df = edited_exp.drop(
                        columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 'Display_Total_HKD', 'Display_Total_AUD', 'Display_Person_HKD', 'Display_Person_AUD'], 
                        errors='ignore'
                    )
                    updated_exp = pd.concat([clean_save_df, new_exp], ignore_index=True)
                    conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                    st.cache_data.clear()
                    st.rerun()

        show_conversion = st.toggle(f"Show {target_currency} conversion in Ledger", value=False)

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
                        
                        # --- THE NEW SETTLEMENT BUTTON ---
                        if st.button(f"💸 Settle {user}'s Debt", key=f"settle_{user}"):
                            with st.spinner(f"Calculating {user}'s payments..."):
                                import datetime
                                x_debt = abs(net_aud)
                                new_settlements = []
                                
                                # Find who is owed money and logically "pay" them
                                for cred, cred_amt in balances_aud.items():
                                    if cred != user and cred_amt > 0.01 and x_debt > 0.01:
                                        pay_amt = min(x_debt, cred_amt)
                                        
                                        new_settlements.append({
                                            "Date": datetime.date.today().strftime("%Y-%m-%d"),
                                            "Category": "💡 Other",
                                            "Item": f"🤝 Settlement: {user} paid {cred}",
                                            "Currency": "AUD",
                                            "Cost": pay_amt,
                                            "Paid By": user,
                                            "Split By": cred,
                                            "Settled": False, # Important! Keep it active so it offsets the negative math!
                                            "Remark": "Auto-generated"
                                        })
                                        
                                        x_debt -= pay_amt
                                        balances_aud[cred] -= pay_amt 
                                        
                                if new_settlements:
                                    clean_save_df = edited_exp.drop(
                                        columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 
                                                 'Display_Total_HKD', 'Display_Total_AUD', 'Display_Person_HKD', 'Display_Person_AUD'], 
                                        errors='ignore'
                                    )
                                    updated_exp = pd.concat([clean_save_df, pd.DataFrame(new_settlements)], ignore_index=True)
                                    conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                                    st.success("Debt mathematically neutralized!")
                                    st.cache_data.clear()
                                    st.rerun()
                                    
                    else:
                        st.write("All Settled!")

        else:
            st.success("🎉 All debts are settled!")

    except Exception as e:
         st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
