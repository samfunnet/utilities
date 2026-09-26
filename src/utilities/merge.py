    from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import openpyxl

from utilities.files import get_newest_file
from utilities.pdf import _notify, convert_to_pdf


class SafeDict(dict):
    """Sørger for at manglende kolonner i malen ikke krasjer navneformateringen."""

    def __missing__(self, key: str) -> str:
        return ""


def _substitute_xml(xml_str: str, row_data: dict[str, Any]) -> str:
    """Erstatter flettefelter i LibreOffice content.xml med verdier fra raden."""

    # 1. Håndter LibreOffice databasefelter (<text:database-display ...>)
    def db_repl(match: re.Match) -> str:
        tag = match.group(0)
        kol_m = re.search(r'text:column-name="([^"]+)"', tag)
        if kol_m:
            kol_norm = kol_m.group(1).lower().replace(" ", "_")
            for k, v in row_data.items():
                if k.lower().replace(" ", "_") == kol_norm:
                    return html.escape(str(v))
        return tag

    xml_str = re.sub(
        r"<text:database-display\b[^>]*>.*?</text:database-display>",
        db_repl,
        xml_str,
    )

    # 2. Tekstkoder som <Kolonne>, «Kolonne», {{ Kolonne }}
    for k, v in row_data.items():
        v_esc = html.escape(str(v))
        for k_var in [k, k.replace(" ", "_")]:
            for tag in [f"<{k_var}>", f"&lt;{k_var}&gt;", f"«{k_var}»", f"{{{k_var}}}"]:
                xml_str = xml_str.replace(tag, v_esc)

    return xml_str


def _build_combined_xml(xml_mal: str, rader: list[dict[str, Any]]) -> str:
    """Syr sammen innholdet for alle rader med sideskift mellom hver person."""
    m = re.search(r"(<office:text\b[^>]*>)(.*?)(</office:text>)", xml_mal, re.DOTALL)
    if not m:
        return xml_mal

    start_tag, innhold, slutt_tag = m.group(1), m.group(2), m.group(3)

    prefiks = ""
    match_decls = re.search(r"^(.*?</text:sequence-decls>)(.*)$", innhold, re.DOTALL)
    if match_decls:
        prefiks = match_decls.group(1)
        kropp_mal = match_decls.group(2)
    else:
        match_forms = re.search(r"^(.*?</office:forms>)(.*)$", innhold, re.DOTALL)
        if match_forms:
            prefiks = match_forms.group(1)
            kropp_mal = match_forms.group(2)
        else:
            kropp_mal = innhold

    brevdeler = []
    for i, rad in enumerate(rader):
        brev_tekst = _substitute_xml(kropp_mal, rad)
        if i > 0:
            brevdeler.append('<text:p text:style-name="PB_MERGE"/>')
        brevdeler.append(brev_tekst)

    ny_tekst = prefiks + "".join(brevdeler)
    ny_xml = xml_mal[: m.start()] + start_tag + ny_tekst + slutt_tag + xml_mal[m.end() :]

    pb_stil = (
        '<style:style style:name="PB_MERGE" style:family="paragraph">'
        '<style:paragraph-properties fo:break-before="page" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:line-height="0%"/>'
        '<style:text-properties fo:font-size="1pt"/>'
        "</style:style>"
    )
    if "<office:automatic-styles>" in ny_xml:
        ny_xml = ny_xml.replace("<office:automatic-styles>", "<office:automatic-styles>" + pb_stil, 1)
    elif "<office:automatic-styles/>" in ny_xml:
        ny_xml = ny_xml.replace(
            "<office:automatic-styles/>",
            "<office:automatic-styles>" + pb_stil + "</office:automatic-styles>",
            1,
        )

    return ny_xml


def _write_odt(mal_filer: dict[str, bytes], xml_content: str, ut_sti: Path) -> None:
    """Pakker sammen en ny .odt-fil med oppdatert content.xml."""
    with zipfile.ZipFile(ut_sti, "w") as z:
        if "mimetype" in mal_filer:
            z.writestr("mimetype", mal_filer["mimetype"], compress_type=zipfile.ZIP_STORED)
        for fil, data in mal_filer.items():
            if fil == "mimetype":
                continue
            innhold = xml_content.encode("utf-8") if fil == "content.xml" else data
            z.writestr(fil, innhold, compress_type=zipfile.ZIP_DEFLATED)


