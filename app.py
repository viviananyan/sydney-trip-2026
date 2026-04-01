import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘", layout="wide")

st.title("🇦🇺 Our Shared Travel Hub")

# 1. Manually pull the secrets into a dictionary (This fixes the MalformedError)
# This ensures the robot sees EVERYTHING it needs in one go.
try:
    secret_info = st.secrets["connections"]["gsheets"]
    conn = st.connection("gsheets", type=GSheetsConnection, **secret_info)
except Exception as e:
    st.error("The app can't see your Secrets yet. Check the Streamlit Dashboard Settings!")
    st.stop()

url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=0#gid=0"

try:
    df = conn.read(spreadsheet=url, worksheet="Planner")

    st.subheader("🗓️ Trip Planner")
    
    # 2. FIXING THE WIDTH WARNING (The 2026 Update)
    # 'use_container_width=True' is now 'width="stretch"'
    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

    if st.button("Save Changes"):
        conn.update(spreadsheet=url, data=edited_df, worksheet="Planner")
        st.success("Saved! 🚀")
        st.balloons()

except Exception as e:
    st.error(f"Connected to Robot, but couldn't read the Sheet: {e}")
