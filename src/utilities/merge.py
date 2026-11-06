from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence

import openpyxl

import frontmatter
import csv
from jinja2 import BaseLoader, Environment
import markdown
import polars as pl
import warnings
from email.header import Header
from email.utils import formataddr, parseaddr
from utilities.files import get_newest_file
from utilities.pdf import _notify, convert_to_pdf
from utilities.gmail import create_email_draft, send_email


# ---------------------- START jinja2 mailmerge stuff -------------------------------

# Sett opp Jinja-miljø
_jinja_env = Environment(loader=BaseLoader(), autoescape=False)


# ==========================================
# 1. Datainnlesing
# ==========================================
def load_data(
    source: Path | str | None = None,
    pattern: str = "Export*.*",
    search_dirs: Sequence[str] = ("~/syncthing/Downloads", "~/Downloads"),
) -> pl.DataFrame:
    """Leser nyeste Excel/CSV-fil eller en oppgitt sti inn i Polars."""
    if source:
        file_path = Path(source).expanduser().resolve()
    else:
        file_path = None
        for d in search_dirs:
            found = get_newest_file(d, pattern)
            if found:
                file_path = found
                break

    if not file_path or not file_path.exists():
        raise FileNotFoundError(f"Fant ingen datafil: '{source or pattern}'")

    ext = file_path.suffix.lower()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*Could not determine dtype.*")
        if ext in [".xlsx", ".xls"]:
            df = pl.read_excel(file_path)
        elif ext == ".csv":
            df = pl.read_csv(file_path, infer_schema_length=10000)
        else:
            raise ValueError(f"Støtter kun .xlsx, .xls og .csv, fikk: {ext}")

    # Rens kolonnenavn (trimmer usynlige mellomrom)
    return df.rename({col: str(col).strip() for col in df.columns})


