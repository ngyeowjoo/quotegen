import streamlit as st

st.set_page_config(page_title="BPO Quote Generator", page_icon="💼", layout="wide")

st.title("💼 BPO Quote Generator")
st.caption("Prototype — pricing data lives in data/master_data.xlsx, checked into this repo")

st.markdown("""
### What's working
- **Quote Builder** (sidebar) — build a quote with agent + auto-added support staff
  roles, live-priced with an engine validated to the cent against the original Excel.
- Every dollar figure pulled from the database is a **reference default** — base
  salary, margin %, and penalty % are all editable per line item.
- A full **calculation breakdown** is shown for every line item.
- **Download the finished quote** as an Excel file.

### How master data works in this prototype
All country, salary, overhead, FX, tax, and support-ratio data lives in one file:
`data/master_data.xlsx`. To update it (new salary bands, new country, new FX
rate): edit that file and push to the repo — Streamlit Cloud picks up the
change automatically on the next deploy/refresh.

### Not in this prototype (yet)
- Login / role-based permissions — anyone with the app link can build quotes
  and could, in principle, edit `master_data.xlsx` if they have repo access.
  Fine for a demo; add real auth (e.g. Supabase) before this goes to production
  with real client pricing.
- Persistent quote history — quotes aren't saved centrally; use the **Download
  as Excel** button on a finished quote to keep a copy.
""")
