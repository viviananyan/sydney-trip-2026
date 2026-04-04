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
import google.generativeai as genai

@st.cache_data(ttl=3600)
def get_aud_to_hkd_rate():
    try:
        url = "https://open.er-api.com/v6/latest/AUD"
        data = requests.get(url).json()
        return data['rates']['HKD']
    except:
        return 5.15

# --- CONFIGURATION ---
trip_users = ["Sally🦕", "Suri🐶", "Bobo🍔"]
expense_categories = ["🎟️ Activity", "🍔 Food", "🏠 Stay", "✈️ Flight", "🚗 Transport", "🛍️ Shopping", "💡 Other"]
# Generates combinations for splits automatically
split_options = ["All"] + trip_users + [f"{u1}, {u2}" for u1, u2 in itertools.combinations(trip_users, 2)]

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

# --- 1. CONNECTION SETUP ---
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

@st.cache_data(show_spinner=False)
def get_coordinates(location_name):
    try:
        geolocator = ArcGIS()
        location = geolocator.geocode(f"{location_name}, Australia", timeout=10)
        if location:
            return [location.latitude, location.longitude]
        return None
    except Exception as e:
        return None

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("🔑 AI Key missing! Please check your Streamlit Secrets.")
    model = None

# --- 2. CREATE THE TABS ---
tab1, tab2 = st.tabs(["🗓️ Planner & Map", "💰 Expenses"])

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import google.generativeai as genai

# --- INITIAL SETUP ---
st.set_page_config(page_title="Sydney Trip 2026", layout="wide")

# Connect to Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0)

# Ensure columns exist
for col in ['name', 'area', 'status', 'day']:
    if col not in df.columns:
        df[col] = ""

# --- THE AI BRAIN ---
def ask_gemini(user_input):
    prompt = f"""
    You are a Sydney travel expert. Extract info from this note: "{user_input}"
    Return ONLY a comma-separated list: Polished Name, Specific Sydney Area, Day Number (or 'TBD')
    Example: "coffee at gertrude and alice on day 2" -> Gertrude & Alice, Bondi, 2
    Example: "taronga zoo" -> Taronga Zoo, Mosman, TBD
    """
    response = model.generate_content(prompt)
    # Splits the response "Name, Area, Day" into a list
    return [item.strip() for item in response.text.split(',')]

st.title("🇦🇺 Sydney Trip Intelligence")

# --- 1. AI QUICK-ADD BLOCK ---
with st.container(border=True):
    st.subheader("🪄 AI Smart Add")
    user_note = st.text_input("Describe your plan...", placeholder="e.g. Opera House on Day 1")
    
    if st.button("Add to Itinerary") and user_note:
        with st.spinner("Gemini is polishing your plan..."):
            name, area, day = ask_gemini(user_note)
            
            # Logic: If day is a number, it's Scheduled. If it's TBD, it goes to TBD.
            status = "Scheduled" if day.lower() != 'tbd' else "TBD"
            
            new_data = pd.DataFrame([{"name": name, "area": area, "status": status, "day": day}])
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(data=updated_df)
            st.success(f"Added {name} to {area}!")
            st.rerun()

# --- 2. THE GROUPED VIEW ---
col1, col2 = st.columns(2)

with col1:
    st.header("📍 TBD List (By Area)")
    tbd_df = df[df['status'] == 'TBD']
    if tbd_df.empty:
        st.write("No unscheduled plans.")
    else:
        # This groups the list by the "area" column automatically
        for area, group in tbd_df.groupby('area'):
            with st.expander(f"🏘️ {area}", expanded=True):
                for idx, row in group.iterrows():
                    st.write(f"• {row['name']}")

with col2:
    st.header("🗓️ Itinerary (By Day)")
    sched_df = df[df['status'] == 'Scheduled']
    if sched_df.empty:
        st.info("Nothing scheduled yet.")
    else:
        # Group by Day first, then by Area inside the day
        for day, day_group in sched_df.sort_values('day').groupby('day'):
            st.markdown(f"### 🗓️ Day {day}")
            for area, area_group in day_group.groupby('area'):
                st.caption(f"Neighborhood: {area}")
                for idx, row in area_group.iterrows():
                    st.info(f"**{row['name']}**")