# ==========================================
# 2. Mal og Kontekst
# ==========================================
def parse_obsidian_template(path: Path | str) -> tuple[dict[str, Any], str]:
    """Leser en Obsidian Markdown-fil og returnerer (frontmatter_dict, brødtekst)."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Malfilen finnes ikke: {p}")
    post = frontmatter.load(p)
    return post.metadata, post.content


def _slugify(text: str) -> str:
    s = str(text).strip().lower()
    for ch in ("-", "–", "—", " ", "\t", "\xa0"):
        s = s.replace(ch, "_")
    return re.sub(r"_+", "_", s)


def prepare_context(row: dict[str, Any]) -> dict[str, Any]:
    """Gjør raden klar for Jinja2 med universelle oppslag.

    Gjør at f.eks. 'E-post 1', 'e_post_1', 'epost' og 'row[...]'
    peker til samme verdi.
    """
    clean = {str(k).strip(): ("" if v is None else v) for k, v in row.items()}
    ctx: dict[str, Any] = dict(clean)

    # 1. Små bokstaver og snake_case
    for k, v in clean.items():
        ctx[k.lower()] = v
        ctx[_slugify(k)] = v

    # 2. Synonymer for navn
    if "fornavn" in ctx and "navn" not in ctx:
        ctx["navn"] = ctx["fornavn"]
    elif "navn" in ctx and "fornavn" not in ctx:
        ctx["fornavn"] = ctx["navn"]

    # 3. Finn e-postverdi på tvers av vanlige kolonnenavn
    email_val = ""
    for candidate in (
        "e_post_1",
        "e_post",
        "epost",
        "email",
        "e_postadresse",
        "e_post_foresatt",
    ):
        val = str(ctx.get(candidate, "")).strip()
        if val and "@" in val:
            email_val = val
            break

    # Gjør e-postadressen tilgjengelig under alle varianter
    if email_val:
        for alias in (
            "e_post_1",
            "e_post",
            "epost",
            "email",
            "e_postadresse",
            "E-post 1",
            "E-post",
        ):
            ctx[alias] = email_val
            clean[alias] = email_val

    # Råoppslag via row[...] slår opp i den samme vaskede ordboken
    ctx["row"] = ctx
    return ctx


def markdown_to_html(md_text: str) -> str:
    """Konverterer Markdown til e-post-HTML."""
    return markdown.markdown(
        md_text,
        extensions=["nl2br", "tables", "fenced_code", "sane_lists"],
    )


def extract_person_label(ctx: dict[str, Any], fallback_idx: int) -> str:
    """Henter lesbart navn eller ID for pene logger."""
    f = str(
        ctx.get("fornavn")
        or ctx.get("navn")
        or ctx.get("Fornavn")
        or ctx.get("Navn")
        or ""
    ).strip()
    e = str(ctx.get("etternavn") or ctx.get("Etternavn") or "").strip()
    full = f"{f} {e}".strip()
    if full:
        return full
    for k in (
        "cornerstone_id",
        "medlemsnummer",
        "kid",
        "id",
        "Cornerstone-ID",
        "Medlemsnummer",
        "KID",
    ):
        if ctx.get(k):
            return f"{k}: {ctx[k]}"
    return f"Rad {fallback_idx}"


# ==========================================
# 3. Payload-bygger
# ==========================================
def build_email_payload(
    meta: dict[str, Any],
    body_template_str: str,
    row: dict[str, Any],
    sender: str | None = None,
    to_column: str | None = None,
    compiled: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fletter én enkelt e-post og validerer mottakeradresse."""
    ctx = prepare_context(row)
    person = extract_person_label(ctx, 0)

    body_tmpl = (
        compiled["body"] if compiled else _jinja_env.from_string(body_template_str)
    )
    subj_tmpl = (
        compiled["subject"]
        if compiled
        else _jinja_env.from_string(str(meta.get("subject", "")))
    )

    to_raw = to_column or meta.get("to")
    if not to_raw:
        raise ValueError("Mottaker ('to') er ikke oppgitt i malens frontmatter!")
    to_tmpl = compiled["to"] if compiled else _jinja_env.from_string(str(to_raw))

    # 1. Flett mottaker og formater trygt for norske tegn (æ, ø, å)
    to_field = to_tmpl.render(ctx).strip()
    display_name, email_address = parseaddr(to_field)

    if not email_address or "@" not in email_address:
        raise ValueError(
            f"Mangler gyldig e-postadresse for '{person}' (fikk: '{to_field}')"
        )

    # Sikre at særnorske tegn (æ, ø, å) i navnet ikke krasjer Gmail
    if display_name:
        try:
            display_name.encode("ascii")
            clean_to = f'"{display_name}" <{email_address}>'
        except UnicodeEncodeError:
            # RFC 2047 MIME-koding av navn med æ/ø/å
            encoded_name = Header(display_name, "utf-8").encode()
            clean_to = f"{encoded_name} <{email_address}>"
    else:
        clean_to = email_address

    # 2. Emne
    subject_field = subj_tmpl.render(ctx).strip()
    if not subject_field:
        raise ValueError(f"Emne mangler for '{person}'.")

    # 3. Brødtekst (Markdown -> HTML)
    rendered_body = body_tmpl.render(ctx)
    html_body = markdown_to_html(rendered_body)

    # 4. Avsender (Standard er "me")
    s_val = sender or meta.get("from") or meta.get("sender") or "me"
    sender_tmpl = (
        compiled.get("sender")
        if compiled
        else (_jinja_env.from_string(str(s_val)) if s_val != "me" else None)
    )
    sender_field = sender_tmpl.render(ctx).strip() if sender_tmpl else "me"

    # 5. Kopi (cc)
    cc_tmpl = (
        compiled.get("cc")
        if compiled
        else (_jinja_env.from_string(str(meta.get("cc", ""))) if "cc" in meta else None)
    )
    cc_field = cc_tmpl.render(ctx).strip() if cc_tmpl else None

    # 6. Vedlegg
    attachments = meta.get("attachments")
    if isinstance(attachments, str):
        attachments = [attachments]

    return {
        "to": clean_to,  # <--- Sender den riktig kodede mottakeren
        "subject": subject_field,
        "body_text": rendered_body,
        "body_html": html_body,
        "sender": sender_field,
        "cc": cc_field or None,
        "attachments": attachments,
    }


