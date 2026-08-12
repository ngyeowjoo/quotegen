# BPO Quote Generator (prototype)

Web-based replacement for the Excel Quote Generator. This version reads all
master data from `data/master_data.xlsx`, checked into this repo — no
database or auth setup required, good for a quick demo.

## Run locally

```
pip install -r requirements.txt
python3 tests/test_pricing.py     # validates pricing math against real Excel output
streamlit run app/Home.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. share.streamlit.io → Create app → point at this repo, main file `app/Home.py`.
3. Deploy. No secrets needed for this version.

## Updating master data

Edit `data/master_data.xlsx` directly (sheets: Drivers, BaseSalary, Overheads,
FXRates, TaxRates, CampaignTypes, SupportRatios, SpanRatios) and push to the
repo. The app re-reads it on next load.

To regenerate `master_data.xlsx` from the original source workbook (e.g. after
a big update), re-run:
```
python3 scripts_extract_data.py /path/to/Quote_Generator.xlsx
```
then re-run the small script that bundles `data/*.json` into `data/master_data.xlsx`
(ask Claude to regenerate this step, or see git history).

## Project structure

```
engine/pricing.py       - core calc engine (pure Python, no I/O), validated to the cent
data/master_data.xlsx   - all master data, editable directly
app/                     - Streamlit UI
tests/                   - validation tests against real Excel ground truth
```

## Known limitations (prototype stage)

- No login / role-based access control — anyone with the link can build quotes,
  and anyone with repo access can edit master data directly.
- Quotes aren't saved centrally — use the "Download as Excel" button on a
  finished quote to keep a copy.
- A few per-role cost inputs (hiring cost, two comp buckets) were calibrated to
  match one validated example — worth confirming exact source cells with
  Finance before this is used for real client pricing. See `tests/test_pricing.py`.
- Only Line of Business 1 (of 3 in the original workbook) and its support-ratio
  table are wired up so far.

## Path to production

When ready to move past demo stage: real auth + RBAC + persistent quote storage
(a hosted DB, e.g. Supabase) is a natural next step — ask Claude to wire it back
in; the pricing engine and UI won't need to change, just the data-access layer.
