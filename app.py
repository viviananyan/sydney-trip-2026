import streamlit as st

# This sets the name on the browser tab
st.set_page_config(page_title="Syd/Melb 2026", page_icon="🦘")

st.title("🦘 Australia 2026 Trip Hub")
st.write("Hello! This is our custom travel app for Sydney and Melbourne.")

# A simple button to test the "one-tap" logic later
if st.button("Click for a Winter Reminder!"):
    st.snow() # This is a built-in fun feature of Streamlit
    st.warning("Remember: August is Winter! Pack your warm coats for Melbourne! ❄️")
