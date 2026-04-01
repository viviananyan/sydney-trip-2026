import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘")

st.title("🇦🇺 Our Shared Travel Hub")

# 1. Connect to Google Sheets (This looks at your SECRETS automatically)
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Define the URL of your Google Sheet
# (Make sure this is the URL of the sheet you SHARED with the robot email!)
url = "PASTE_YOUR_GOOGLE_SHEET_URL_HERE"

try:
    # 3. Read the data
    df = conn.read(spreadsheet=url, worksheet="Planner")

    # 4. Show the interactive table
    st.subheader("🗓️ Trip Planner")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    # 5. Save functionality
    if st.button("Save Changes"):
        conn.update(spreadsheet=url, data=edited_df, worksheet="Planner")
        st.success("Saved! 🚀")
        st.balloons()

except Exception as e:
    st.error("The app is connected to the 'Key', but it can't find the Sheet.")
    st.write(f"Error Details: {e}")