# ==============================================================================
# --- TAB 2: EXPENSES & DEBTS ---
# ==============================================================================
with tab2:
    st.subheader("💸 Expense Tracker")
    aud_to_hkd = get_aud_to_hkd_rate()

    col1, col2 = st.columns([1, 1])
    with col1:
        st.caption(f"💱 **Live Exchange Rate:** 1 AUD = {aud_to_hkd:.2f} HKD")
    with col2:
        target_currency = st.radio("Display Trip Overview in:", ["HKD", "AUD"], horizontal=True)

    try:
        df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=60)
        # Note: We keep 'Settled' in the required columns for background math, but we won't display it to the user.
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

        df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
        df_exp['Settled'] = df_exp['Settled'].fillna(False).astype(bool)
        df_exp['Cost'] = pd.to_numeric(df_exp['Cost'], errors='coerce').fillna(0.0)
        df_exp['Currency'] = df_exp['Currency'].replace("", "AUD") 
        df_exp['Split By'] = df_exp['Split By'].replace("", "All")

        # --- 1. BACKGROUND MATH ---
        def get_hkd(row):
            return row['Cost'] * aud_to_hkd if row['Currency'] == 'AUD' else row['Cost']
        def get_aud(row):
            return row['Cost'] / aud_to_hkd if row['Currency'] == 'HKD' else row['Cost']
        def get_split_count(split_str):
            s = str(split_str).strip()
            if s == 'All': return len(trip_users)
            involved = [u.strip() for u in s.split(',') if u.strip() in trip_users]
            return len(involved) if involved else len(trip_users)

        df_exp['Cost_HKD'] = df_exp.apply(get_hkd, axis=1)
        df_exp['Cost_AUD'] = df_exp.apply(get_aud, axis=1)
        df_exp['Split_Count'] = df_exp['Split By'].apply(get_split_count)
        df_exp['Per_Person_Cost'] = df_exp['Cost'] / df_exp['Split_Count']
        df_exp['Per_Person_HKD'] = df_exp['Cost_HKD'] / df_exp['Split_Count']
        df_exp['Per_Person_AUD'] = df_exp['Cost_AUD'] / df_exp['Split_Count']

        calc_col = 'Cost_HKD' if target_currency == "HKD" else 'Cost_AUD'

        df_exp['Display_Total_HKD'] = df_exp.apply(lambda r: r['Cost_HKD'] if r['Currency'] == 'AUD' else None, axis=1)
        df_exp['Display_Total_AUD'] = df_exp.apply(lambda r: r['Cost_AUD'] if r['Currency'] == 'HKD' else None, axis=1)

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

        # --- THE MOBILE FORM ---
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
                        "Split By": e_split, "Remark": "", "Settled": False
                    }])
                    # Drop the math columns so we only save raw data to sheets
                    clean_save_df = df_exp.drop(
                        columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 'Display_Total_HKD', 'Display_Total_AUD'], 
                        errors='ignore'
                    )
                    updated_exp = pd.concat([clean_save_df, new_exp], ignore_index=True)
                    conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                    st.cache_data.clear()
                    st.rerun()

        # --- THE EDITOR ---
        st.caption("Edit existing rows below. Save when done!")
        edited_exp = st.data_editor(
            df_exp,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", required=True),
                "Category": st.column_config.SelectboxColumn("Category", options=expense_categories, required=True),
                "Item": st.column_config.TextColumn("Item", required=True),
                "Currency": st.column_config.SelectboxColumn("Curr", options=["AUD", "HKD"], required=True),
                "Cost": st.column_config.NumberColumn("Cost", required=True, format="%.2f"),
                "Paid By": st.column_config.SelectboxColumn("Paid By", options=trip_users, required=True),
                "Split By": st.column_config.SelectboxColumn("Split", options=split_options, required=True),
                "Settled": None, # Completely hidden from the user UI!
                "Display_Total_HKD": st.column_config.NumberColumn("(HKD Equivalent)", disabled=True, format="$%.2f"),
                "Display_Total_AUD": st.column_config.NumberColumn("(AUD Equivalent)", disabled=True, format="$%.2f"),
                "Cost_HKD": None, "Cost_AUD": None, "Split_Count": None, "Per_Person_Cost": None, "Per_Person_HKD": None, "Per_Person_AUD": None
            }
        )

        if st.button("💾 Save Ledger Changes", use_container_width=True):
            # Strip out math columns before saving
            clean_edited_exp = edited_exp.drop(
                columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 'Display_Total_HKD', 'Display_Total_AUD'], 
                errors='ignore'
            )
            conn.update(spreadsheet=url, data=clean_edited_exp, worksheet="Expenses")
            st.success("Ledger saved!")
            st.cache_data.clear()
            st.rerun()

        # --- 2C: SMART SETTLEMENT ENGINE ---
        st.divider()
        st.subheader("⚖️ Unified Net Balances")
        st.write("Settle up in whichever currency you prefer! (Green = You are owed money / Red = You owe money)")

        # We rely on the un-edited df_exp to calculate debts safely
        active_debts = df_exp[df_exp['Settled'] == False].copy()

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
                        
                        # --- THE NEW SETTLEMENT BUTTON (COMPLETED!) ---
                        if st.button(f"💸 Settle {user}'s Debt", key=f"settle_{user}"):
                            with st.spinner(f"Calculating {user}'s payments..."):
                                import datetime
                                x_debt = abs(net_aud)
                                new_settlements = []
                                
                                for cred, cred_amt in balances_aud.items():
                                    if cred != user and cred_amt > 0.01 and x_debt > 0.01:
                                        pay_amt = min(x_debt, cred_amt)
                                        
                                        new_settlements.append({
                                            "Date": datetime.date.today(),
                                            "Category": "💡 Other",
                                            "Item": f"🤝 Settlement: {user} paid {cred}",
                                            "Currency": "AUD",
                                            "Cost": pay_amt,
                                            "Paid By": user,
                                            "Split By": cred,
                                            "Settled": False, 
                                            "Remark": "Auto-generated"
                                        })
                                        
                                        x_debt -= pay_amt
                                        balances_aud[cred] -= pay_amt 
                                        
                                if new_settlements:
                                    clean_save_df = df_exp.drop(
                                        columns=['Cost_HKD', 'Cost_AUD', 'Per_Person_Cost', 'Per_Person_HKD', 'Per_Person_AUD', 'Split_Count', 'Display_Total_HKD', 'Display_Total_AUD'], 
                                        errors='ignore'
                                    )
                                    updated_exp = pd.concat([clean_save_df, pd.DataFrame(new_settlements)], ignore_index=True)
                                    conn.update(spreadsheet=url, data=updated_exp, worksheet="Expenses")
                                    st.cache_data.clear()
                                    st.rerun()

    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