# ==========================================
# 4. Hovedfunksjon for Gmail
# ==========================================
def merge_gmail(
    template_path: Path | str,
    data: pl.DataFrame | Path | str | None = None,
    to_column: str | None = None,
    sender: str | None = None,
    send: bool = False,
    limit: int | None = None,
) -> list[Any]:
    """Hovedfunksjon: Fletter e-poster og oppretter utkast (eller sender) i Gmail."""
    df = data if isinstance(data, pl.DataFrame) else load_data(data)
    if limit:
        df = df.head(limit)

    if df.is_empty():
        print("⚠️ Ingen rader å flette.")
        return []

    meta, body_template = parse_obsidian_template(template_path)

    to_raw = to_column or meta.get("to")
    if not to_raw:
        raise ValueError("Mottaker ('to') er ikke spesifisert i malens frontmatter!")

    # Forhåndskompiler malene én gang
    compiled = {
        "body": _jinja_env.from_string(body_template),
        "subject": _jinja_env.from_string(str(meta.get("subject", ""))),
        "to": _jinja_env.from_string(str(to_raw)),
        "cc": (
            _jinja_env.from_string(str(meta.get("cc", ""))) if "cc" in meta else None
        ),
    }
    s_val = sender or meta.get("from") or meta.get("sender")
    if s_val and s_val != "me":
        compiled["sender"] = _jinja_env.from_string(str(s_val))

    action = "Sender" if send else "Oppretter utkast for"
    print(
        f"✉️ {action} {len(df)} e-post(er) basert på mal: '{Path(template_path).name}'"
    )

    results = []
    skipped = 0

    for i, row in enumerate(df.iter_rows(named=True), 1):
        ctx = prepare_context(row)
        person = extract_person_label(ctx, i)
        try:
            payload = build_email_payload(
                meta,
                body_template,
                row,
                sender=sender,
                to_column=to_column,
                compiled=compiled,
            )

            try:
                if send:
                    res = send_email(**payload)
                    print(f"  [{i}/{len(df)}] 🚀 Sendt til {payload['to']}")
                else:
                    res = create_email_draft(**payload)
                    print(f"  [{i}/{len(df)}] 📝 Utkast til {payload['to']}")
                results.append(res)
            except Exception as google_err:
                # Hvis Google likevel skulle nekte pga tegnsett i headeren, prøv med ren e-post
                if "Invalid To header" in str(google_err):
                    _, pure_email = parseaddr(payload["to"])
                    if pure_email and "@" in pure_email:
                        payload["to"] = pure_email
                        if send:
                            res = send_email(**payload)
                            print(
                                f"  [{i}/{len(df)}] 🚀 Sendt til {payload['to']} ({person})"
                            )
                        else:
                            res = create_email_draft(**payload)
                            print(
                                f"  [{i}/{len(df)}] 📝 Utkast til {payload['to']} ({person})"
                            )
                        results.append(res)
                        continue
                raise google_err

        except Exception as e:
            skipped += 1
            print(f"  [{i}/{len(df)}] ⚠️ Hoppet over '{person}': {e}")

    print(
        f"\n✨ Ferdig! {len(results)} vellykket, {skipped} hoppet over/feilet av totalt {len(df)}."
    )
    return results


# ---------------------- END jinja2 mailmerge stuff -------------------------------


class SafeDict(dict):
    """Sørger for at manglende kolonner i malen ikkeikrasjer navneformateringen,
    og tillater treff uavhengig av store/små bokstaver."""

    def __getitem__(self, key: str) -> Any:
        if key in self:
            return super().__getitem__(key)
        # Sjekk case-insensitive og med space/understrek
        key_norm = key.lower().replace(" ", "_")
        for k, v in self.items():
            if k.lower().replace(" ", "_") == key_norm:
                return v
        return ""

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
    ny_xml = (
        xml_mal[: m.start()] + start_tag + ny_tekst + slutt_tag + xml_mal[m.end() :]
    )

    pb_stil = (
        '<style:style style:name="PB_MERGE" style:family="paragraph">'
        '<style:paragraph-properties fo:break-before="page" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:line-height="0%"/>'
        '<style:text-properties fo:font-size="1pt"/>'
        "</style:style>"
    )
    if "<office:automatic-styles>" in ny_xml:
        ny_xml = ny_xml.replace(
            "<office:automatic-styles>", "<office:automatic-styles>" + pb_stil, 1
        )
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
            z.writestr(
                "mimetype", mal_filer["mimetype"], compress_type=zipfile.ZIP_STORED
            )
        for fil, data in mal_filer.items():
            if fil == "mimetype":
                continue
            innhold = xml_content.encode("utf-8") if fil == "content.xml" else data
            z.writestr(fil, innhold, compress_type=zipfile.ZIP_DEFLATED)


