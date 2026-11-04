 Utilities

A shared Python library containing common tools and utilities for repetitive automation workflows. Managed with `uv`.

---

## 1. Installation

Add to another project using `uv`:

```bash
uv add git+https://github.com/samfunnet/utilities
```

To lock the installation to a specific tag or commit hash:

```bash
uv add git+https://github.com/samfunnet/utilities@v0.2.0
# or
uv add git+https://github.com/samfunnet/utilities@a1b2c3d
```

---

## 2. Python API

All primary functions can be imported directly from the top-level `utilities` package:

```python
from utilities import (
    convert_to_pdf,
    create_email_draft,
    find_email,
    find_emails,
    fnr_detaljer,
    generate_qrcode,
    generate_qrcode_mikaelkirken,
    get_gmail,
    get_newest_file,
    merge_odt,
)
```

---

### 2.1 File Utilities

#### `get_newest_file(directory, pattern="*") -> Path | None`

Finds the most recently modified file in a directory matching a glob pattern.

```python
from pathlib import Path
from utilities import get_newest_file

latest = get_newest_file(Path("/path/to/downloads"), "*.xlsx")
if latest:
    print(f"Latest file: {latest}")
```

---

### 2.2 PDF Conversion

#### `convert_to_pdf(input_file, output_file=None, timeout=60) -> Path`

Converts document formats supported by LibreOffice (ODT, DOCX, XLSX, etc.) to PDF using a headless LibreOffice instance.

```python
from pathlib import Path
from utilities import convert_to_pdf

pdf = convert_to_pdf(Path("report.odt"))
# Creates report.pdf in the same directory
```

---

### 2.3 Mail Merge Engine

#### `merge_odt(template_path, data_source, output_dir, name_template=None, generate_pdf=False, ...)`

Performs mail merge operations using LibreOffice ODT templates and tabular data sources (Excel `.xlsx` or CSV). Uses Jinja-like syntax (`{{ FieldName }}`) inside the template document.

```python
from pathlib import Path
from utilities import merge_odt

created_files = merge_odt(
    template_path=Path("brev_mal.odt"),
    data_source=Path("mottakere.xlsx"),
    output_dir=Path("./utsendelser"),
    name_template="{Etternavn}_{Fornavn}",
    generate_pdf=True,
)
```

---

### 2.4 QR Code Utilities

#### `generate_qrcode(data, output_file, scale=10, border=4, fill_color="black", back_color="white") -> Path`

Generates standard QR codes.

```python
from pathlib import Path
from utilities import generate_qrcode

generate_qrcode("https://mikaelkirken.no", Path("nettside.png"))
```

#### `generate_qrcode_mikaelkirken(data, output_file, scale=10) -> Path`

