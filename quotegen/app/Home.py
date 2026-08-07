import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from app.auth import require_login, current_user, current_role, logout

st.set_page_config(page_title="BPO Quote Generator", page_icon="💼", layout="wide")

require_login()

user = current_user()
role = current_role()

with st.sidebar:
    st.caption(f"Signed in as **{user.email}**")
    st.caption(f"Role: **{role or 'unassigned'}**")
    if st.button("Sign out"):
        logout()

st.title("💼 BPO Quote Generator")
st.caption("Web replacement for the Excel Quote Generator — connected to Supabase")

st.markdown("""
### What's working now
- **Login / roles** — Supabase Auth, with Admin / Finance / HR / Sales roles and
  country-scoped edit permissions enforced by database-level Row Level Security.
- **Quote Builder** (sidebar) — build a quote for one or more roles using live
  master data (31 cities, 8 campaign types) and a pricing engine validated to
  the cent against the original Excel.

### Still to build
- Quote persistence (save/reopen quotes) — coming next.
- HR / Finance master-data admin screens.
- PDF/Excel export of a finished quote.

### New accounts
New sign-ups default to the **Sales** role (can build quotes, can't edit master
data). An Admin needs to promote Finance/HR accounts and grant country access
— see `supabase/schema.sql` for the `user_profiles` / `user_country_access`
tables, editable from the Supabase Table Editor for now.
""")
