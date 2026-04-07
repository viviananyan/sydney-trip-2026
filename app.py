import urllib.parse
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import itertools
import plotly.express as px
import google.generativeai as genai

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
        import requests
        res = requests.get("https://open.er-api.com/v6/latest/AUD").json()
        return res['rates']['HKD']
    except:
        return 5.15

# ==============================================================================
# --- CREATE THE TABS ---
# ==============================================================================
tab1, tab2 = st.tabs(["🗓️ Planner & Map", "💰 Expenses"])

# ==============================================================================
# --- TAB 1: PLANNER & MAP ---
# ==============================================================================
with tab1:
    df_plan = conn.read(ttl=0)

    # Ensure columns exist
    for col in ['name', 'area', 'status', 'day']:
        if col not in df_plan.columns:
            df_plan[col] = ""

    def ask_gemini(user_input):
        if not model: return ["Error", "Error", "TBD"]
        prompt = f"""
        You are a Sydney travel expert. Extract info from this note: "{user_input}"
        Return ONLY a comma-separated list: Polished Name, Specific Sydney Area, Day Number (or 'TBD')
        Example: "coffee at gertrude and alice on day 2" -> Gertrude & Alice, Bondi, 2
        """
        response = model.generate_content(prompt)
        return [item.strip() for item in response.text.split(',')]

    # --- AI QUICK-ADD BLOCK ---
    with st.container(border=True):
        st.subheader("🪄 AI Smart Add")
        user_note = st.text_input("Describe your plan...", placeholder="e.g. Opera House on Day 1")
        
        if st.button("Add to Itinerary") and user_note:
            with st.spinner("Gemini is polishing your plan..."):
                name, area, day = ask_gemini(user_note)
                status = "Scheduled" if day.lower() != 'tbd' else "TBD"
                
                new_data = pd.DataFrame([{"name": name, "area": area, "status": status, "day": day}])
                updated_df = pd.concat([df_plan, new_data], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"Added {name} to {area}!")
                st.rerun()

    # --- THE GROUPED VIEW ---
    col1, col2 = st.columns(2)
    with col1:
        st.header("📍 TBD List (By Area)")
        tbd_df = df_plan[df_plan['status'] == 'TBD']
        if tbd_df.empty:
            st.write("No unscheduled plans.")
        else:
            for area, group in tbd_df.groupby('area'):
                with st.expander(f"🏘️ {area}", expanded=True):
                    for idx, row in group.iterrows():
                        st.write(f"• {row['name']}")

    with col2:
        st.header("🗓️ Itinerary (By Day)")
        sched_df = df_plan[df_plan['status'] == 'Scheduled']
        if sched_df.empty:
            st.info("Nothing scheduled yet.")
        else:
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

        # Fix Date formatting to ensure it doesn't break
        df_exp['Date'] = pd.to_datetime(df_exp['Date'], errors='coerce').dt.date
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

        st.divider()

        # --- 2B: THE CLEAN LEDGER ---
        st.write("### 📝 Quick Ledger")
        st.caption("Scroll right to edit columns. Empty row at the bottom adds new expenses.")
        
        # Thinner, mobile-friendly data editor
        edited_exp = st.data_editor(
            df_exp,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", required=True),
                "Category": st.column_config.SelectboxColumn("Cat", options=expense_categories, width="small"),
                "Item": st.column_config.TextColumn("Item", required=True),
                "Currency": st.column_config.SelectboxColumn("Cur", options=["AUD", "HKD"], width="small"),
                "Cost": st.column_config.NumberColumn("Cost", required=True, format="%.2f"),
                "Paid By": st.column_config.SelectboxColumn("Paid", options=trip_users, width="small"),
                "Split By": st.column_config.SelectboxColumn("Split", options=split_options, width="small"),
                "Settled": st.column_config.CheckboxColumn("Settled?"),
                "Remark": None, # Hiding to save space, but preserved in data
                "Cost_HKD": None, "Cost_AUD": None, "Split_Count": None
            }
        )

        if st.button("💾 Save Ledger Changes", use_container_width=True):
            # FIX: Safely parse dates, filling blanks with today's date so the app doesn't crash
            edited_exp['Date'] = pd.to_datetime(edited_exp['Date'], errors='coerce').fillna(datetime.date.today()).dt.date
            
            clean_edited_exp = edited_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
            conn.update(spreadsheet=url, data=clean_edited_exp, worksheet="Expenses")
            st.success("Ledger saved!")
            st.cache_data.clear()
            st.rerun()

        # --- 2C: SMART SETTLEMENT ENGINE ---
        st.divider()
        st.subheader("⚖️ Unified Net Balances")

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
                        
                        # NEW SETTLEMENT LOGIC: Just marks the relevant rows as "Settled"
                        if st.button(f"💸 Settle {user}'s Debt", key=f"settle_{user}"):
                            with st.spinner(f"Marking {user}'s debts as settled..."):
                                
                                def involves_user(r):
                                    if r['Paid By'] == user: return True
                                    s = str(r['Split By'])
                                    return True if s == 'All' else (user in s)

                                mask = df_exp['Settled'] == False
                                affected = df_exp[mask].apply(involves_user, axis=1)
                                
                                # Mark them settled in the dataframe directly
                                df_exp.loc[mask & affected, 'Settled'] = True
                                
                                clean_save_df = df_exp.drop(columns=['Cost_HKD', 'Cost_AUD', 'Split_Count'], errors='ignore')
                                conn.update(spreadsheet=url, data=clean_save_df, worksheet="Expenses")
                                st.cache_data.clear()
                                st.rerun()

    except Exception as e:
        st.error(f"Robot can't read the 'Expenses' tab. Error: {e}")
