import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘")

st.title("🇦🇺 Our Shared Travel Hub")

# 1. Your Google Sheet Address
SHEET_URL = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=0#gid=0"

# 2. Connect to Google Sheets (The Robot Intern wakes up)
conn = st.connection("gsheets", type=GSheetsConnection)

st.subheader("🗓️ Trip Planner")
st.write("Edit the table below directly! Click save when you're done.")

try:
    # 3. Read the data from the tab named "Planner"
    df = conn.read(spreadsheet=SHEET_URL, worksheet="Planner")

    # 4. The Magic Table (allows editing on the website)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    # 5. The Save Button
    if st.button("Save Changes to Google Sheet"):
        # Tell the robot to overwrite the old sheet with your new edits
        conn.update(spreadsheet=SHEET_URL, worksheet="Planner", data=edited_df)
        st.success("Trip updated! Your friends can see the changes now. 🚀")
        st.balloons() # Fun celebration animation

except Exception as e:
    st.error(f"Oops! The robot couldn't connect. Error: {e}")
