import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘")

st.title("🇦🇺 Our Shared Travel Hub")

# 1. Connect to Google Sheets (This looks at your SECRETS automatically)
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Define the URL of your Google Sheet
# (Make sure this is the URL of the sheet you SHARED with the robot email!)
url = "https://docs.google.com/spreadsheets/d/17vTlewfPPS2lZainhCJgEEOkp5tJ3LDNqX8myrfJ7uQ/edit?pli=1&gid=0#gid=0"

try:
    # 3. Read the data
    df = conn.read(spreadsheet=url, worksheet="Planner")

    # 4. Show the interactive table
    st.subheader("🗓️ Trip Planner")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    # 5. Save functionality
    import folium
from streamlit_folium import st_folium

st.divider() # Adds a nice visual line
st.subheader("📍 Our Sydney/Melbourne Map")

# Create a map centered on Australia
m = folium.Map(location=[-33.8688, 151.2093], zoom_start=12)

# This loop looks at your table and adds pins
for index, row in df.iterrows():
    # If you have a column named 'Location', it adds a pin
    if 'Location' in df.columns and pd.notnull(row['Location']):
        # For now, let's just put a pin in Sydney as a test
        folium.Marker(
            [-33.86, 151.20], 
            popup=row['Activity'], 
            tooltip=row['Activity']
        ).add_to(m)

st_folium(m, width="stretch", height=400)
    if st.button("Save Changes"):
        conn.update(spreadsheet=url, data=edited_df, worksheet="Planner")
        st.success("Saved! 🚀")
        st.balloons()

except Exception as e:
    st.error("The app is connected to the 'Key', but it can't find the Sheet.")
    st.write(f"Error Details: {e}")
