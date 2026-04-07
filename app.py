import urllib.parse
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import itertools
import plotly.express as px
import google.generativeai as genai
import requests
import time
import json

# ==============================================================================
# --- INITIAL SETUP & CONFIGURATION ---
# ==============================================================================
st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

trip_users = ["Sally🦕", "Suri🐶", "Bobo🍔"]
expense_categories = ["🎟️ Activity", "🍔 Food", "🏠 Stay", "✈️ Flight", "🚗 Transport", "🛍️ Shopping", "💡 Other"]
split_options = ["All"] + trip_users + [f"{u1}, {u2}" for u1, u2 in itertools.combinations(trip_users, 2)]

# Connect to Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("🔑 AI Key missing! Please check your Streamlit Secrets.")
    model = None

# Connect to Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection failed! The real error is: {e}")
    st.stop()

url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=743694833#gid=743694833"

st.title("🇦🇺 Australia Trip Hub 2026")

with st.sidebar:
    st.header("⚙️ App Settings")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.info("Data is cached for 60s to avoid Google's speed limits. Use the button above to sync manually!")

@st.cache_data(ttl=3600)
def get_aud_to_hkd_rate():
    try:
        res = requests.get("https://open.er-api.com/v6/latest/AUD").json()
        return res['rates']['HKD']
    except:
        return 5.15

# ==============================================================================
# --- CREATE THE TABS ---
# ==============================================================================
tab1, tab2 = st.tabs(["🗓️ Planner & Map", "💰 Expenses"])

