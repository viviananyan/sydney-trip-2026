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
if "confirm_settle" not in st.session_state:
    st.session_state.confirm_settle = False

# --- 2. GOOGLE SHEETS CONNECTION & CONSTANTS ---
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit#gid=743694833"
conn = st.connection("gsheets", type=GSheetsConnection)

trip_users = ["Suri🐶", "Bobo🍔", "Sally🦕"] 
FIXED_HKD_RATE = 5.42

base_categories = [
    "🍔 Food", "🚌 Transport", "🛍️ Shopping", 
    "🎟️ Entertainment", "🏨 Stay", "✈️ Flights", "📦 Other"
]

def safe_index(lst, item):
    return lst.index(item) if item in lst else 0

# --- 3. DATA LOADING & SANITIZATION ---
try:
    df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=5)
    
    # Ensure all columns exist, including our new permanent Cost (HKD) column
    required_cols = ["Date", "Category", "Item", "Currency", "Cost", "Cost (HKD)", "Paid By", "Split By", "Remark", "Settled"]
    for col in required_cols:
        if col not in df_exp.columns:
            df_exp[col] = False if col == "Settled" else ""
            
    df_exp = df_exp.dropna(how="all", subset=["Item"])
    df_exp["Settled"] = df_exp["Settled"].fillna(False).astype(bool)
    df_exp["Cost"] = pd.to_numeric(df_exp["Cost"], errors="coerce").fillna(0.0)
    
    df_exp["Remark"] = df_exp["Remark"].fillna("").astype(str)
    df_exp["Remark"] = df_exp["Remark"].replace({"nan": "", "None": "", "NaN": ""})

    df_exp["Date"] = pd.to_datetime(df_exp["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    
    # 🔴 Retrofit existing rows to ensure Cost (HKD) is strictly populated
    def force_hkd_calc(row):
        return row["Cost"] * FIXED_HKD_RATE if row["Currency"] == "AUD" else row["Cost"]
    df_exp["Cost (HKD)"] = df_exp.apply(force_hkd_calc, axis=1)

    existing_custom_cats = [c for c in df_exp["Category"].dropna().unique() if c and c not in base_categories]
    all_categories_list = base_categories + existing_custom_cats
    dropdown_options = all_categories_list + ["➕ Add Custom..."]

except Exception as e:
    st.error(f"Error loading Expenses tab: {e}")
    st.stop()

# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    with st.form("australia_tracker_form_v12", clear_on_submit=True):
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
        f_split_selections = st.multiselect("Split With", ["All"] + trip_users, default=["All"])
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            f_split_str = "All" if "All" in f_split_selections or not f_split_selections else ", ".join(f_split_selections)
            
            if f_item and f_cost > 0 and f_cat:
                new_hkd_cost = f_cost * FIXED_HKD_RATE if f_curr == "AUD" else f_cost
                new_row = pd.DataFrame([{
                    "Date": str(f_date), "Category": f_cat, "Item": f_item,
                    "Currency": f_curr, "Cost": f_cost, "Cost (HKD)": new_hkd_cost, 
                    "Paid By": f_paid, "Split By": f_split_str, "Remark": f_remark, "Settled": False
                }])
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                # Save the new row with the HKD column directly to the sheet
                conn.update(spreadsheet=url, data=updated_df[required_cols], worksheet="Expenses")
                st.success(f"Added {f_item}!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please ensure the item, amount, category, and split are filled out.")

st.divider()

# --- 5. GLOBAL CURRENCY CONFIGURATION ---
st.sidebar.header("💱 Live View Settings")
st.sidebar.info(f"Fixed App Exchange Rate:\n**1 AUD = {FIXED_HKD_RATE} HKD**")
display_currency = st.sidebar.radio("View App In:", ["HKD", "AUD"], horizontal=True)

def convert_display_cost(row):
    if display_currency == "HKD":
        return row["Cost"] * FIXED_HKD_RATE if row["Currency"] == "AUD" else row["Cost"]
    else:
        return row["Cost"] / FIXED_HKD_RATE if row["Currency"] == "HKD" else row["Cost"]

df_exp["Converted_Cost"] = df_exp.apply(convert_display_cost, axis=1)

# --- 6. SECTION: ACTIVE LEDGER (WITH EDIT CAPABILITY) ---
st.subheader("📊 Full Trip Ledger")

with st.expander("🔍 Search & Filter Tools", expanded=False):
    s_query = st.text_input("Search by Item Name", placeholder="Type keywords...")
    f1, f2 = st.columns(2)
    s_payer = f1.multiselect("Filter by Payer", options=trip_users, default=[])
    s_cat = f2.multiselect("Filter by Category", options=all_categories_list, default=[])
    s_sort = st.selectbox("Sort Order", ["Date (Newest First)", "Date (Oldest First)", "Cost (Highest First)", "Cost (Lowest First)"])

view_df = df_exp.copy()
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
                    e_cat = st.text_input("Type Custom Category", placeholder="e.g., 🏄‍♂️ Surfing") if e_cat_selection == "➕ Add Custom..." else e_cat_selection
                    e_item = st.text_input("Item", row['Item'])
                    
                    ec1, ec2 = st.columns(2)
                    e_curr = ec1.selectbox("Currency", ["AUD", "HKD"], index=safe_index(["AUD", "HKD"], row['Currency']))
                    e_cost = ec2.number_input("Amount", min_value=0.0, value=float(row['Cost']), step=0.01)
                    e_paid = st.selectbox("Paid By", trip_users, index=safe_index(trip_users, row['Paid By']))
                    
                    current_split = str(row['Split By']).strip()
                    def_split = ["All"] if current_split == "All" else [u.strip() for u in current_split.split(",") if u.strip() in trip_users]
                    if not def_split: def_split = ["All"]
                        
                    e_split_selections = st.multiselect("Split With", ["All"] + trip_users, default=def_split)
                    e_remark = st.text_input("Remarks", str(row['Remark']))
                    
                    sc1, sc2 = st.columns(2)
                    if sc1.form_submit_button("💾 Save Changes", use_container_width=True):
                        if e_cat:
                            e_split_str = "All" if "All" in e_split_selections or not e_split_selections else ", ".join(e_split_selections)
                            df_exp.loc[idx, "Date"] = str(e_date_input)
                            df_exp.loc[idx, "Category"] = e_cat
                            df_exp.loc[idx, "Item"] = e_item
                            df_exp.loc[idx, "Currency"] = e_curr
                            df_exp.loc[idx, "Cost"] = e_cost
                            df_exp.loc[idx, "Cost (HKD)"] = e_cost * FIXED_HKD_RATE if e_curr == "AUD" else e_cost
                            df_exp.loc[idx, "Paid By"] = e_paid
                            df_exp.loc[idx, "Split By"] = e_split_str
                            df_exp.loc[idx, "Remark"] = e_remark
                            
                            conn.update(spreadsheet=url, data=df_exp[required_cols], worksheet="Expenses")
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
                    st.caption(f"📝 {row['Remark'] if str(row['Remark']).strip() else 'nothing yet...'}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_btn_{idx}", use_container_width=True):
                        st.session_state.editing_row = idx
                        st.rerun()
                        
                    if st.button("🗑️ Delete", key=f"del_{idx}", type="secondary", use_container_width=True):
                        cleaned_df = df_exp.drop(index=idx)
                        conn.update(spreadsheet=url, data=cleaned_df[required_cols], worksheet="Expenses")
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()

st.divider()

# --- 7. SECTION: ANALYTICS & SETTLEMENTS ---
st.subheader("📈 Trip Analytics & Final Settlement")

if df_exp.empty:
    st.info("No expenses logged yet.")
else:
    # We strictly use the permanent Cost (HKD) column for all final math
    grand_total_hkd = df_exp["Cost (HKD)"].sum()
    balances_hkd = {user: 0.0 for user in trip_users}
    paid_hkd = {user: 0.0 for user in trip_users}
    consumed_hkd = {user: 0.0 for user in trip_users}
    
    for _, row in df_exp.iterrows():
        amt = row["Cost (HKD)"]
        payer = str(row["Paid By"]).strip()
        splitter = str(row["Split By"]).strip()
        
        if payer in paid_hkd: 
            paid_hkd[payer] += amt
            balances_hkd[payer] += amt
            
        if splitter == "All":
            for user in trip_users: 
                consumed_hkd[user] += (amt / len(trip_users))
                balances_hkd[user] -= (amt / len(trip_users))
        else:
            involved_users = [u.strip() for u in splitter.split(",") if u.strip() in balances_hkd]
            if involved_users:
                for user in involved_users: 
                    consumed_hkd[user] += (amt / len(involved_users))
                    balances_hkd[user] -= (amt / len(involved_users))
            else:
                if payer in balances_hkd: 
                    consumed_hkd[payer] += amt
                    balances_hkd[payer] -= amt

    m1, m2 = st.columns(2)
    m1.metric("Grand Trip Total (HKD)", f"${grand_total_hkd:,.2f}")
    
    selected_view_user = m2.selectbox("👀 View Personal Total Consumed:", ["Everyone"] + trip_users)
    display_total = grand_total_hkd if selected_view_user == "Everyone" else consumed_hkd[selected_view_user]
    m2.metric("Total True Share (HKD)", f"${display_total:,.2f}")
    
    st.divider()
    st.write("#### 💸 Final Settlement Details (HKD)")
    
    # Calculate exact transactions
    debtors = sorted([[user, bal] for user, bal in balances_hkd.items() if bal < -0.01], key=lambda x: x[1])
    creditors = sorted([[user, bal] for user, bal in balances_hkd.items() if bal > 0.01], key=lambda x: x[1], reverse=True)
    transactions = []
    
    while debtors and creditors:
        debtor_name, debtor_bal = debtors[0]
        creditor_name, creditor_bal = creditors[0]
        amount_to_pay = min(abs(debtor_bal), creditor_bal)
        transactions.append(f"👉 **{debtor_name}** pays **{creditor_name}**: **HKD ${amount_to_pay:,.2f}**")
        
        debtors[0][1] += amount_to_pay
        creditors[0][1] -= amount_to_pay
        
        if abs(debtors[0][1]) < 0.01: debtors.pop(0)
        if creditors[0][1] < 0.01: creditors.pop(0)

    for trans in transactions:
        st.write(trans)

    st.write("")
    
    # 🔴 THE NEW FEATURE: Exporting the breakdown to Google Sheets
    with st.container(border=True):
        st.write("Ready to ask for the money? Click below to generate a clear breakdown tab directly inside your Google Sheet so everyone can check the math.")
        if st.button("🧾 Generate Google Sheets Settlement Report", use_container_width=True, type="primary"):
            
            # 1. Build the personal totals table
            report_data = []
            for user in trip_users:
                report_data.append({
                    "Name": user,
                    "Total Paid (HKD)": round(paid_hkd[user], 2),
                    "Total Share Consumed (HKD)": round(consumed_hkd[user], 2),
                    "Net Balance (Owes/Owed)": round(balances_hkd[user], 2)
                })
            report_df = pd.DataFrame(report_data)
            
            # 2. Build the final transfers table
            trans_data = [{"Name": "--- FINAL TRANSFERS ---", "Total Paid (HKD)": "", "Total Share Consumed (HKD)": "", "Net Balance (Owes/Owed)": ""}]
            for t in transactions:
                clean_t = t.replace("👉 ", "").replace("**", "")
                trans_data.append({
                    "Name": clean_t, "Total Paid (HKD)": "", 
                    "Total Share Consumed (HKD)": "", "Net Balance (Owes/Owed)": ""
                })
            
            # 3. Combine and write to a new tab!
            final_export_df = pd.concat([report_df, pd.DataFrame(trans_data)], ignore_index=True)
            conn.update(spreadsheet=url, data=final_export_df, worksheet="Settlement_Report")
            
            st.success("✅ Success! A new tab named 'Settlement_Report' has been created in your Google Sheet.")
            st.balloons()
