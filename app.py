import streamlit as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Sydney 2026 Expense Tracker", page_icon="💰", layout="centered")
st.title("💰 Sydney 2026 Expense Tracker")

# --- GOOGLE SHEETS CONNECTION ---
# Replace with your actual Google Sheet URL
url = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

# Define your trip members here
trip_users = ["UserA", "UserB", "UserC"] 

# --- DATA LOADING (With 5-second safety buffer for rate limits) ---
try:
    df_exp = conn.read(spreadsheet=url, worksheet="Expenses", ttl=5)
    
    # Ensure required columns exist
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

# ==============================================================================
# --- SECTION 1: ADD NEW EXPENSE ---
# ==============================================================================
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
                # Build the new row matching your sheet's column schema
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
                
                # Append and write to Google Sheets
                updated_df = pd.concat([df_exp, new_row], ignore_index=True)
                conn.update(spreadsheet=url, data=updated_df, worksheet="Expenses")
                
                st.success(f"Added {f_item} (${f_cost} {f_curr})!")
                st.cache_data.clear()
                import time; time.sleep(1)
                st.rerun()
            else:
                st.error("Please enter both an item description and an amount.")

st.divider()

# ==============================================================================
# --- SECTION 2: THE LEDGER & SETTLEMENTS ---
# ==============================================================================
st.subheader("📊 Active Ledger")

# Quick Filters
show_settled = st.checkbox("Show Settled Expenses", value=False)
view_df = df_exp[df_exp["Settled"] == show_settled]

if view_df.empty:
    st.info("No active expenses found. Keep an eye on your wallet!")
else:
    # Display expenses in a mobile-friendly stack view
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
                # Settle Button Toggle
                button_label = "🔄" if show_settled else "✅"
                button_help = "Mark as Unsettled" if show_settled else "Mark as Settled"
                
                if st.button(button_label, key=f"settle_{idx}", help=button_help):
                    df_exp.loc[idx, "Settled"] = not show_settled
                    conn.update(spreadsheet=url, data=df_exp, worksheet="Expenses")
                    st.cache_data.clear()
                    import time; time.sleep(0.5)
                    st.rerun()
                
                # Delete Button
                if st.button("🗑️", key=f"del_{idx}", help="Delete Entry"):
                    cleaned_df = df_exp.drop(index=idx)
                    conn.update(spreadsheet=url, data=cleaned_df, worksheet="Expenses")
                    st.cache_data.clear()
                    import time; time.sleep(0.5)
                    st.rerun()
