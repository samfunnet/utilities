# Bruksanvisning: E-postfletting med Obsidian, Jinja2, Polars og Gmail

Denne flettemotoren lar deg kombinere **Obsidian Markdown-notater** (med Jinja2-maler) og **regneark** (Excel / CSV lest med Polars) for å opprette ferdige utkast eller sende e-poster via **Gmail API**.

---

## Innholdsfortegnelse
1. [Hvorfor dette oppsettet?](#1-hvorfor-dette-oppsettet)
2. [Oversikt over kjernefunksjonene](#2-oversikt-over-kjernefunksjonene)
3. [Hvordan bygge en mal i Obsidian](#3-hvordan-bygge-en-mal-i-obsidian)
4. [Praktiske eksempler](#4-praktiske-eksempler)
   - [Eksempel 1: Det enkle standardoppsettet](#eksempel-1-det-enkle-standardoppsettet-finner-nyeste-fil-selv)
   - [Eksempel 2: Spesifikk Excel-fil med alternativ avsenderadresse](#eksempel-2-spesifikk-excel-fil-med-alternativ-avsenderadresse)
   - [Eksempel 3: Vasking, filtrering og beregninger med Polars før sending](#eksempel-3-vasking-filtrering-og-beregninger-med-polars-før-sending)
   - [Eksempel 4: Betinget innhold (Jinja-logikk) og vedlegg](#eksempel-4-betinget-innhold-jinja-logikk-og-vedlegg)
   - [Eksempel 5: Tørrkjøring (Dry Run) – Se resultatet i terminalen før Gmail røres](#eksempel-5-tørrkjøring-dry-run--se-resultatet-i-terminalen-uten-gmail)
5. [Viktige prinsipper og feilsøking](#5-viktige-prinsipper-og-feilsøking)

---

## 1. Hvorfor dette oppsettet?

* **Ren tekst og full kontroll:** Malene dine skrives i Obsidian som vanlige Markdown-filer. Ingen klønete Word- eller LibreOffice-menyer.
* **Metadata i malen (YAML):** Emne, mottaker, avsender og kopi defineres direkte i toppen av malen (Obsidian Properties).
* **Smart variabelhåndtering:** Kolonnenavn fra Excel (f.eks. `E-post 1` eller `Fornavn`) vaskes automatisk slik at du kan bruke både `{{ e_post_1 }}`, `{{ fornavn }}` og `{{ row['E-post 1'] }}`.
* **Sikkerhet:** Som standard oppretter motoren **utkast (drafts)** i Gmail. Du risikerer aldri å spamme hundrevis av folk ved en feil.

---

## 2. Oversikt over kjernefunksjonene

Koden i `src/utilities/merge.py` er bygget opp av atomiske byggeklosser:

| Funksjon | Beskrivelse |
| :--- | :--- |
| `merge_gmail()` | **Hovedfunksjonen.** Leser mal og data, fletter innhold og oppretter utkast (eller sender) i Gmail. |
| `load_data()` | Leser CSV eller Excel (`.xlsx`/`.xls`) inn i en **Polars DataFrame**. Finner nyeste eksportfil automatisk hvis sti utelates. |
| `parse_obsidian_template()` | Deler en `.md`-fil i to: en ordbok med frontmatter (metadata) og selve brødteksten. |
| `prepare_context()` | Gjør en datapad klar for Jinja2: rydder bort `None`-verdier, lager snake_case-aliaser og knytter sammen synonymer (`navn`/`fornavn`, e-postvarianter). |
| `markdown_to_html()` | Gjør om ferdig flettet Markdown-tekst til formatert e-post-HTML med støtte for tabeller, kodelister og linjeskift. |
| `build_email_payload()` | Fletter én enkelt rad mot malen og returnerer et rent dataobjekt med `to`, `subject`, `body_html` osv. Uavhengig av Gmail API. |

---

## 3. Hvordan bygge en mal i Obsidian

En mal er et helt vanlig notat i Obsidian med **YAML frontmatter** øverst:

```markdown
---
from: '"Mikaelkirken, Kristensamfunnet i Oslo" <post@mikaelkirken.no>'
to: '"{{ navn }} {{ etternavn }}" <{{ e_post_1 }}>'
subject: Informasjon om konfirmant {{ konfirmant_navn }}
cc: "leder@mikaelkirken.no"
---
Hei {{ navn }}!

Dette er en viktig beskjed angående **{{ konfirmant_navn }}**.

### Registrert kontaktinformasjon:
* **Telefon:** {{ telefonnummer_1 }}
* **E-post:** {{ e_post_1 }}

Vennlig hilsen,  
Styret
```

### Støttede felter i frontmatter:
* **`to`** *(Påkrevd)*: Mottakeradresse. Kan være ren adresse `{{ e_post_1 }}` eller formatert med navn: `'"{{ navn }} {{ etternavn }}" <{{ e_post_1 }}>'`.
* **`subject`** *(Påkrevd)*: Emnefeltet. Støtter variabler.
* **`from`** *(Valgfritt)*: Avsender. Må være godkjent som alias under *«Send e-post som»* i Gmail. Hvis visningsnavnet har komma, **må** det omsluttes av hermetegn (`'"Navn, Gruppe" <epost@domene.no>'`).
* **`cc`** / **`bcc`** *(Valgfritt)*: Kopi-mottakere.
* **`attachments`** *(Valgfritt)*: Liste over filstier til vedlegg.

---

## 4. Praktiske eksempler

### Eksempel 1: Det enkle standardoppsettet (finner nyeste fil selv)

Hvis du jevnlig laster ned en fil fra medlemsregisteret (f.eks. `Export_20261106.xlsx` til `~/Downloads`), trenger du ikke en gang å oppgi filstien.

```python
from utilities.merge import merge_gmail

# 1. Søker automatisk opp nyeste Export*.* i Downloads
# 2. Leser 'nyhetsbrev_mal.md'
# 3. Lager utkast for de 5 første radene i Gmail
merge_gmail("nyhetsbrev_mal.md", limit=5)
```

---

### Eksempel 2: Spesifikk Excel-fil med alternativ avsenderadresse

Når du har et spesifikt regneark og vil overstyre avsenderprogrammatisk:

```python
from pathlib import Path
from utilities.merge import merge_gmail

EXCEL_FIL = Path(
    "/mnt/server/system-ssd/mount/dev/python/konfirmant-betalinger/foreldre_pr_konfirmant_liste.xlsx"
)

merge_gmail(
    template_path="Bidrag ved konfirmasjon.md",
    data=EXCEL_FIL,
    sender="post@mikaelkirken.no",  # Må være registrert i Gmail-innstillinger
    limit=10,  # Test med 10 først
    send=False,  # False = lag utkast (anbefalt), True = send direkte
)
```

---

### Eksempel 3: Vasking, filtrering og beregninger med Polars før sending

Dette er den **største styrken** med Polars. Du kan rense dataene i forkant slik at du aldri sender tomme eller irrelevante e-poster.

```python
import polars as pl
from utilities.merge import load_data, merge_gmail

# 1. Les inn dataarket med load_data
df = load_data("medlemmer.xlsx")

# 2. Vask og filtrer med Polars:
vasket_df = (
    df.filter(
        # Bare ta med de som faktisk har en gyldig e-post
        pl.col("E-post 1").is_not_null()
        & pl.col("E-post 1").str.contains("@")
    )
    .filter(
        # Send kun til de med utestående beløp
        pl.col("Utestående") > 0
    )
    .with_columns(
        # Beregn et purregebyr i en ny kolonne
        (pl.col("Utestående") + 50).alias("Totalbeløp")
    )
    .unique(subset=["E-post 1"])  # Unngå å sende to e-poster til samme adresse
)

print(f"Fant {len(vasket_df)} mottakere som skal ha purring.")

# 3. Send Polars DataFrame rett inn i flettemotoren
merge_gmail("purring_mal.md", data=vasket_df)
```

---

### Eksempel 4: Betinget innhold (Jinja-logikk) og vedlegg

Jinja2 lar deg tilpasse teksten basert på mottakerens verdier.

#### Obsidian-mal (`kontingent_mal.md`):
```markdown
---
from: "kasserer@klubb.no"
subject: Medlemsstatus for {{ fornavn }}
to: "{{ e_post_1 }}"
attachments:
  - "/dokumenter/vedtekter_2026.pdf"
---
Hei {{ fornavn }}!

{% if har_betalt == "Ja" %}
Tusen takk! Vi har registrert din innbetaling for sesongen. Alt er i orden.
{% else %}
⚠️ Vi kan ikke se at kontingenten på **kr {{ belop }},-** er betalt ennå. 
Vennligst benytt KID `{{ kid }}` ved betaling innen {{ forfallsdato }}.
{% endif %}

{% if er_foresatt %}
*Merk: Denne e-posten gjelder medlemskapet til ditt barn, {{ barn_navn }}.*
{% endif %}

Med vennlig hilsen,  
Styret
```

---

### Eksempel 5: Tørrkjøring (Dry Run) – Se resultatet i terminalen uten Gmail

Hvis du vil teste hvordan malen og variablene ser ut **før du rører Gmail**, kan du bruke `build_email_payload` direkte:

```python
from utilities.merge import (
    build_email_payload,
    load_data,
    parse_obsidian_template,
)

# 1. Hent data og mal
df = load_data("deltakere.xlsx")
meta, body = parse_obsidian_template("velkomst_mal.md")

# 2. Test kun på første rad
forste_rad = df.row(0, named=True)
payload = build_email_payload(meta, body, forste_rad)

# 3. Inspiser payloaden
print("=== FORHÅNDSVISNING AV FØRSTE E-POST ===")
print("Til:     ", payload["to"])
print("Fra:     ", payload["sender"])
print("Emne:    ", payload["subject"])
print("--- TEKSTVERSJON ---")
print(payload["body_text"])
print("--- HTML-VERSJON ---")
print(payload["body_html"][:300], "...")
```

---

## 5. Viktige prinsipper og feilsøking

### 1. Tomme celler blir aldri `"None"`
Når Polars leser tomme Excel-celler, gjør `prepare_context()` dem automatisk om til tomme strenger (`""`). Dermed unngår du at det plutselig står *"Hei None"* i brevet.

### 2. Særnorske tegn i navn (`æ`, `ø`, `å`)
Gmail API krever såkalt RFC 2047-koding for visningsnavn i e-posthoder. Hvis mottakeren heter f.eks. **Mali Konstad Brødreskift**, koder motoren dette automatisk i bakgrunnen. Hvis Google likevel skulle avvise et hode, vil motoren automatisk prøve på nytt med bare den rene e-postadressen.

### 3. Send mail as (Gmail aliaser)
Du kan ikke flette fra en vilkårlig adresse (f.eks. `post@menigheten.no`) med mindre den er registrert og verifisert i Gmail:
1. Åpne Gmail ➔ **Innstillinger (tannhjulet)** ➔ **Se alle innstillinger**.
2. Fanen **Kontoer og import**.
3. Sjekk at adressen ligger under **«Send e-post som:»**.

### 4. Sikkerhetsregel
Kjør alltid med `send=False` (standard) og `limit=2` eller `limit=5` første gang. Åpne Gmail i nettleseren, sjekk utkastene manuelt, og kjør deretter hele arket når alt ser perfekt ut!
