import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import time

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Australia 2026 Expense Tracker", page_icon="💰", layout="centered")
st.title("💰 Australia 2026 Expense Tracker")

# --- 2. GOOGLE SHEETS CONNECTION ---
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit#gid=743694833"
conn = st.connection("gsheets", type=GSheetsConnection)

# Your personalized squad names matching your spreadsheet exactly
trip_users = ["Suri🐶", "Bobo🍔", "Sally🦕"] 

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

except Exception as e:
    st.error(f"Error loading Expenses tab: {e}")
    st.stop()

# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    with st.form("australia_final_ledger_form_2026", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        f_cat = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"])
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        
        f_paid = st.selectbox("Paid By", trip_users)
        f_split = st.selectbox("Split With", ["All"] + trip_users)
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            if f_item and f_cost > 0:
                new_row = pd.DataFrame([{
                    "Date": str(f_date), "Category": f_cat, "Item": f_item,
                    "Currency": f_curr, "Cost": f_cost, "Paid By": f_paid,
                    "Split By": f_split, "Remark": f_remark, "Settled": False
                }])
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                st.success(f"Added {f_item} ({f_curr} {f_cost:.2f})!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter both an item description and an amount.")

st.divider()

# --- 5. GLOBAL EXCHANGE RATE CONFIGURATION (With fully unique element key) ---
st.sidebar.header("💱 Exchange Settings")
# Added an explicit, unique key string to bypass ID collisions entirely
ex_rate = st.sidebar.number_input(
    "Set Conversion Rate (1 AUD to HKD)", 
    min_value=1.0, 
    value=5.42, 
    step=0.01, 
    key="unique_sys_exchange_rate_input",
    help="Used to normalize all calculation values."
)

# Helper function to normalize cost to HKD
def convert_to_hkd(row):
    return row["Cost"] * ex_rate if row["Currency"] == "AUD" else row["Cost"]

df_exp["Cost_HKD"] = df_exp.apply(convert_to_hkd, axis=1)

# --- 6. SECTION: SEARCH, FILTER & SORT LEDGER ---
st.subheader("📊 Active Ledger")

with st.expander("🔍 Search & Filter Tools", expanded=False):
    s_query = st.text_input("Search by Item Name", placeholder="Type keywords...")
    
    f1, f2 = st.columns(2)
    s_payer = f1.multiselect("Filter by Payer", options=trip_users, default=[])
    s_cat = f2.multiselect("Filter by Category", options=["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"], default=[])
    
    s_sort = st.selectbox("Sort Order", [
        "Date (Newest First)", "Date (Oldest First)", 
        "Cost (Highest First)", "Cost (Lowest First)"
    ])

# Apply State Filters
show_settled = st.checkbox("Show Settled Expenses", value=False)
view_df = df_exp[df_exp["Settled"] == show_settled].copy()

# Apply Search Filters
if s_query:
    view_df = view_df[view_df["Item"].str.contains(s_query, case=False, na=False)]
if s_payer:
    view_df = view_df[view_df["Paid By"].isin(s_payer)]
if s_cat:
    view_df = view_df[view_df["Category"].isin(s_cat)]

# Apply Sorting
if s_sort == "Date (Newest First)":
    view_df = view_df.sort_values(by="Date", ascending=False)
elif s_sort == "Date (Oldest First)":
    view_df = view_df.sort_values(by="Date", ascending=True)
elif s_sort == "Cost (Highest First)":
    view_df = view_df.sort_values(by="Cost_HKD", ascending=False)
elif s_sort == "Cost (Lowest First)":
    view_df = view_df.sort_values(by="Cost_HKD", ascending=True)
# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    # Isolated form key to bypass Streamlit's background cache locks
    with st.form("australia_final_ledger_form_2026", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        f_cat = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"])
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        
        f_paid = st.selectbox("Paid By", trip_users)
        f_split = st.selectbox("Split With", ["All"] + trip_users)
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            if f_item and f_cost > 0:
                new_row = pd.DataFrame([{
                    "Date": str(f_date), "Category": f_cat, "Item": f_item,
                    "Currency": f_curr, "Cost": f_cost, "Paid By": f_paid,
                    "Split By": f_split, "Remark": f_remark, "Settled": False
                }])
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                st.success(f"Added {f_item} ({f_curr} {f_cost:.2f})!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter both an item description and an amount.")

st.divider()

# --- 5. GLOBAL EXCHANGE RATE CONFIGURATION ---
st.sidebar.header("💱 Exchange Settings")
ex_rate = st.sidebar.number_input("1 AUD to HKD Rate", min_value=1.0, value=5.15, step=0.01, help="Used for unified analytics calculations.")

# Helper function to# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    # 🛠️ FIXED: Changed form key to "main_expense_creation_form" to eliminate duplicate key error
    with st.form("main_expense_creation_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        f_cat = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"])
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        
        f_paid = st.selectbox("Paid By", trip_users)
        f_split = st.selectbox("Split With", ["All"] + trip_users)
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            if f_item and f_cost > 0:
                new_row = pd.DataFrame([{
                    "Date": str(f_date), "Category": f_cat, "Item": f_item,
                    "Currency": f_curr, "Cost": f_cost, "Paid By": f_paid,
                    "Split By": f_split, "Remark": f_remark, "Settled": False
                }])
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                st.success(f"Added {f_item} ({f_curr} {f_cost:.2f})!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter both an item description and an amount.")
                
# --- 5. GLOBAL EXCHANGE RATE CONFIGURATION ---
st.sidebar.header("💱 Exchange Settings")
ex_rate = st.sidebar.number_input("1 AUD to HKD Rate", min_value=1.0, value=5.15, step=0.01, help="Used for unified analytics calculations.")

