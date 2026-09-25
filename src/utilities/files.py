from __future__ import annotations

import fnmatch
import re
from pathlib import Path


def get_newest_file(
    folder_path: str | Path | None = None,
    pattern: str | None = None,
    *,
    is_regex: bool = False,
    case_sensitive: bool = False,
    recursive: bool = False,
    folderPath: str | Path | None = None,
    fileNameRegx: str | None = None,
) -> Path | None:
    """Henter den nyeste filen i en mappe basert på et filnavnmønster.

    Støtter både vanlige wildcard-mønstre (f.eks. 'Eksport *.xlsx') og
    regulære uttrykk (regex). Fungerer på tvers av Windows, macOS og Linux.

    :param folder_path: Sti til mappen (støtter f.eks. '~/Downloads').
    :param pattern: Filnavnmønster (wildcard eller regex).
    :param is_regex: Sett til True hvis mønsteret skal tolkes strengt som regex.
    :param case_sensitive: Om søket skal skille mellom store og små bokstaver (standard: False).
    :param recursive: Om det også skal søkes i undermapper (standard: False).
    :param folderPath: Alias for folder_path (camelCase-kompatibilitet).
    :param fileNameRegx: Alias for pattern (camelCase-kompatibilitet).
    :return: Path-objekt til nyeste fil, eller None hvis ingen fil matcher.
    :raises FileNotFoundError: Dersom oppgitt mappe ikke finnes.
    :raises NotADirectoryError: Dersom stien ikke er en mappe.
    """
    # Støtt både snake_case og camelCase argumenter
    resolved_folder = folderPath if folderPath is not None else folder_path
    resolved_pattern = fileNameRegx if fileNameRegx is not None else pattern

    if resolved_folder is None:
        raise ValueError("Mappesti (folder_path / folderPath) må oppgis.")

    if resolved_pattern is None:
        resolved_pattern = "*"

    # Håndter ~ (hjemmemappe) og konverter til plattformuavhengig Path
    target_dir = Path(resolved_folder).expanduser().resolve()

    if not target_dir.exists():
        raise FileNotFoundError(f"Mappen finnes ikke: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Stien er ikke en mappe: {target_dir}")

    # Hent filer
    candidates = target_dir.rglob("*") if recursive else target_dir.iterdir()

    matching_files: list[Path] = []
    flags = 0 if case_sensitive else re.IGNORECASE

    for item in candidates:
        if not item.is_file():
            continue

        name = item.name

        if is_regex:
            if re.search(resolved_pattern, name, flags):
                matching_files.append(item)
        else:
            # 1. Prøv først med wildcard/glob (f.eks. "Eksport *.xlsx")
            if case_sensitive:
                matched = fnmatch.fnmatchcase(name, resolved_pattern)
            else:
                matched = fnmatch.fnmatchcase(name.lower(), resolved_pattern.lower())

            if matched:
                matching_files.append(item)
            else:
                # 2. Fallback: Hvis det ikke matchet som glob, test om det er et regex-uttrykk
                try:
                    if re.search(resolved_pattern, name, flags):
                        matching_files.append(item)
                except re.error:
                    pass

    if not matching_files:
        return None

    # Returner filen som har nyest modifiseringstidspunkt (st_mtime)
    return max(matching_files, key=lambda f: f.stat().st_mtime)
