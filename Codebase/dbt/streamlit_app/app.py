"""Minimal Streamlit app for TED AI (skeleton).

Run with `streamlit run app.py` from the `streamlit_app` folder.
"""
import streamlit as st

st.set_page_config(page_title="TED AI", layout="centered")

st.title("TED AI — Demo")

st.write("This is a minimal skeleton for the Streamlit UI. Add components in `components/`.")

if st.button("Run sample embed"):
    st.write("Embedding and search will run here in the full app.")
