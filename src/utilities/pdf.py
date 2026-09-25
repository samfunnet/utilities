from __future__ import annotations
import sys
import shutil
import subprocess
from pathlib import Path


def _find_libreoffice() -> str:
    """Finner stien til LibreOffice på tvers av Linux, macOS og Windows."""
    # 1. Sjekk om libreoffice eller soffice ligger i PATH (vanligst på Linux)
    for cmd in ("libreoffice", "soffice"):
        path = shutil.which(cmd)
        if path:
            return path

    # 2. Vanlige stier på macOS
    mac_paths = [
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("~/Applications/LibreOffice.app/Contents/MacOS/soffice").expanduser(),
    ]
    for p in mac_paths:
        if p.exists():
            return str(p)

    # 3. Vanlige stier på Windows
    win_paths = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]
    for p in win_paths:
        if p.exists():
            return str(p)

    raise RuntimeError(
        "Fant ikke LibreOffice. For å konvertere dokumenter til PDF må LibreOffice "
        "være installert på maskinen."
    )


def convert_to_pdf(
    files: str | Path | list[str | Path],
    output_dir: str | Path | None = None,
    timeout: int = 120,
) -> list[Path]:
    """Konverterer ett eller flere dokumenter (docx, xlsx, pptx, etc.) til PDF

    ved hjelp av headless LibreOffice.

    :param files: Én filsti eller en liste med filstier.
    :param output_dir: Mappe hvor PDF-ene skal lagres (standard: samme mappe som kildefilen).
    :param timeout: Maksimal ventetid i sekunder per konvertering.
    :return: Liste med Path-objekter til de genererte PDF-filene.
    :raises RuntimeError: Hvis LibreOffice mangler eller konverteringen feilet.
    :raises FileNotFoundError: Hvis noen av kildefilene ikke finnes.
    """
    libreoffice_cmd = _find_libreoffice()

    # Normaliser til en liste med Path-objekter
    if isinstance(files, (str, Path)):
        file_list = [Path(files).expanduser().resolve()]
    else:
        file_list = [Path(f).expanduser().resolve() for f in files]

    if not file_list:
        return []

    # Verifiser at kildefilene finnes
    for f in file_list:
        if not f.exists():
            raise FileNotFoundError(f"Filen finnes ikke: {f}")

    generated_pdfs: list[Path] = []

    # Hvis output_dir er oppgitt, konverterer vi alt dit
    if output_dir:
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            libreoffice_cmd,
            "--headless",
            "--convert-to",
            "pdf",
            *[str(f) for f in file_list],
            "--outdir",
            str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            raise RuntimeError(f"Konvertering feilet:\n{res.stderr}")

        for f in file_list:
            pdf_path = out_path / f"{f.stem}.pdf"
            if pdf_path.exists():
                generated_pdfs.append(pdf_path)
    else:
        # Grupper filer etter foreldremappe for rask felles-kjøring per mappe
        from collections import defaultdict

        grouped: dict[Path, list[Path]] = defaultdict(list)
        for f in file_list:
            grouped[f.parent].append(f)

        for folder, group_files in grouped.items():
            cmd = [
                libreoffice_cmd,
                "--headless",
                "--convert-to",
                "pdf",
                *[str(f) for f in group_files],
                "--outdir",
                str(folder),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode != 0:
                raise RuntimeError(
                    f"Konvertering feilet for filer i {folder}:\n{res.stderr}"
                )

            for f in group_files:
                pdf_path = folder / f"{f.stem}.pdf"
                if pdf_path.exists():
                    generated_pdfs.append(pdf_path)

    return generated_pdfs


def _notify(
    title: str, message: str, icon: str | None = None, urgency: str = "normal"
) -> None:
    """Sender skrivebordsvarsel med notify-send hvis tilgjengelig, ellers print til terminal."""
    if shutil.which("notify-send"):
        cmd = ["notify-send", "-u", urgency]
        if icon:
            cmd.extend(["-i", icon])
        cmd.extend([title, message])
        subprocess.run(cmd, check=False)
    else:
        print(f"[{title}] {message}")


def cli_convert_to_pdf() -> None:
    """CLI-inngangspunkt (erstatter bash-skriptet for Yazi og terminalen)."""
    args = sys.argv[1:]

    # 1. Valider at minst én fil ble sendt inn
    if not args:
        _notify("Feil", "Ingen filer valgt for konvertering.", urgency="critical")
        sys.exit(1)

    total = len(args)

    # 2. Varsle om start
    if total == 1:
        filnavn = Path(args[0]).name
        _notify(
            "Konverterer...",
            f"Gjør om {filnavn} til PDF...",
            icon="x-office-document",
        )
    else:
        _notify(
            "Batch-konvertering",
            f"Starter konvertering av {total} filer til PDF...",
            icon="x-office-document",
        )

    # 3. Kjør konvertering med feilhåndtering
    try:
        genererte_pdf = convert_to_pdf(args)

        # 4. Varsle om fullført
        if total == 1 and genererte_pdf:
            _notify(
                "PDF Opprettet",
                f"Lagret som:\n{genererte_pdf[0].name}",
                icon="document-save",
            )
        else:
            _notify(
                "Fullført!",
                f"{len(genererte_pdf)} av {total} filer ble konvertert til PDF.",
                icon="document-save",
            )
    except Exception as e:
        _notify(
            "Feil under konvertering",
            str(e),
            icon="dialog-error",
            urgency="critical",
        )
        sys.exit(1)


if __name__ == "__main__":
    cli_convert_to_pdf()
