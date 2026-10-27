# Security policy

TenderFlow is a **hackathon prototype**. It has not had a security audit and is not intended to be exposed to the
internet or used with confidential tenders in production.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Contact the maintainers privately (add the team's
contact address here before publishing the repository) with:

- a description of the problem and its impact,
- steps to reproduce (use the fictional sample files, never a real confidential document),
- the version / commit you tested.

We aim to acknowledge reports within a few days. Please give us reasonable time to fix the issue before disclosure.

## Never commit

- `.env` files, API keys, tokens, passwords or certificates (`.env.example` holds placeholders only),
- real tender documents, private quotations, price lists or customer data,
- anything under `backend/data/` (uploads, exports and project files).

`python scripts/check_secrets.py` scans the repository for common secret patterns before you push.

## What the prototype does to reduce risk

- Upload allow-lists per document role, file-signature and OOXML structure checks, size limit, zip-bomb guard.
- Files stored under generated IDs; user filenames are sanitised and only displayed.
- IDs in URLs are validated against strict patterns, so requests cannot reach arbitrary paths.
- Uploaded content is parsed, never executed; LibreOffice (for PDF) runs headless with a throw-away profile.
- Document text is treated as untrusted data; instruction-like text is flagged and never acted on.
- No document content is logged; error responses never contain paths, stack traces or environment values.
- The optional AI key is read from the environment only and never returned by the API.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) on every response.

## Known limitations

- No authentication or authorisation: anyone who can reach the backend can read and delete projects. Run it on
  `localhost` only.
- Parsing relies on third-party libraries (pdfplumber/pdfminer, python-docx, openpyxl) that may have their own
  vulnerabilities with malicious files. Keep dependencies updated.
- The prompt-injection detector is a basic pattern check, not a guarantee.

More detail: [docs/SECURITY_PRIVACY.md](docs/SECURITY_PRIVACY.md).