def merge_odt(
    template_path: str | Path,
    excel_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    name_format: str = "{mal}_{Fornavn}_{Etternavn}",
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

    # Fjern 'mal' som første ord i navnet (case-insensitive) hvis det finnes
    # F.eks. "mal ny medlem" -> "ny medlem", "Mal_Purring" -> "Purring"
    mal_tittel = re.sub(r"^mal[\s_\-:]+", "", mal_sti.stem, flags=re.IGNORECASE).strip()
    if not mal_tittel:
        mal_tittel = mal_sti.stem

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
        raise FileNotFoundError(
            f"Fant ingen Excel-fil som matcher '{pattern}' i Downloads."
        )

    print(f"📄 Excel-kilde: {kilde_excel.name}")
    print(f"📝 Mal: {mal_sti.name} (bruker tittel: '{mal_tittel}')")
    print(f"📁 Lagres i: {ut_mappe}")

    # 2. Les Excel-arket
    wb = openpyxl.load_workbook(kilde_excel, data_only=True)
    if sheet_name:
        sheet = (
            wb[sheet_name]
            if isinstance(sheet_name, str) and sheet_name in wb.sheetnames
            else wb.worksheets[int(sheet_name) - 1]
        )
    else:
        sheet = wb.active or wb.worksheets[0]

    headere = [str(c.value).strip() for c in sheet[1] if c.value is not None]
    rader: list[dict[str, Any]] = []
    for row in sheet.iter_rows(min_row=2, max_col=len(headere), values_only=True):
        if not any(row):
            continue
        rad_dict = {
            h: ("" if v is None else str(v).strip()) for h, v in zip(headere, row)
        }
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
        samlet_tittel = f"{mal_tittel}_Samlet"
        odt_ut = ut_mappe / f"{samlet_tittel}.odt"
        samlet_xml = _build_combined_xml(
            mal_filer["content.xml"].decode("utf-8"), rader
        )
        _write_odt(mal_filer, samlet_xml, odt_ut)
        produserte_odt.append(odt_ut)
    else:
        # MODUS 2: Individuelle brev
        format_streng = name_format or "{mal}_{Fornavn}_{Etternavn}"
        for i, rad in enumerate(rader, 1):
            safe_data = SafeDict(
                rad,
                i=i,
                nr=i,
                mal=mal_tittel,
                mal_navn=mal_tittel,
                template=mal_tittel,
            )
            try:
                filnavn_base = format_streng.format_map(safe_data).strip()
            except Exception:
                filnavn_base = f"{mal_tittel}_{i}"

            # Vask filnavnet for ugyldige tegn og doble/hengende understreker
            trygt_navn = re.sub(r'[/\\*?:"<>|]', "", filnavn_base).strip()
            trygt_navn = re.sub(r"_+", "_", trygt_navn).strip("_-")

            if not trygt_navn or trygt_navn == mal_tittel:
                trygt_navn = f"{mal_tittel}_{i}"

            odt_ut = ut_mappe / f"{trygt_navn}.odt"

            # Kollisjonssikring i tilfelle to personer har identisk navn
            if odt_ut in produserte_odt:
                odt_ut = ut_mappe / f"{trygt_navn}_{i}.odt"

            xml = _substitute_xml(mal_filer["content.xml"].decode("utf-8"), rad)
            _write_odt(mal_filer, xml, odt_ut)
            produserte_odt.append(odt_ut)

    # 4. Konverter til PDF med convert_to_pdf() i én samlet batch
    genererte_filer: list[Path] = []
    if output_format in ["pdf", "both"]:
        print(
            f"🖨️ Konverterer {len(produserte_odt)} fil(er) til PDF i én felles batch..."
        )
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
    parser = argparse.ArgumentParser(
        description="Flettemotor for LibreOffice ODT og Excel."
    )
    parser.add_argument(
        "templates", nargs="*", help="Sti til .odt-mal(er) fra filbehandler (%%F)"
    )
    parser.add_argument("-t", "--template", help="Sti til .odt-malen")
    parser.add_argument(
        "-o", "--out-dir", help="Mappe der ferdige filer lagres (standard: ./diverse)"
    )

    parser.add_argument(
        "-n",
        "--name-format",
        default="{mal}_{Fornavn}_{Etternavn}",
        help="Navneformat (standard: '{mal}_{Fornavn}_{Etternavn}')",
    )

    parser.add_argument(
        "-p", "--pattern", default="Export*.xlsx", help="Mønster for nyeste Excel-fil"
    )
    parser.add_argument("-e", "--excel", help="Bruk en spesifikk Excel-fil")
    parser.add_argument(
        "-f",
        "--format",
        choices=["both", "pdf", "odt"],
        default="both",
        help="Filformat",
    )
    parser.add_argument(
        "--combine", action="store_true", help="Slå sammen alle brev til ett dokument"
    )
    parser.add_argument(
        "-l", "--limit", type=int, help="Begrens antall rader (for testing)"
    )

    args = parser.parse_args()

    template = args.template
    if not template and args.templates:
        template = args.templates[0]

    if not template:
        _notify("Feil", "Ingen .odt-mal ble oppgitt.", urgency="critical")
        sys.exit(1)

    template_path = Path(template)
    _notify(
        "Fletting pågår",
        f"Fletter '{template_path.name}' med nyeste medlemsliste...",
        icon="x-office-document",
    )

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