def merge_odt(
    template_path: str | Path,
    excel_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    name_format: str = "Brev_{i}_{Fornavn}_{Etternavn}",
    pattern: str = "Export*.xlsx",
    output_format: str = "both",
    combine: bool = False,
    sheet_name: str | int | None = None,
    limit: int | None = None,
) -> list[Path]:
    """Hovedfunksjon for fletting av ODT-mal mot Excel-data."""
    mal_sti = Path(template_path).expanduser().resolve()
    if not mal_sti.exists():
        raise FileNotFoundError(f"Finner ikke mal-filen: {mal_sti}")

    if output_dir:
        ut_mappe = Path(output_dir).expanduser().resolve()
    else:
        ut_mappe = mal_sti.parent / "diverse"
    ut_mappe.mkdir(parents=True, exist_ok=True)

    # 1. Finn Excel-fil ved hjelp av get_newest_file()
    if excel_path:
        kilde_excel = Path(excel_path).expanduser().resolve()
    else:
        kilde_excel = get_newest_file("~/syncthing/Downloads", pattern)
        if not kilde_excel:
            kilde_excel = get_newest_file("~/Downloads", pattern)

    if not kilde_excel or not kilde_excel.exists():
        raise FileNotFoundError(f"Fant ingen Excel-fil som matcher '{pattern}' i Downloads.")

    print(f"📄 Excel-kilde: {kilde_excel.name}")
    print(f"📝 Mal:         {mal_sti.name}")
    print(f"📁 Lagres i:    {ut_mappe}")

    # 2. Les Excel-arket
    wb = openpyxl.load_workbook(kilde_excel, data_only=True)
    if sheet_name:
        sheet = wb[sheet_name] if isinstance(sheet_name, str) and sheet_name in wb.sheetnames else wb.worksheets[int(sheet_name) - 1]
    else:
        sheet = wb.active or wb.worksheets[0]

    headere = [str(c.value).strip() for c in sheet[1] if c.value is not None]
    rader: list[dict[str, Any]] = []
    for row in sheet.iter_rows(min_row=2, max_col=len(headere), values_only=True):
        if not any(row):
            continue
        rad_dict = {h: ("" if v is None else str(v).strip()) for h, v in zip(headere, row)}
        rader.append(rad_dict)

    if limit:
        rader = rader[:limit]

    if not rader:
        print("⚠️ Ingen rader med data funnet i Excel-arket.")
        return []

    # 3. Les malen inn i minnet
    with zipfile.ZipFile(mal_sti, "r") as z:
        mal_filer = {navn: z.read(navn) for navn in z.namelist()}

    produserte_odt: list[Path] = []

    # MODUS 1: Samlet dokument (--combine)
    if combine:
        samlet_tittel = f"{mal_sti.stem}_Samlet"
        odt_ut = ut_mappe / f"{samlet_tittel}.odt"
        samlet_xml = _build_combined_xml(mal_filer["content.xml"].decode("utf-8"), rader)
        _write_odt(mal_filer, samlet_xml, odt_ut)
        produserte_odt.append(odt_ut)
    else:
        # MODUS 2: Individuelle brev
        for i, rad in enumerate(rader, 1):
            safe_data = SafeDict(rad, i=i, nr=i)
            try:
                filnavn_base = name_format.format_map(safe_data).strip()
            except Exception:
                filnavn_base = f"Brev_{i}"

            # Vask filnavnet for ugyldige tegn og doble/hengende understreker
            trygt_navn = re.sub(r'[\\/*?:"<>|]', "", filnavn_base).strip()
            trygt_navn = re.sub(r"_+", "_", trygt_navn).strip("_-")

            if not trygt_navn or trygt_navn == "Brev":
                trygt_navn = f"Brev_{i}"

            odt_ut = ut_mappe / f"{trygt_navn}.odt"

            xml = _substitute_xml(mal_filer["content.xml"].decode("utf-8"), rad)
            _write_odt(mal_filer, xml, odt_ut)
            produserte_odt.append(odt_ut)

    # 4. Konverter til PDF med convert_to_pdf() i én samlet batch
    genererte_filer: list[Path] = []
    if output_format in ["pdf", "both"]:
        print(f"🖨️ Konverterer {len(produserte_odt)} fil(er) til PDF i én felles batch...")
        pdf_filer = convert_to_pdf(produserte_odt, output_dir=ut_mappe)
        genererte_filer.extend(pdf_filer)

        if output_format == "pdf":
            for f in produserte_odt:
                f.unlink(missing_ok=True)
        else:
            genererte_filer.extend(produserte_odt)
    else:
        genererte_filer.extend(produserte_odt)

    return genererte_filer


def cli_merge_odt() -> None:
    """CLI-inngangspunkt for bruk i terminal og MenuLibre (%F)."""
    parser = argparse.ArgumentParser(description="Flettemotor for LibreOffice ODT og Excel.")
    parser.add_argument("templates", nargs="*", help="Sti til .odt-mal(er) fra filbehandler (%F)")
    parser.add_argument("-t", "--template", help="Sti til .odt-malen")
    parser.add_argument("-o", "--out-dir", help="Mappe der ferdige filer lagres (standard: ./diverse)")
    parser.add_argument("-n", "--name-format", default="Brev_{i}_{Fornavn}_{Etternavn}", help="Navneformat")
    parser.add_argument("-p", "--pattern", default="Export*.xlsx", help="Mønster for nyeste Excel-fil")
    parser.add_argument("-e", "--excel", help="Bruk en spesifikk Excel-fil")
    parser.add_argument("-f", "--format", choices=["both", "pdf", "odt"], default="both", help="Filformat")
    parser.add_argument("--combine", action="store_true", help="Slå sammen alle brev til ett dokument")
    parser.add_argument("-l", "--limit", type=int, help="Begrens antall rader (for testing)")

    args = parser.parse_args()

    template = args.template
    if not template and args.templates:
        template = args.templates[0]

    if not template:
        _notify("Feil", "Ingen .odt-mal ble oppgitt.", urgency="critical")
        sys.exit(1)

    template_path = Path(template)
    _notify("Fletting pågår", f"Fletter '{template_path.name}' med nyeste medlemsliste...", icon="x-office-document")

    try:
        filer = merge_odt(
            template_path=template_path,
            excel_path=args.excel,
            output_dir=args.out_dir,
            name_format=args.name_format,
            pattern=args.pattern,
            output_format=args.format,
            combine=args.combine,
            limit=args.limit,
        )

        lagringsmappe = args.out_dir or (template_path.parent / "diverse")
        _notify(
            "Fletting fullført!",
            f"Lagret {len(filer)} fil(er) i:\n{lagringsmappe}",
            icon="document-save",
        )
    except Exception as e:
        _notify("Fletting feilet", str(e), icon="dialog-error", urgency="critical")
        sys.exit(1)


if __name__ == "__main__":
    cli_merge_odt()
