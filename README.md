# Utilities

A shared Python library containing common tools and utilities for repetitive automation workflows. Managed with **[uv](https://docs.astral.sh/uv/)**.

---

## 1. Installation

### Add to another project using `uv`

Install the latest version directly from GitHub:

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
    generate_qrcode,
    generate_qrcode_mikaelkirken,
    get_newest_file,
    merge_odt,
)
```

---

### 2.1 File Utilities (`get_newest_file`)

Locates the most recently modified file in a directory matching a wildcard pattern or regular expression.

* **Cross-platform**: Automatically resolves `~` (home directory) and paths across Windows, macOS, and Linux.
* **Flexible matching**: Supports shell wildcards/globs (`Export*.xlsx`) and regular expressions (`r"^Export_\d+\.xlsx$"`).

```python
from utilities import get_newest_file

# 1. Using wildcard (glob) pattern
latest_export = get_newest_file("~/syncthing/Downloads", "Export*.xlsx")
if latest_export:
    print(f"Path: {latest_export}")
    print(f"Filename: {latest_export.name}")

# 2. Using Regular Expressions (regex)
latest_invoice = get_newest_file(
    folder_path="~/Documents/Invoices",
    pattern=r"^Faktura_\d{4}-\d{2}\.pdf$",
    is_regex=True,
)
```

---

### 2.2 PDF Conversion (`convert_to_pdf`)

Converts Word, Excel, PowerPoint, ODT, and ODS documents to PDF using headless LibreOffice.

> **Requirement:** LibreOffice must be installed on the machine (`apt install libreoffice`, `brew install libreoffice`, or installed on Windows).

```python
from utilities import convert_to_pdf, get_newest_file

# Example A: Convert the newest export file to PDF
latest_excel = get_newest_file("~/syncthing/Downloads", "Export*.xlsx")
if latest_excel:
    pdf_files = convert_to_pdf(latest_excel)
    print(f"Created: {pdf_files[0]}")

# Example B: Batch-convert multiple documents to a specific archive folder
documents = ["rapport.docx", "budsjett.xlsx"]
output_folder = "~/Documents/PDF_Archive"
pdf_files = convert_to_pdf(documents, output_dir=output_folder)
```

---

### 2.3 Mail Merge Engine (`merge_odt`)

Merges LibreOffice `.odt` templates with data from an Excel spreadsheet (`.xlsx`). Reuses `get_newest_file` to find the newest spreadsheet and `convert_to_pdf` for fast batch PDF generation.

* **Template tags:** Supports `<Column>`, `«Column»`, `{{ Column }}`, or standard LibreOffice database fields (`F4`).
* **Safe formatting:** Missing columns in the spreadsheet will not cause crashes.
* **Batch or single document:** Can output individual letters or combine everything into one document.

```python
from utilities import merge_odt

# Example A: Standard merge (auto-detects newest Export*.xlsx in Downloads)
generated_files = merge_odt(
    template_path="~/Templates/WelcomeLetter.odt",
    output_dir="~/Documents/Letters",
    name_format="Letter_{i}_{Fornavn}_{Etternavn}",
    output_format="both",  # 'both', 'pdf', or 'odt'
)

# Example B: Bulk print mode (combine all recipients into one PDF)
combined_pdf = merge_odt(
    template_path="~/Templates/MemberLetter.odt",
    output_dir="~/Documents/Print",
    output_format="pdf",
    combine=True,
)
```

---

### 2.4 QR Code Utilities (`generate_qrcode`)

Generates high-resolution QR codes with optional church branding and styling.

```python
from utilities import generate_qrcode, generate_qrcode_mikaelkirken

# 1. Standard QR Code
img = generate_qrcode("https://mikaelkirken.no")
img.save("qr.png")

# 2. Mikaelkirken branded QR Code
img_branded = generate_qrcode_mikaelkirken("123456", "1234.56.78903")
img_branded.save("mikaelkirken_qr.png")
```

---

## 3. Command-Line Tools (CLI)

The package provides CLI entry points configured in `pyproject.toml`.

### 3.1 `convert-pdf` (Batch Office-to-PDF Converter)

Converts one or multiple documents to PDF and triggers native desktop notifications (`notify-send`) when finished.

```bash
# Run locally within the repository:
uv run convert-pdf document1.docx document2.xlsx
```

#### Run On-Demand via `uvx` (No Local Clone Required)

```bash
# Run pinned to a specific commit:
uvx --from git+https://github.com/samfunnet/utilities@<commit-hash> convert-pdf file1.xlsx
```

#### Desktop Integration (MenuLibre / File Manager "Open With")

In MenuLibre, set the `Exec` command to:

```text
/home/jviksaas/.local/bin/uvx --from git+https://github.com/samfunnet/utilities@<commit-hash> convert-pdf %F
```

---

### 3.2 `merge-odt` (Universal Mail Merge Engine)

Merges a selected `.odt` template with the newest Excel export from your downloads folder.

```bash
# Run locally with options:
uv run merge-odt -t "Mal.odt" -o "~/diverse" -n "{Etternavn}_{Fornavn}"
```

#### Desktop Integration (MenuLibre / Right-Click on `.odt` files)

Associate with the `.odt` mimetype (`application/vnd.oasis.opendocument.text`):

```text
# Standard individual letters:
/home/jviksaas/.local/bin/uvx --from git+https://github.com/samfunnet/utilities@<commit-hash> merge-odt %F

# With custom output directory and custom filename format:
/home/jviksaas/.local/bin/uvx --from git+https://github.com/samfunnet/utilities@<commit-hash> merge-odt -o ~/diverse -n "Medlem_{Medlemsnummer}_{Etternavn}" %F

# Bulk print: Combine all recipients into one single PDF:
/home/jviksaas/.local/bin/uvx --from git+https://github.com/samfunnet/utilities@<commit-hash> merge-odt --combine -f pdf -o ~/diverse %F
```

---

### 3.3 `generate-qr`

Generates a QR code directly from the command line:

```bash
uv run generate-qr "123456" "1234.56.78903"
```

---

## 4. Project Structure

```text
utilities/
├── pyproject.toml
├── README.md
├── src/
│   └── utilities/
│       ├── __init__.py    # Exports all public utilities
│       ├── files.py       # File finding & filesystem utilities
│       ├── merge.py       # LibreOffice ODT + Excel mail merge engine
│       ├── pdf.py         # LibreOffice headless PDF converter & CLI
│       └── qr.py          # QR code generation & CLI
```

### Adding New Utilities

1. **Create a new module** in `src/utilities/` (e.g. `src/utilities/dates.py`).
2. **Export the functions** in `src/utilities/__init__.py`.
3. If exposing a CLI command, register it under `[project.scripts]` in `pyproject.toml`.
4. Run `uv sync` to update the environment.

---

## 5. Development

Clone and install dependencies:

```bash
git clone https://github.com/samfunnet/utilities.git
cd utilities
uv sync
```
