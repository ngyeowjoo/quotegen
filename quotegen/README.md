# BPO Quote Generator

Web-based replacement for the Excel Quote Generator.

## Status: Phase 1 (local build, pre-database)

- [x] Master data extracted from source Excel → `data/*.json`
- [x] Pricing engine ported and validated to the cent against real Excel output → `engine/pricing.py`, `tests/test_pricing.py`
- [ ] Supabase schema + auth + country-scoped RBAC
- [ ] Streamlit quote builder UI (multi-role, multi-LOB)
- [ ] Quote storage, history, export (PDF/Excel)
- [ ] Admin pages: HR (salary matrix), Finance (overheads/FX/tax)

## Run tests

```
pip install -r requirements.txt
python3 tests/test_pricing.py
```

## Run the app (once Supabase is wired up)

```
streamlit run app/Home.py
```

## Project structure

```
engine/pricing.py       - core calc engine (pure Python, no I/O)
scripts_extract_data.py - pulls master data from source Excel into data/*.json
data/                    - extracted master data (drivers, salary matrix, overheads, FX, tax, campaign types)
app/                     - Streamlit UI (multi-page)
tests/                   - validation tests against real Excel ground truth
```

## Open items to confirm with Finance/HR before go-live

The following per-role figures matched the ground-truth Excel example but their
exact source cells in the workbook weren't uniquely labeled — need confirmation:

- `hiring_cost_flat_lc` (MX1 col AE "TOTAL HIRING") — appears to be a flat per-role amount
- `cash_benefit_1` (MX1 col N, ~$86.66 in the SG example) — extra comp bucket
- `amortised_severance` (MX1 col Y, ~$166.67 in the SG example) — likely a monthly amortisation of an annual severance provision