Generates Mikaelkirken-branded QR codes using official colors (#970000 on warm background).

```python
from pathlib import Path
from utilities import generate_qrcode_mikaelkirken

generate_qrcode_mikaelkirken("https://mikaelkirken.no", Path("mikaelkirken.png"))
```

---

### 2.5 Norwegian Identity Numbers (Fødselsnummer)

#### `fnr_detaljer(fnr_kolonne="Fødselsnummer") -> list[pl.Expr]`

Returns composable Polars expressions that parse Norwegian identity numbers (both standard fødselsnummer and D-nummer) into birth date and gender.

- **`fodsels_dato` (`pl.Date`)**: Resolves the full 4-digit birth year using official Skatteetaten century rules (1800s, 1900s, 2000s) based on the individual digits (siffer 7–9), and automatically adjusts D-numbers. Invalid dates resolve to `null` safely.
- **`kjønn` (`pl.String`)**: Determines gender (`"Mann"` / `"Kvinne"`) from the 9th digit (odd = male, even = female).

```python
import polars as pl
from utilities import fnr_detaljer

# Sample data (standard fnr, 2000s fnr, and D-number)
df = pl.DataFrame({
    "Navn": ["Kari Nordmann", "Ola Nordmann", "D-nummer Eksempel"],
    "Fødselsnummer": ["15038512346", "01010561234", "45089212345"],
})

# Derive 'fodsels_dato' and 'kjønn'
df = df.with_columns(fnr_detaljer("Fødselsnummer"))
print(df)
```

**Output:**

```text
shape: (3, 4)
┌───────────────────┬───────────────┬──────────────┬────────┐
│ Navn              ┆ Fødselsnummer ┆ fodsels_dato ┆ kjønn  │
│ ---               ┆ ---           ┆ ---          ┆ ---    │
│ str               ┆ str           ┆ date         ┆ str    │
╞═══════════════════╪═══════════════╪══════════════╪════════╡
│ Kari Nordmann     ┆ 15038512346   ┆ 1985-03-15   ┆ Kvinne │
│ Ola Nordmann      ┆ 01010561234   ┆ 2005-01-01   ┆ Mann   │
│ D-nummer Eksempel ┆ 45089212345   ┆ 1992-08-05   ┆ Mann   │
└───────────────────┴───────────────┴──────────────┴────────┘
```

---

### 2.6 Gmail Utilities

Integrates with Gmail via `simplegmail` to search messages, create drafts, and send emails directly.

#### Authentication & Setup

Authentication relies on Google OAuth 2.0. By default, credentials are expected in:

```text
~/.config/credentials/gmail/
├── client_secret.json
└── gmail_token.json  (generated automatically after first run)
```

1. **Google Cloud Console Setup:**
   - Enable the **Gmail API** in your Google Cloud project.
   - Configure the **OAuth Consent Screen** (User type: Internal for Workspace, or External with test users added).
   - Create credentials for **OAuth 2.0 Client ID** with Application type set to **Desktop app**.
   - Download the client secret JSON file and save it as:
     `~/.config/credentials/gmail/client_secret.json`

2. **First-time Authentication:**
   - The first time any Gmail function (`get_gmail()`, `create_email_draft()`, or `send_email()`) runs without an existing token, `simplegmail` opens a browser window (or prints an authorization link) asking you to log in and approve permissions.
   - Once approved, `gmail_token.json` is created automatically in the same folder.
   - All subsequent executions reuse this token silently without user interaction.

3. **Custom Directory:**
   - Pass a custom path using `get_gmail(creds_dir=...)` if you want to store credentials elsewhere, or pass a pre-authenticated `client` into any of the email functions.

---

#### `get_gmail(creds_dir=None) -> Gmail`

Returns an authenticated `simplegmail.Gmail` client. Checks `DEFAULT_CREDS_DIR` (`~/.config/credentials/gmail/`) by default.

```python
from utilities import get_gmail

client = get_gmail()
```

---

#### `find_emails(query=None, sender=None, subject=None, label=None, unread_only=False, max_results=None, client=None) -> list[Message]`

Searches messages matching criteria or a raw Gmail search string. Automatically builds a query if specific arguments (`sender`, `subject`, `label`, `unread_only`) are provided.

```python
from utilities import find_emails

# Search by specific filter
messages = find_emails(sender="noreply@example.com", unread_only=True)

# Or using raw Gmail query syntax
messages = find_emails(query="has:attachment newer_than:2d")
for msg in messages:
    print(msg.subject, msg.date)
```

---

#### `find_email(query=None, sender=None, subject=None, label=None, unread_only=False, client=None) -> Message | None`

Convenience function returning only the single newest email matching the criteria, or `None` if no messages match.

```python
from utilities import find_email

msg = find_email(subject="Invoice", unread_only=True)
if msg:
    print(f"Latest invoice ID: {msg.id}")
```

---

#### `create_email_draft(to, subject, body_html=None, body_text=None, attachments=None, sender="me", cc=None, bcc=None, signature=False, client=None) -> EmailDraft`

Creates a draft email in Gmail without sending it immediately. Returns an `EmailDraft` object where both dict indexing (`draft['id']`) and attribute access (`draft.id`) work.

- **`to`**: Recipient email address (`str`) or list of recipients (`Sequence[stri`).
- **`attachments`**: Optional list of files as `Path` objects or path strings (`str`).
- **`sender`**: Defaults to `"me"` (the authenticated user).
- **`cc` / `bcc`**: Optional recipient(s) as `str` or `list[str]`.
- **`signature`**: Appends your Gmail signature if set to `True` (default `False`).

```python
from pathlib import Path
from utilities import create_email_draft

SENDER = '"Mikaelkirken, Kristensamfunnet i hovedstaden" <post@mikaelkirken.no>'


draft = create_email_draft(
    sender=SENDER,
    to="colleague@example.com",
    subject="Monthly Report (Draft)",
    body_html="<p>Hi,</p><p>Please review the attached report draft.</p>",
    body_text="Hi, please review the attached report draft.",
    attachments=[Path("./reports/monthly.pdf")],
)

print(f"Draft created with ID: {draft.id}")
```

---

#### `send_email(to, subject, body_html=None, body_text=None, attachments=None, sender="me", cc=None, bcc=None, signature=False, reply_to=None, client=None) -> Message`

Directly sends an email via Gmail. Returns the sent `simplegmail.message.Message` object.

- **`to`**: Recipient email address (`str`) or list of recipients (`Sequence[str]`).
- **`attachments`**: Optional list of files as `Path` objects or path strings (`str`).
- **`sender`**: Defaults to `"me"` (the authenticated user).
- **`cc` / `bcc`**: Optional recipient(s) as `str` or `list[str]`.
- **`signature`**: Appends your Gmail signature if set to `True` (default `False`).
- **`reply_to`**: Optional `Message` object to reply within an existing Gmail thread.

```python
from pathlib import Path
from utilities import send_email

SENDER = '"Mikaelkirken, Kristensamfunnet i hovedstaden" <post@mikaelkirken.no>'

msg = send_email(
    sender=SENDER,
    to=["alice@example.com", "bob@example.com"],
    subject="Project Status Update",
    body_html="<h1>Status Update</h1><p>The project is on track!</p>",
    body_text="Status Update: The project is on track!",
    attachments=[Path("./docs/overview.pdf")],
    cc="manager@example.com",
)

print(f"Email sent with ID: {msg.id}")
```

---

## 3. Command-Line Tools (CLI)

The library exposes standard command-line entry points.

### 3.1 `convert-pdf`

Convert documents directly from the terminal:

```bash
convert-pdf document.odt
convert-pdf document.docx --output /path/to/output.pdf
```

### 3.2 `merge-odt`

Run mail merge tasks without writing Python code:

```bash
merge-odt mal.odt data.xlsx --pdf --output-dir ./utsendelser
```

---

## Requirements

- Python >= 3.12
- LibreOffice (required for `convert_to_pdf` and PDF generation in `merge_odt`)
