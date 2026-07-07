import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import time
import plotly.express as px

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Australia 2026 Expense Tracker", page_icon="💰", layout="centered")
st.title("💰 Australia 2026 Expense Tracker")

if "editing_row" not in st.session_state:
    st.session_state.editing_row = None

# --- 2. GOOGLE SHEETS CONNECTION & CONSTANTS ---
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit#gid=743694833"
conn = st.connection("gsheets", type=GSheetsConnection)

trip_users = ["Suri🐶", "Bobo🍔", "Sally🦕"] 

base_categories = [
    "🍔 Food", "🚌 Transport", "🛍️ Shopping", 
    "🎟️ Entertainment", "🏨 Stay", "✈️ Flights", "📦 Other"
]

def safe_index(lst, item):
    return lst.index(item) if item in lst else 0

# --- 3. DATA LOADING & SANITIZATION ---
try:
    df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=5)
    
    required_cols = ["Date", "Category", "Item", "Currency", "Cost", "Paid By", "Split By", "Remark", "Settled"]
    for col in required_cols:
        if col not in df_exp.columns:
            df_exp[col] = False if col == "Settled" else ""
            
    df_exp = df_exp[required_cols].dropna(how="all", subset=["Item"])
    df_exp["Settled"] = df_exp["Settled"].fillna(False).astype(bool)
    df_exp["Cost"] = pd.to_numeric(df_exp["Cost"], errors="coerce").fillna(0.0)
    
    df_exp["Remark"] = df_exp["Remark"].fillna("").astype(str)
    df_exp["Remark"] = df_exp["Remark"].replace({"nan": "", "None": "", "NaN": ""})

    # 🔴 THE FIX: Standardize all messy Google Sheets dates into strict YYYY-MM-DD formats
    # This ensures alphabetical string sorting perfectly matches chronological sorting!
    df_exp["Date"] = pd.to_datetime(df_exp["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    existing_custom_cats = [c for c in df_exp["Category"].dropna().unique() if c and c not in base_categories]
    all_categories_list = base_categories + existing_custom_cats
    dropdown_options = all_categories_list + ["➕ Add Custom..."]

except Exception as e:
    st.error(f"Error loading Expenses tab: {e}")
    st.stop()

# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    with st.form("australia_tracker_form_v9", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        
        f_cat_selection = st.selectbox("Category", dropdown_options)
        if f_cat_selection == "➕ Add Custom...":
            f_cat = st.text_input("Type Custom Category", placeholder="e.g., 🏄‍♂️ Surfing")
        else:
            f_cat = f_cat_selection
            
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        
        f_paid = st.selectbox("Paid By", trip_users)
        f_split = st.selectbox("Split With", ["All"] + trip_users)
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            if f_item and f_cost > 0 and f_cat:
                new_row = pd.DataFrame([{
                    "Date": str(f_date), "Category": f_cat, "Item": f_item,
                    "Currency": f_curr, "Cost": f_cost, "Paid By": f_paid,
                    "Split By": f_split, "Remark": f_remark, "Settled": False
                }])
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                st.success(f"Added {f_item}!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please ensure the item, amount, and category are filled out.")

st.divider()

# --- 5. GLOBAL CURRENCY CONFIGURATION ---
st.sidebar.header("💱 Currency Settings")
display_currency = st.sidebar.radio("View & Settle Expenses In:", ["HKD", "AUD"], horizontal=True)

ex_rate = st.sidebar.number_input(
    "Set Conversion Rate (1 AUD = ? HKD)", 
    min_value=1.0, value=5.42, step=0.01, 
    key="unique_sys_exchange_rate_input"
)

def convert_cost(row):
    if display_currency == "HKD":
        return row["Cost"] * ex_rate if row["Currency"] == "AUD" else row["Cost"]
    else:
        return row["Cost"] / ex_rate if row["Currency"] == "HKD" else row["Cost"]

df_exp["Converted_Cost"] = df_exp.apply(convert_cost, axis=1)

# --- 6. SECTION: ACTIVE LEDGER (WITH EDIT CAPABILITY) ---
st.subheader("📊 Active Ledger")

with st.expander("🔍 Search & Filter Tools", expanded=False):
    s_query = st.text_input("Search by Item Name", placeholder="Type keywords...")
    f1, f2 = st.columns(2)
    s_payer = f1.multiselect("Filter by Payer", options=trip_users, default=[])
    
    s_cat = f2.multiselect("Filter by Category", options=all_categories_list, default=[])
    s_sort = st.selectbox("Sort Order", ["Date (Newest First)", "Date (Oldest First)", "Cost (Highest First)", "Cost (Lowest First)"])

show_settled = st.checkbox("Show Settled Expenses", value=False)
view_df = df_exp[df_exp["Settled"] == show_settled].copy()

if s_query: view_df = view_df[view_df["Item"].str.contains(s_query, case=False, na=False)]
if s_payer: view_df = view_df[view_df["Paid By"].isin(s_payer)]
if s_cat: view_df = view_df[view_df["Category"].isin(s_cat)]

if s_sort == "Date (Newest First)": view_df = view_df.sort_values(by="Date", ascending=False)
elif s_sort == "Date (Oldest First)": view_df = view_df.sort_values(by="Date", ascending=True)
elif s_sort == "Cost (Highest First)": view_df = view_df.sort_values(by="Converted_Cost", ascending=False)
elif s_sort == "Cost (Lowest First)": view_df = view_df.sort_values(by="Converted_Cost", ascending=True)

if view_df.empty:
    st.info("No expenses found matching these criteria.")
else:
    for idx, row in view_df.iterrows():
        # --- EDIT MODE ---
        if st.session_state.editing_row == idx:
            with st.container(border=True):
                st.write(f"✏️ **Editing:** {row['Item']}")
                with st.form(key=f"edit_form_{idx}"):
                    try:
                        e_date = pd.to_datetime(row['Date']).date()
                    except:
                        e_date = datetime.date.today()
                        
                    e_date_input = st.date_input("Date", e_date)
                    
                    e_cat_selection = st.selectbox("Category", dropdown_options, index=safe_index(dropdown_options, row['Category']))
                    if e_cat_selection == "➕ Add Custom...":
                        e_cat = st.text_input("Type Custom Category", placeholder="e.g., 🏄‍♂️ Surfing")
                    else:
                        e_cat = e_cat_selection
                        
                    e_item = st.text_input("Item", row['Item'])
                    
                    ec1, ec2 = st.columns(2)
                    e_curr = ec1.selectbox("Currency", ["AUD", "HKD"], index=safe_index(["AUD", "HKD"], row['Currency']))
                    e_cost = ec2.number_input("Amount", min_value=0.0, value=float(row['Cost']), step=0.01)
                    
                    e_paid = st.selectbox("Paid By", trip_users, index=safe_index(trip_users, row['Paid By']))
                    
                    split_opts = ["All"] + trip_users
                    e_split = st.selectbox("Split With", split_opts, index=safe_index(split_opts, row['Split By']))
                    e_remark = st.text_input("Remarks", str(row['Remark']))
                    
                    sc1, sc2 = st.columns(2)
                    if sc1.form_submit_button("💾 Save Changes", use_container_width=True):
                        if e_cat:
                            df_exp.loc[idx, "Date"] = str(e_date_input)
                            df_exp.loc[idx, "Category"] = e_cat
                            df_exp.loc[idx, "Item"] = e_item
                            df_exp.loc[idx, "Currency"] = e_curr
                            df_exp.loc[idx, "Cost"] = e_cost
                            df_exp.loc[idx, "Paid By"] = e_paid
                            df_exp.loc[idx, "Split By"] = e_split
                            df_exp.loc[idx, "Remark"] = e_remark
                            
                            conn.update(spreadsheet=url, data=df_exp, worksheet="Expenses")
                            st.session_state.editing_row = None
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Category cannot be blank.")
                        
                    if sc2.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.editing_row = None
                        st.rerun()
                        
        # --- VIEW MODE ---
        else:
            with st.container(border=True):
                col1, col2 = st.columns([5, 1.5])
                with col1:
                    st.markdown(f"#### {row['Item']}")
                    st.caption(f"📅 {row['Date']} | 📂 {row['Category']}")
                    
                    st.write(f"💰 **{display_currency} {row['Converted_Cost']:.2f}**")
                    if row['Currency'] != display_currency:
                        st.caption(f"*(Original: {row['Currency']} {row['Cost']:.2f})*")
                        
                    st.write(f"💳 Paid by **{row['Paid By']}** | Split: **{row['Split By']}**")
                    
                    display_remark = row['Remark'] if str(row['Remark']).strip() else "nothing yet..."
                    st.caption(f"📝 {display_remark}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_btn_{idx}", use_container_width=True):
                        st.session_state.editing_row = idx
                        st.rerun()
                        
                    if st.button("🗑️ Delete", key=f"del_{idx}", type="secondary", use_container_width=True):
                        cleaned_df = df_exp.drop(index=idx)
                        conn.update(spreadsheet=url, data=cleaned_df, worksheet="Expenses")
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()

st.divider()

# --- 7. SECTION: ANALYTICS & SETTLEMENTS ---
st.subheader("📈 Trip Summary & Analytics")

active_calc_df = df_exp[df_exp["Settled"] == False].copy()

if active_calc_df.empty:
    st.success("🎉 All logged items are completely settled!")
else:
    total_trip = active_calc_df["Converted_Cost"].sum()
    
    pie_data = []
    for _, row in active_calc_df.iterrows():
        amt = row["Converted_Cost"]
        cat = row["Category"]
        splitter = str(row["Split By"]).strip()
        
        if splitter == "All":
            share = amt / len(trip_users)
            for u in trip_users:
                pie_data.append({"User": u, "Category": cat, "Amount": share})
        else:
            involved = [u.strip() for u in splitter.split(",") if u.strip() in trip_users]
            if involved:
                share = amt / len(involved)
                for u in involved:
                    pie_data.append({"User": u, "Category": cat, "Amount": share})
            else:
                payer = str(row["Paid By"]).strip()
                pie_data.append({"User": payer, "Category": cat, "Amount": amt})

    shares_df = pd.DataFrame(pie_data)
    
    m1, m2 = st.columns(2)
    m1.metric(f"Unsettled Total ({display_currency})", f"${total_trip:,.2f}")
    
    view_options = ["Everyone"] + trip_users
    selected_view_user = m2.selectbox("👀 View Personal Total Expense:", view_options)
    
    if selected_view_user == "Everyone":
        display_total = total_trip
        cat_chart_data = active_calc_df.groupby("Category")["Converted_Cost"].sum().reset_index()
        cat_chart_data.rename(columns={"Converted_Cost": "Amount"}, inplace=True)
    else:
        if not shares_df.empty:
            user_df = shares_df[shares_df["User"] == selected_view_user]
            display_total = user_df["Amount"].sum()
            cat_chart_data = user_df.groupby("Category")["Amount"].sum().reset_index()
        else:
            display_total = 0.0
            cat_chart_data = pd.DataFrame(columns=["Category", "Amount"])
            
    m2.metric(f"Total Share ({display_currency})", f"${display_total:,.2f}")
    
    st.write(f"#### 🍩 Spending Breakdown ({selected_view_user})")
    
    if not cat_chart_data.empty and display_total > 0:
        fig = px.pie(
            cat_chart_data, 
            values="Amount", 
            names="Category", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Prism 
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No active expenses for {selected_view_user} yet.")
    
    st.write("#### Who pays who?💸")
    balances = {user: 0.0 for user in trip_users}
    
    for _, row in active_calc_df.iterrows():
        amt = row["Converted_Cost"]
        payer = str(row["Paid By"]).strip()
        splitter = str(row["Split By"]).strip()
        
        if payer in balances: balances[payer] += amt
            
        if splitter == "All":
            for user in trip_users: balances[user] -= (amt / len(trip_users))
        else:
            involved_users = [u.strip() for u in splitter.split(",") if u.strip() in balances]
            if involved_users:
                for user in involved_users: balances[user] -= (amt / len(involved_users))
            else:
                if payer in balances: balances[payer] -= amt

    debtors = sorted([[user, bal] for user, bal in balances.items() if bal < -0.01], key=lambda x: x[1])
    creditors = sorted([[user, bal] for user, bal in balances.items() if bal > 0.01], key=lambda x: x[1], reverse=True)
    transactions = []
    
    while debtors and creditors:
        debtor_name, debtor_bal = debtors[0]
        creditor_name, creditor_bal = creditors[0]
        amount_to_pay = min(abs(debtor_bal), creditor_bal)
        transactions.append(f"👉 **{debtor_name}** pays **{creditor_name}**: **{display_currency} {amount_to_pay:.2f}**")
        
        debtors[0][1] += amount_to_pay
        creditors[0][1] -= amount_to_pay
        
        if abs(debtors[0][1]) < 0.01: debtors.pop(0)
        if creditors[0][1] < 0.01: creditors.pop(0)
            
    if not transactions:
        st.info("Balances are fully even! Nobody owes anything.")
    else:
        for trans in transactions:
            st.write(trans)
            
        st.divider()
        if st.button("✅ Settle All Pending Expenses", use_container_width=True, type="primary"):
            df_exp.loc[df_exp["Settled"] == False, "Settled"] = True
            conn.update(spreadsheet=url, data=df_exp, worksheet="Expenses")
            st.cache_data.clear()
            st.success("All expenses have been successfully settled! 🎉")
            time.sleep(1.5)
            st.rerun()
