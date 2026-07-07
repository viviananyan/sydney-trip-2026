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

# 🔴 Base categories with emojis
base_categories = [
    "🍔 Food", "🚌 Transport", "🛍️ Shopping", 
    "🎟️ Entertainment", "🏨 Stay", "✈️ Flights", "📦 Other"
]

def safe_index(lst, item):
    return lst.index(item) if item in lst else 0

# --- 3. DATA LOADING & DYNAMIC CATEGORIES ---
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

    # 🔴 Dynamically load any custom categories previously saved to the sheet
    existing_custom_cats = [c for c in df_exp["Category"].dropna().unique() if c and c not in base_categories]
    all_categories_list = base_categories + existing_custom_cats
    dropdown_options = all_categories_list + ["➕ Add Custom..."]

except Exception as e:
    st.error(f"Error loading Expenses tab: {e}")
    st.stop()

# --- 4. SECTION: ADD NEW EXPENSE ---
with st.expander("➕ Log New Expense", expanded=False):
    with st.form("australia_tracker_form_v8", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.date.today())
        
        # 🔴 Dynamic Category Selector
        f_cat_selection = st.selectbox("Category", dropdown_options)
        if f_cat_selection == "➕ Add Custom...":
            f_cat = st.text_input("Type Custom Category", placeholder="e.g., 🏄‍♂️ Surfing")
        else:
            f_cat = f_cat_selection
            
        f_item = st.text_input("Item / Description", placeholder="e.g., Dinner at Sydney Tower")
        
        c1, c2 = st.columns(2)
        f_curr = c1.selectbox("Currency", ["AUD", "HKD"])
        f_cost = c2.number
