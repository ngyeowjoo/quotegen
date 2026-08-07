"""
Supabase client for the app. Uses the public/anon (publishable) key only --
this is safe to embed in a client app because Row Level Security policies on
the Supabase side (see supabase/schema.sql) enforce who can read/write what.
Never put the service_role key here.

Reads config from Streamlit secrets (preferred, for Streamlit Cloud) or
environment variables (for local dev).
"""
import os
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
    key = st.secrets.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_ANON_KEY"))
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL / SUPABASE_ANON_KEY. Set them in "
            ".streamlit/secrets.toml (see .streamlit/secrets.toml.example)."
        )
    return create_client(url, key)