# ==============================================================================
# --- TAB 1: AI ITINERARY PLANNER ---
# ==============================================================================
with tab1:
    st.subheader("🗺️ AI Smart Planner")
    
    # --- 1. DATA LOADING & CLEANING ---
    try:
        # Using a 10-minute cache (600s) to prevent Google API rate limits!
        df_plan = conn.read(spreadsheet=url, worksheet="Planner", ttl=600)
        
        required_plan_cols = ['Day', 'Time', 'Item', 'Category', 'Area', 'Maps Link', 'Booking Needed', 'Notes']
        for col in required_plan_cols:
            if col not in df_plan.columns:
                if col == 'Booking Needed': df_plan[col] = False
                elif col == 'Day': df_plan[col] = "TBC"
                else: df_plan[col] = ""
                
        df_plan = df_plan[required_plan_cols].dropna(how="all", subset=['Item'])
        df_plan['Booking Needed'] = df_plan['Booking Needed'].fillna(False).astype(bool)
        df_plan['Day'] = df_plan['Day'].replace("", "TBC").fillna("TBC")
        df_plan['Category'] = df_plan['Category'].replace("", "Activity").fillna("Activity")

    except Exception as e:
        st.error(f"Error loading Planner tab: {e}")
        st.stop()

    # --- 2. AI SMART ADD & SCHEDULING TOOLKIT ---
    with st.expander("✨ AI Planning Assistant", expanded=False):
        ai_tab1, ai_tab2 = st.tabs(["➕ Smart Add", "🪄 Suggest Schedule"])
        
        with ai_tab1:
            st.write("**Paste anything here!** (e.g., 'Opera house tour 2pm', a Google Maps link, or 'need to book that cool airbnb in surry hills')")
            raw_input = st.text_area("Raw Details:")
            force_cat = st.selectbox("Category Hint (Optional)", ["Auto-Detect", "Stay", "Flight", "Tour", "Food", "Activity"])
            
            if st.button("🚀 Process & Add to Itinerary", use_container_width=True):
                if raw_input:
                    with st.spinner("AI is analyzing, formatting, and checking booking needs..."):
                        # ==========================================
                        # LLM INTEGRATION POINT:
                        # In a live app, you would send `raw_input` to Gemini here.
                        # Prompt: "Extract: Official Name, Category, Area, Maps Search Link, and Boolean if booking is required. Return strictly as JSON."
                        # ==========================================
                        
                        # --- MOCK AI RESPONSE (Replace with actual genai call) ---
                        import time; time.sleep(1.5) # Simulating AI thinking
                        mock_ai_data = {
                            "Item": f"Cleaned: {raw_input[:15]}...",
                            "Category": force_cat if force_cat != "Auto-Detect" else "Activity",
                            "Area": "Sydney (AI Detected)",
                            "Maps Link": f"https://www.google.com/maps/search/?api=1&query=Sydney",
                            "Booking Needed": True if "book" in raw_input.lower() or "airbnb" in raw_input.lower() or "flight" in raw_input.lower() else False,
                            "Day": "TBC", "Time": "", "Notes": "Auto-added via AI."
                        }
                        
                        # Add to Planner
                        new_plan_row = pd.DataFrame([mock_ai_data])
                        updated_plan = pd.concat([df_plan, new_plan_row], ignore_index=True)
                        conn.update(spreadsheet=url, data=updated_plan, worksheet="Planner")
                        
                        # --- CROSS-TAB SYNC: ADD TO LEDGER IF BOOKING NEEDED ---
                        if mock_ai_data["Booking Needed"]:
                            try:
                                df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=5)
                                new_exp_row = pd.DataFrame([{
                                    "Date": str(datetime.date.today()), "Category": mock_ai_data["Category"], 
                                    "Item": f"Booking Deposit: {mock_ai_data['Item']}", "Currency": "AUD", 
                                    "Cost": 0.0, "Paid By": trip_users[0], "Split By": "All", 
                                    "Remark": "Auto-generated from Planner", "Settled": False
                                }])
                                clean_exp = df_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                                updated_exp = pd.concat([clean_exp, new_exp_row], ignore_index=True)
                                conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                                st.toast("Ledger updated: Pending booking expense added!")
                            except Exception as e:
                                st.error(f"Could not cross-sync to Expenses: {e}")
                        
                        st.success(f"Added {mock_ai_data['Item']}!")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()

        with ai_tab2:
            st.write("Let AI analyze your **TBC** items and suggest how to group them by area and day.")
            if st.button("🧠 Generate Schedule Suggestions", use_container_width=True):
                with st.spinner("AI is calculating distances and optimizing your trip..."):
                    # ==========================================
                    # LLM INTEGRATION POINT:
                    # Send `df_plan.to_dict()` to Gemini here.
                    # Prompt: "Look at these items. Group items in similar 'Areas' onto the same 'Day'. Output a friendly text suggestion, do NOT output code."
                    # ==========================================
                    st.info("""
                    **🤖 AI Suggestions:**
                    * **Day 2:** Move 'Bondi Beach' and 'Icebergs Dining' to Day 2, as they are in the same area.
                    * **Day 3:** You have 'Opera House' (CBD) and 'Taronga Zoo' (North Shore) on the same day. Consider grouping the Zoo with your Manly ferry trip!
                    
                    *(Review these suggestions and edit your items below!)*
                    """)

    st.divider()

    # --- 3. FILTERING & GROUPING UI ---
    st.caption("🔍 View Options")
    vf1, vf2, vf3 = st.columns(3)
    
    unique_days = ["All Days"] + sorted([d for d in df_plan['Day'].unique() if str(d) != "nan" and d])
    unique_areas = ["All Areas"] + sorted([a for a in df_plan['Area'].unique() if str(a) != "nan" and a])
    unique_cats = ["All Categories"] + sorted([c for c in df_plan['Category'].unique() if str(c) != "nan" and c])
    
    filt_day = vf1.selectbox("Filter Day", unique_days)
    filt_area = vf2.selectbox("Filter Area", unique_areas)
    filt_cat = vf3.selectbox("Filter Category", unique_cats)
    
    group_by = st.radio("Group Feed By:", ["None (Chronological)", "Day", "Area", "Category"], horizontal=True)

    # Apply Filters
    view_plan = df_plan.copy()
    if filt_day != "All Days": view_plan = view_plan[view_plan['Day'] == filt_day]
    if filt_area != "All Areas": view_plan = view_plan[view_plan['Area'] == filt_area]
    if filt_cat != "All Categories": view_plan = view_plan[view_plan['Category'] == filt_cat]

    # Session state for planner editing
    if 'plan_edit_idx' not in st.session_state:
        st.session_state.plan_edit_idx = None

    # --- 4. THE STACKED ITINERARY FEED ---
    category_emojis = {"Stay": "🏨", "Flight": "✈️", "Tour": "🚌", "Food": "🍽️", "Activity": "🎟️"}

    if view_plan.empty:
        st.info("No plans match this filter. Use the AI Smart Add above!")
    else:
        # Function to render a single card
        def render_plan_card(idx, row):
            with st.container(border=True):
                # EDIT MODE
                if st.session_state.plan_edit_idx == idx:
                    with st.form(key=f"edit_plan_{idx}"):
                        st.write(f"✏️ **Editing:** {row['Item']}")
                        e_item = st.text_input("Official Name", value=row['Item'])
                        
                        ec1, ec2, ec3 = st.columns(3)
                        e_day = ec1.text_input("Day (e.g., Day 1, TBC)", value=row['Day'])
                        e_time = ec2.text_input("Time", value=row['Time'])
                        e_cat = ec3.selectbox("Category", ["Stay", "Flight", "Tour", "Food", "Activity", "Other"], 
                                              index=["Stay", "Flight", "Tour", "Food", "Activity", "Other"].index(row['Category']) if row['Category'] in ["Stay", "Flight", "Tour", "Food", "Activity", "Other"] else 5)
                        
                        ec4, ec5 = st.columns(2)
                        e_area = ec4.text_input("Area / District", value=row['Area'])
                        e_link = ec5.text_input("Maps Link", value=row['Maps Link'])
                        
                        e_book = st.checkbox("Booking/Tickets Needed?", value=row['Booking Needed'])
                        e_notes = st.text_area("Notes (Meetup spot, check-in times, etc.)", value=row['Notes'])
                        
                        sub1, sub2 = st.columns(2)
                        if sub1.form_submit_button("💾 Save", use_container_width=True):
                            df_plan.loc[idx, 'Item'] = e_item
                            df_plan.loc[idx, 'Day'] = e_day
                            df_plan.loc[idx, 'Time'] = e_time
                            df_plan.loc[idx, 'Category'] = e_cat
                            df_plan.loc[idx, 'Area'] = e_area
                            df_plan.loc[idx, 'Maps Link'] = e_link
                            df_plan.loc[idx, 'Booking Needed'] = e_book
                            df_plan.loc[idx, 'Notes'] = e_notes
                            
                            conn.update(spreadsheet=url, data=df_plan, worksheet="Planner")
                            st.session_state.plan_edit_idx = None
                            st.cache_data.clear()
                            import time; time.sleep(1)
                            st.rerun()
                        if sub2.form_submit_button("❌ Cancel", use_container_width=True):
                            st.session_state.plan_edit_idx = None
                            st.rerun()
                
                # NORMAL VIEW MODE
                else:
                    icon = category_emojis.get(row['Category'], "📍")
                    book_badge = "🚨 **Needs Booking**" if row['Booking Needed'] else ""
                    
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        if row['Maps Link']:
                            st.markdown(f"#### [{icon} {row['Item']}]({row['Maps Link']})")
                        else:
                            st.markdown(f"#### {icon} {row['Item']}")
                        
                        st.write(f"**{row['Day']}** | 🕒 {row['Time']} | 🏙️ {row['Area']}")
                        if book_badge: st.warning(book_badge)
                        if row['Notes']: st.caption(f"📝 {row['Notes']}")
                    
                    with c2:
                        if st.button("✏️", key=f"p_edit_{idx}"):
                            st.session_state.plan_edit_idx = idx
                            st.rerun()
                        if st.button("🗑️", key=f"p_del_{idx}"):
                            clean_df = df_plan.drop(index=idx)
                            conn.update(spreadsheet=url, data=clean_df, worksheet="Planner")
                            st.toast(f"Deleted {row['Item']}")
                            st.cache_data.clear()
                            import time; time.sleep(1)
                            st.rerun()

        # Grouping Logic Display
        if group_by == "None (Chronological)":
            for idx, row in view_plan.iterrows():
                render_plan_card(idx, row)
        else:
            grouped = view_plan.groupby(group_by)
            for group_name, group_df in grouped:
                st.write(f"### {group_name}")
                for idx, row in group_df.iterrows():
                    render_plan_card(idx, row)

