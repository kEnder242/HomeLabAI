import streamlit as st
import time
import os

st.set_page_config(page_title="Acme Lab Pager", page_icon="📟", layout="wide")

st.title("📟 Acme Lab Pager")

# Paths
SERVER_LOG = "server.log"
USER_NOTES = "user_notes.log"

# Sidebar for controls
st.sidebar.header("Controls")
auto_refresh = st.sidebar.checkbox("Auto-refresh Logs", value=True)
refresh_rate = st.sidebar.slider("Refresh Rate (s)", 1, 10, 2)

# Input Section
st.subheader("📝 Quick Note / Command")
with st.form("message_form", clear_on_submit=True):
    user_input = st.text_input("Message for Pinky/Self:")
    submitted = st.form_submit_button("Send")
    
    if submitted and user_input:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] USER: {user_input}\n"
        with open(USER_NOTES, "a") as f:
            f.write(entry)
        st.success(f"Sent: {user_input}")

# Columns for Logs
col1, col2 = st.columns(2)

with col1:
    st.subheader("📜 Server Log (Tail)")
    log_placeholder = st.empty()

with col2:
    st.subheader("📓 User Notes")
    notes_placeholder = st.empty()

def read_tail(filename, n=50):
    if not os.path.exists(filename):
        return [f"File {filename} not found."]
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
            return lines[-n:]
    except Exception as e:
        return [f"Error reading {filename}: {str(e)}"]

# Main Loop
if auto_refresh:
    while True:
        with log_placeholder.container():
            lines = read_tail(SERVER_LOG)
            st.code("".join(lines), language="log")
            
        with notes_placeholder.container():
            lines = read_tail(USER_NOTES)
            st.code("".join(lines), language="text")
            
        time.sleep(refresh_rate)
else:
    with log_placeholder.container():
        lines = read_tail(SERVER_LOG)
        st.code("".join(lines), language="log")
        
    with notes_placeholder.container():
        lines = read_tail(USER_NOTES)
        st.code("".join(lines), language="text")
