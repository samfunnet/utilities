# Utilities

A shared Python library containing common utilities for Mikaelkirken and related projects. Managed with **uv**.

---

## 1. Quick Setup: Add to Another Project

Whenever you create a new Python project (like `tidsskriftet-giroer`) and want to use these utilities, run **one** of the commands below inside your project folder:

### A. On your local computer (Recommended)

Connects directly to your local folder so changes take effect immediately:

```bash
uv add --editable /mnt/server/system-ssd/mount/dev/python/utilities
```

### B. On a server or another machine (From GitHub)

Fetches directly from the GitHub repository:

```bash
uv add git+https://github.com/samfunnet/utilities.git
```

---

## 2. Using in Python Code

Import the functions directly from the package:

```python
from utilities import generate_qrcode, generate_qrcode_mikaelkirken

# 1. Mikaelkirken QR code (Purple color + embedded logo)
generate_qrcode_mikaelkirken(
    url="https://mikaelkirken.no/giro/101",
    output_file="giro_qr.svg",  # Optional, defaults to 'qrcode.svg'
)

# 2. Plain / Generic QR code (Black, no logo)
generate_qrcode(
    url="https://example.com",
    output_file="simple.svg",
)

# 3. Custom QR code (Custom color and your own logo)
generate_qrcode(
    url="https://example.com",
    png_image="path/to/custom-logo.png",
    color="#0055AA",
    output_file="custom.svg",
)
```

---

## 3. Using from the Command Line (CLI)

You can run the generator directly from the terminal inside any project where `utilities` is added.

### See all options and help

```bash
uv run generate-qr --help
```

### Examples

**1. Create a Mikaelkirken QR code (`-m`):**

```bash
uv run generate-qr "https://mikaelkirken.no/program" -m
```

**2. Create a Mikaelkirken QR code with a custom filename (`-o`):**

```bash
uv run generate-qr "https://mikaelkirken.no/giro/101" -m -o "giro-101.svg"
```

**3. Create a standard black QR code:**

```bash
uv run generate-qr "https://example.com" -o "simple.svg"
```

**4. Create a custom colored QR code (`-c`):**

```bash
uv run generate-qr "https://example.com" -c "#8D008C" -o "colored.svg"
```

---

## 4. How to Add New Functions Later

When you want to add new tools (for example PDF utilities, date helpers, etc.):

1. **Create a new file** in `src/utilities/`, e.g. `src/utilities/pdf.py`:

   ```python
   def create_giro_pdf(...) -> str:
       # your code here
       pass
   ```

2. **Export the function** in `src/utilities/__init__.py`:

   ```python
   from utilities.pdf import create_giro_pdf
   from utilities.qr import generate_qrcode, generate_qrcode_mikaelkirken

   __all__ = [
       "create_giro_pdf",
       "generate_qrcode",
       "generate_qrcode_mikaelkirken",
   ]
   ```

3. **Use it in your other projects**:

   ```python
   from utilities import create_giro_pdf
   ```
