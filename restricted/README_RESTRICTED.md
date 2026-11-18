# Restricted Evidence Package — NOT FOR PUBLIC RELEASE

This directory contains actual operational identifiers, source counts, code mappings, reporting details and generated outputs. It **must not** be uploaded into the public Overleaf project or the public GitHub repository. Distribute only through an authorized, access-controlled Centre/FedEx storage location. The original uploaded Excel/XLSB snapshots are **not** bundled here; authorized staff must obtain the exact hashed originals separately.

## What was actually executed
A read-only arithmetic audit directly parsed the two XLSX snapshots and produced `audit_summary.json`, the fixed population ledger, and the destination/service/origin/week reconciliation CSV files. `audit_compute.py` uses standard library XML/ZIP parsing and its own fixed date window and operational mapping constants. `make_restricted_figure.py` generated the corrected same-population restricted figure. `verify_audit.py` checked input conservation, output hashes and cross-grain additive package totals. All these local consistency checks passed. A separate fresh-directory run reproduced the seven audit output hashes byte-for-byte using the same environment and operator. The original historical end-to-end canonicalization, QA record-level intersections, and figure-generation workflow were **not** independently reconstructed or certified.

## Exact reproduction commands
From a directory containing the three approved snapshots and the scripts:

```bash
python audit_compute.py --weekly "Weekly 202201-202412(1)(1).xlsx" --aug "Aug actuals with DOM (1)(1).xlsx" --xlsb "Fedex data version 1 (1)(1).xlsb" --out restricted_evidence
python verify_audit.py --out restricted_evidence
python make_restricted_figure.py --out restricted_evidence
```

For figure generation install `matplotlib==3.10.8` to best match this first execution. The numeric audit uses Python 3.13.5 standard library only. For authoring PDF: `pdflatex restricted.tex` (the figure PDF must be alongside the TeX source). The public `main.tex` is self-contained with no external figures.

The repository at `https://github.com/brpuneet898/fedex-supply-chain` was found publicly visible and includes embedded operational code mappings. The data owner/Centre should assess authorization and any past dissemination separately; this package has not been pushed to that repository.

## Unresolved external signoffs
- Centre/FedEx written disclosure clearance for the exact proposed public PDF and any supplements.
- Authorized institutional location and custodian confirmation for the pinned source snapshots.
- Independent second-operator rerun with hash comparison and, if desired, an end-to-end Bronze workflow execution.
- Source owners' billed-weight unit/measure definitions, time allocation, and the exact meaning of the ambiguous origin code.
- Centre confirmation of sanctioned project-title wording; final author approval and journal-positioning decision.

The response matrix uses only the professor's three permitted statuses. It does **not** falsely mark external approvals as completed.
