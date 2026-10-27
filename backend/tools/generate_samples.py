"""Write the fictional sample documents used by the demo to ../samples.

Usage (from backend/):  python -m tools.generate_samples
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import REPO_ROOT
from tools import sample_docs

SAMPLE_COMPANY = {
    "_note": "SAMPLE company profile - fictional details for the TenderFlow demo.",
    "name": "Demo Supplier (Pvt.) Ltd. - sample company",
    "address": "Office 12, Sample Trade Centre, Sample City",
    "phone": "+00 000 0000000",
    "email": "sales@demo-supplier.example",
    "registration": "SAMPLE-REG-0001",
    "prepared_by": "Sales team (sample)",
}


def main(out_dir: Path | None = None) -> list[Path]:
    out = out_dir or (REPO_ROOT / "samples")
    out.mkdir(parents=True, exist_ok=True)
    written = [
        sample_docs.build_tender_pdf(out / "sample_tender_network_equipment.pdf"),
        sample_docs.build_tender_docx(out / "sample_tender_network_equipment.docx"),
        sample_docs.build_template_docx(out / "sample_quotation_template.docx"),
        sample_docs.build_template_xlsx(out / "sample_quotation_template.xlsx"),
        sample_docs.build_price_list_xlsx(out / "sample_price_list.xlsx"),
        sample_docs.build_price_list_csv(out / "sample_price_list.csv"),
    ]
    company = out / "sample_company_profile.json"
    company.write_text(json.dumps(SAMPLE_COMPANY, indent=2) + "\n", encoding="utf-8")
    written.append(company)
    return written


if __name__ == "__main__":
    for path in main():
        print(f"wrote {path.relative_to(REPO_ROOT)}")