# ==============================================================================
# --- TAB 2: EXPENSES & DEBTS ---
# ==============================================================================
with tab2:
    st.subheader("💸 Expense Tracker")
    aud_to_hkd = get_aud_to_hkd_rate()

    col_rate, col_curr = st.columns([1, 1])
    with col_rate:
        st.caption(f"💱 **Live Exchange Rate:** 1 AUD = {aud_to_hkd:.2f} HKD")
    with col_curr:
        target_currency = st.radio("Display App In:", ["HKD", "AUD"], horizontal=True)

    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=60)
        required_exp_cols = ['Date', 'Category', 'Item', 'Currency', 'Cost', 'Paid By', 'Split By', 'Remark', 'Settled']

        for col in required_exp_cols:
            if col not in df_exp.columns:
                if col == 'Currency': df_exp[col] = "AUD"
                elif col == 'Settled': df_exp[col] = False
                elif col == 'Cost': df_exp[col] = 0.0
                elif col == 'Split By': df_exp[col] = "All"
                else: df_exp[col] = None

        df_exp = df_exp[required_exp_cols]
        df_exp = df_exp.dropna(how="all", subset=['Item'])

        # --- DATE FIX ---
        df_exp['Date'] = pd.to_datetime(df_exp['Date'], format='mixed', errors='coerce')
        df_exp['Date'] = df_exp['Date'].fillna(pd.to_datetime('today'))
        df_exp['Date'] = df_exp['Date'].dt.date
        
        df_exp['Settled'] = df_exp['Settled'].fillna(False).astype(bool)
        df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)
        df_exp['Currency'] = df_exp['Currency'].replace("", "AUD") 
        df_exp['Split By'] = df_exp['Split By'].replace("", "All")

        # --- BACKGROUND MATH ---
        def get_hkd(row): return row['Cost'] * aud_to_hkd if row['Currency'] == 'AUD' else row['Cost']
        def get_aud(row): return row['Cost'] / aud_to_hkd if row['Currency'] == 'HKD' else row['Cost']
        def get_split_count(split_str):
            s = str(split_str).strip()
            if s == 'All': return len(trip_users)
            involved = [u.strip() for u in s.split(',') if u.strip() in trip_users]
            return len(involved) if involved else len(trip_users)

        df_exp['Cost_HKD'] = df_exp.apply(get_hkd, axis=1)
        df_exp['Cost_AUD'] = df_exp.apply(get_aud, axis=1)
        df_exp['Split_Count'] = df_exp['Split By'].apply(get_split_count)
        calc_col = 'Cost_HKD' if target_currency == "HKD" else 'Cost_AUD'

        # --- 2A: TRIP OVERVIEW (TOGGLE BLOCK) ---
        if st.toggle("📊 Show Trip Overview Analytics", value=False):
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
                cat = row['Category'] if pd.notna(row['Category']) else "💡 Other" 

                if cost > 0:
                    total_cat_shares[cat] += cost
                    split_str = str(row['Split By']).strip()
                    involved = trip_users if split_str == 'All' else [u.strip() for u in split_str.split(',') if u.strip() in trip_users]
                    if not involved: involved = trip_users

                    split_amount = cost / len(involved)
                    for person in involved:
                        user_shares[person] += split_amount
                        user_cat_shares[person][cat] += split_amount

            share_cols = st.columns(len(trip_users))
            for i, user in enumerate(trip_users):
                with share_cols[i]:
                    st.info(f"**{user}**\n\n${user_shares[user]:,.2f} {target_currency}")

        st.divider()

        # --- 2B: THE NEW STACKED LEDGER & ENTRY FORM ---
        st.write("### 📝 Ledger Feed")
        
        # 1. NEW ENTRY FORM
        with st.expander("➕ Add New Expense", expanded=False):
            with st.form("new_entry_form"):
                f_date = st.date_input("Date", value=datetime.date.today())
                f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Mamak")
                f_cat = st.selectbox("Category", expense_categories)
                
                col_c1, col_c2 = st.columns(2)
                f_cost = col_c1.number_input("Cost", min_value=0.0, format="%.2f")
                f_curr = col_c2.selectbox("Currency", ["AUD", "HKD"])
                
                col_p1, col_p2 = st.columns(2)
                f_payer = col_p1.selectbox("Paid By", trip_users)
                f_split = col_p2.selectbox("Split By", split_options)
                
                if st.form_submit_button("💾 Save to Ledger", use_container_width=True):
                    if f_item and f_cost > 0:
                        new_row = pd.DataFrame([{
                            "Date": f_date.strftime("%Y-%m-%d"), 
                            "Category": f_cat, "Item": f_item, 
                            "Currency": f_curr, "Cost": f_cost, "Paid By": f_payer, 
                            "Split By": f_split, "Remark": "", "Settled": False
                        }])
                        clean_df = df_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                        updated_exp = pd.concat([clean_df, new_row], ignore_index=True)
                        conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                        st.success("✅ Added successfully!")
                        st.cache_data.clear()
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Please enter an item name and a cost greater than 0.")

        # 2. QUERY FILTERS & SORTING
        st.caption("🔍 Sort & Filter")
        
        filt_c1, filt_c2 = st.columns(2)
        filter_user = filt_c1.selectbox("Paid By", ["Everyone"] + trip_users)
        filter_cat = filt_c2.selectbox("Category", ["All Categories"] + expense_categories)
        
        sort_c1, sort_c2 = st.columns(2)
        sort_by = sort_c1.selectbox("Sort By", ["Latest Date", "Oldest Date", "Highest Cost", "Lowest Cost"])
        show_settled = sort_c2.toggle("👀 Show Settled Expenses", value=False)

        # Apply Filters
        view_df = df_exp.copy()
        if not show_settled: view_df = view_df[view_df['Settled'] == False]
        if filter_user != "Everyone": view_df = view_df[view_df['Paid By'] == filter_user]
        if filter_cat != "All Categories": view_df = view_df[view_df['Category'] == filter_cat]

        # Apply Sorting
        if sort_by == "Latest Date": view_df = view_df.sort_values('Date', ascending=False)
        elif sort_by == "Oldest Date": view_df = view_df.sort_values('Date', ascending=True)
        elif sort_by == "Highest Cost": view_df = view_df.sort_values('Cost', ascending=False)
        elif sort_by == "Lowest Cost": view_df = view_df.sort_values('Cost', ascending=True)

        # Session state for editing
        if 'edit_idx' not in st.session_state:
            st.session_state.edit_idx = None

        # 3. STACKED FEED VIEW
        if view_df.empty:
            st.info("No expenses found matching these filters.")
        else:
            for idx, row in view_df.iterrows():
                with st.container(border=True):
                    
                    # --- EDIT MODE ---
                    if st.session_state.edit_idx == idx:
                        st.write(f"✏️ **Editing:** {row['Item']}")
                        with st.form(key=f"edit_form_{idx}"):
                            
                            f_c1, f_c2 = st.columns(2)
                            e_date = f_c1.date_input("Date", value=row['Date'], key=f"e_date_{idx}")
                            e_cat = f_c2.selectbox("Category", expense_categories, index=expense_categories.index(row['Category']) if row['Category'] in expense_categories else 0, key=f"e_cat_{idx}")
                            
                            e_item = st.text_input("Item", value=row['Item'], key=f"e_item_{idx}")
                            
                            c1, c2 = st.columns(2)
                            e_cost = c1.number_input("Cost", value=float(row['Cost']), min_value=0.0, key=f"e_cost_{idx}")
                            e_curr = c2.selectbox("Currency", ["AUD", "HKD"], index=0 if row['Currency'] == "AUD" else 1, key=f"e_curr_{idx}")
                            
                            c3, c4 = st.columns(2)
                            e_payer = c3.selectbox("Paid By", trip_users, index=trip_users.index(row['Paid By']) if row['Paid By'] in trip_users else 0, key=f"e_payer_{idx}")
                            e_split = c4.selectbox("Split By", split_options, index=split_options.index(row['Split By']) if row['Split By'] in split_options else 0, key=f"e_split_{idx}")
                            
                            col_sub1, col_sub2 = st.columns(2)
                            if col_sub1.form_submit_button("💾 Save Changes", use_container_width=True):
                                with st.spinner("Syncing to Google Sheets..."):
                                    # Update exactly this row in the master dataframe
                                    df_exp.loc[idx, 'Date'] = e_date
                                    df_exp.loc[idx, 'Category'] = e_cat
                                    df_exp.loc[idx, 'Item'] = e_item
                                    df_exp.loc[idx, 'Cost'] = e_cost
                                    df_exp.loc[idx, 'Currency'] = e_curr
                                    df_exp.loc[idx, 'Paid By'] = e_payer
                                    df_exp.loc[idx, 'Split By'] = e_split
                                    
                                    # Drop temp columns and force Date to string before saving
                                    clean_save_df = df_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                                    clean_save_df['Date'] = clean_save_df['Date'].astype(str)
                                    
                                    conn.update(spreadsheet=url, data=clean_save_df, worksheet="Expenses")
                                    st.session_state.edit_idx = None
                                    st.cache_data.clear()
                                    import time
                                    time.sleep(2)
                                    st.rerun()
                                
                            if col_sub2.form_submit_button("❌ Cancel", use_container_width=True):
                                st.session_state.edit_idx = None
                                st.rerun()

                    # --- NORMAL VIEW MODE ---
                    else:
                        if row['Currency'] == 'AUD':
                            hkd_equiv = row['Cost'] * aud_to_hkd
                            cost_display = f"${row['Cost']:,.2f} AUD (≈ ${hkd_equiv:,.2f} HKD)"
                        else:
                            cost_display = f"${row['Cost']:,.2f} HKD"

                        status_icon = "✅ Settled" if row['Settled'] else "⏳ Pending"
                        
                        st.markdown(f"**{row['Item']}** | {status_icon}")
                        st.write(f"{row['Category']} • {row['Date']} • **{cost_display}**")
                        
                        c1, c2, c3 = st.columns([3, 3, 1])
                        c1.caption(f"🤑 Paid by: **{row['Paid By']}**")
                        c2.caption(f"🍕 Split: **{row['Split By']}**")
                        
                        # Action Buttons Stacked
                        with c3:
                            if st.button("✏️", key=f"edit_btn_{idx}", help="Edit record"):
                                st.session_state.edit_idx = idx
                                st.rerun()
                            if st.button("🗑️", key=f"del_btn_{idx}", help="Delete record"):
                                clean_df = df_exp.drop(index=idx).drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                                clean_df['Date'] = clean_df['Date'].astype(str)
                                conn.update(spreadsheet=url, data=clean_df, worksheet="Expenses")
                                st.toast(f"Deleted {row['Item']}")
                                st.cache_data.clear()
                                import time
                                time.sleep(2)
                                st.rerun()

        # --- 2C: SMART SETTLEMENT ENGINE ---
        st.divider()
        st.subheader("⚖️ Unified Net Balances & Settlements")

        active_debts = df_exp[df_exp['Settled'] == False].copy()

        if not active_debts.empty:
            balances_aud = {user: 0.0 for user in trip_users}

            for idx, row in active_debts.iterrows():
                cost_in_aud = float(row['Cost']) / aud_to_hkd if row['Currency'] == 'HKD' else float(row['Cost'])
                payer = str(row['Paid By']).strip()
                split_str = str(row['Split By']).strip()

                if cost_in_aud > 0 and payer in balances_aud:
                    involved = trip_users if split_str == 'All' else [u.strip() for u in split_str.split(',') if u.strip() in trip_users]
                    if not involved: involved = trip_users
                    
                    split_amount = cost_in_aud / len(involved)
                    balances_aud[payer] += cost_in_aud
                    for person in involved:
                        balances_aud[person] -= split_amount

            # Display Individual Net Balances
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
                        st.info("Settled Up!")

            # --- CALCULATE WHO PAYS WHOM ---
            st.write("#### 🎯 Smart Transfer Guide")        
            st.caption("Here is exactly who needs to pay whom to settle all debts:")
            
            creditors = {user: amt for user, amt in balances_aud.items() if amt > 0.01}
            debtors = {user: -amt for user, amt in balances_aud.items() if amt < -0.01}
            
            transfers = []
            for debtor, debt_amt in debtors.items():
                for creditor, credit_amt in list(creditors.items()):
                    if debt_amt <= 0.01: break
                    if credit_amt <= 0.01: continue
                    
                    settle_amount = min(debt_amt, credit_amt)
                    transfers.append((debtor, creditor, settle_amount))
                    
                    # Update amounts
                    debt_amt -= settle_amount
                    creditors[creditor] -= settle_amount
            
            if transfers:
                for sender, receiver, amt in transfers:
                    amt_hkd = amt * aud_to_hkd
                    st.warning(f"💸 **{sender}** needs to pay **{receiver}**: ${amt:.2f} AUD *(≈ ${amt_hkd:.2f} HKD)*")
            else:
                st.success("Everyone is totally settled up!")

            # Quick Settle All Button
            if st.button("✅ Mark ALL Active Debts as Settled", use_container_width=True):
                with st.spinner("Updating records..."):
                    df_exp['Settled'] = True
                    clean_save_df = df_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                    clean_save_df['Date'] = clean_save_df['Date'].astype(str)
                    conn.update(spreadsheet=url, data=clean_save_df, worksheet="Expenses")
                    st.success("All debts settled!")
                    st.cache_data.clear()
                    import time
                    time.sleep(2)
                    st.rerun()

    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