# Helper function to normalize cost to HKD
def convert_to_hkd(row):
    return row["Cost"] * ex_rate if row["Currency"] == "AUD" else row["Cost"]

df_exp["Cost_HKD"] = df_exp.apply(convert_to_hkd, axis=1)

# ==============================================================================
# --- 6. SECTION: SEARCH, FILTER & SORT LEDGER ---
# ==============================================================================
st.subheader("📊 Active Ledger")

with st.expander("🔍 Search & Filter Tools", expanded=False):
    s_query = st.text_input("Search by Item Name", placeholder="Type keywords...")
    
    f1, f2 = st.columns(2)
    s_payer = f1.multiselect("Filter by Payer", options=trip_users, default=[])
    s_cat = f2.multiselect("Filter by Category", options=["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"], default=[])
    
    s_sort = st.selectbox("Sort Order", [
        "Date (Newest First)", "Date (Oldest First)", 
        "Cost (Highest First)", "Cost (Lowest First)"
    ])

# Apply State Filters
show_settled = st.checkbox("Show Settled Expenses", value=False)
view_df = df_exp[df_exp["Settled"] == show_settled].copy()

# Apply Search Filters
if s_query:
    view_df = view_df[view_df["Item"].str.contains(s_query, case=False, na=False)]
if s_payer:
    view_df = view_df[view_df["Paid By"].isin(s_payer)]
if s_cat:
    view_df = view_df[view_df["Category"].isin(s_cat)]

# Apply Sorting
if s_sort == "Date (Newest First)":
    view_df = view_df.sort_values(by="Date", ascending=False)
elif s_sort == "Date (Oldest First)":
    view_df = view_df.sort_values(by="Date", ascending=True)
elif s_sort == "Cost (Highest First)":
    view_df = view_df.sort_values(by="Cost_HKD", ascending=False)
elif s_sort == "Cost (Lowest First)":
    view_df = view_df.sort_values(by="Cost_HKD", ascending=True)

# Render filtered stack
if view_df.empty:
    st.info("No expenses found matching these criteria.")
else:
    for idx, row in view_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"#### {row['Item']}")
                st.caption(f"📅 {row['Date']} | 📂 {row['Category']}")
                st.write(f"💰 **{row['Currency']} {row['Cost']:.2f}** *(approx. HKD {row['Cost_HKD']:.2f})*")
                st.write(f"💳 Paid by **{row['Paid By']}** | Split: **{row['Split By']}**")
                if row['Remark']:
                    st.caption(f"📝 {row['Remark']}")
            
            with col2:
                button_label = "🔄" if show_settled else "✅"
                
                # 🛠️ Fixed Line 136: Clean and separated from the data loader error!
                if st.button(button_label, key=f"settle_{idx}", help="Toggle status"):
                    df_exp.loc[idx, "Settled"] = not show_settled
                    conn.update(spreadsheet=url, data=df_exp, worksheet="Expenses")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                
                if st.button("🗑️", key=f"del_{idx}", help="Delete Entry"):
                    cleaned_df = df_exp.drop(index=idx)
                    conn.update(spreadsheet=url, data=cleaned_df, worksheet="Expenses")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                    
# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=True):
    with st.form("expense_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        f_cat = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Stay", "Flights", "Other"])
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number_input("Amount", min_value=0.0, step=0.01, format="%.2f")
        
        f_paid = st.selectbox("Paid By", trip_users)
        f_split = st.selectbox("Split With", ["All"] + trip_users)
        f_remark = st.text_input("Remarks / Notes")
        
        if st.form_submit_button("💾 Save Expense", use_container_width=True):
            if f_item and f_cost > 0:
                new_row = pd.DataFrame([{
                    "Date": str(f_date),
                    "Category": f_cat,
                    "Item": f_item,
                    "Currency": f_curr,
                    "Cost": f_cost,
                    "Paid By": f_paid,
                    "Split By": f_split,
                    "Remark": f_remark,
                    "Settled": False
                }])
                
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                
                st.success(f"Added {f_item} (${f_cost} {f_curr})!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter both an item description and an amount.")

st.divider()

# --- 5. SECTION: THE LEDGER & SETTLEMENTS ---
st.subheader("📊 Active Ledger")

show_settled = st.checkbox("Show Settled Expenses", value=False)
view_df = df_exp[df_exp["Settled"] == show_settled]

if view_df.empty:
    st.info("No active expenses found. Keep an eye on your wallet!")
else:
    for idx, row in view_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"#### {row['Item']}")
                st.caption(f"📅 {row['Date']} | 📂 {row['Category']}")
                st.write(f"💰 **{row['Currency']} {row['Cost']:.2f}**")
                st.write(f"💳 Paid by **{row['Paid By']}** | Split: **{row['Split By']}**")
                if row['Remark']:
                    st.caption(f"📝 {row['Remark']}")
            
            with col2:
                button_label = "🔄" if show_settled else "✅"
                button_help = "Mark as Unsettled" if show_settled else "Mark as Settled"
                
                if st.button(button_label, key=f"settle_{idx}", help=button_help):
                    df_exp.loc[idx, "Settled"] = not show_settled
                    conn.update(spreadsheet=url, data=df_exp, worksheet="Expenses")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                
                if st.button("🗑️", key=f"del_{idx}", help="Delete Entry"):
                    cleaned_df = df_exp.drop(index=idx)
                    conn.update(spreadsheet=url, data=cleaned_df, worksheet="Expenses")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
