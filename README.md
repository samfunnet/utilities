# Utilities

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
    fnr_detaljer,
    generate_qrcode,
    generate_qrcode_mikaelkirken,
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
