"""Norske fødselsnummer- og identitetsverktøy for Polars."""

from __future__ import annotations
import polars as pl


def fnr_detaljer(fnr_kolonne: str = "Fødselsnummer") -> list[pl.Expr]:
    """
    Returnerer Polars-uttrykk som utleder fødselsdato og kjønn fra fødselsnummer.

    Kolonner som lages:
      - fodsels_dato (pl.Date): Beregner 4-sifret årstall iht. Skatteetatens
                                regler for individnummer, og støtter D-nummer.
      - kjønn (pl.String): 'Mann' (oddetall) eller 'Kvinne' (partall) fra 9. siffer.

    Bruk:
        df = df.with_columns(fnr_detaljer("Fødselsnummer"))
    """
    fnr = pl.col(fnr_kolonne)

    dag_raw = fnr.str.slice(0, 2).cast(pl.Int32, strict=False)
    mnd_raw = fnr.str.slice(2, 2).cast(pl.Int32, strict=False)
    aar_2siffer = fnr.str.slice(4, 2).cast(pl.Int32, strict=False)
    individnr = fnr.str.slice(6, 3).cast(pl.Int32, strict=False)
    kjonn_siffer = fnr.str.slice(8, 1).cast(pl.Int32, strict=False)

    # D-nummer-justering (dager 41-71 reduseres med 40)
    dag = pl.when(dag_raw > 40).then(dag_raw - 40).otherwise(dag_raw)

    # Fastsett århundre iht. Skatteetatens fordelingsnøkkel
    arhundre = (
        pl.when(individnr.is_between(500, 749) & (aar_2siffer >= 54))
        .then(1800)
        .when((individnr < 500) | ((individnr >= 900) & (aar_2siffer >= 40)))
        .then(1900)
        .when(individnr >= 500)
        .then(2000)
        .otherwise(None)
    )
    fullt_ar = arhundre + aar_2siffer

    # Bygg dato og parse som pl.Date (strict=False gjør ugyldige datoer til null)
    fodsels_dato = (
        pl.concat_str(
            [
                fullt_ar.cast(pl.String),
                mnd_raw.cast(pl.String).str.zfill(2),
                dag.cast(pl.String).str.zfill(2),
            ],
            separator="-",
        )
        .str.to_date("%Y-%m-%d", strict=False)
        .alias("fodsels_dato")
    )

    # Kjønn fra 9. siffer
    kjonn = (
        pl.when(kjonn_siffer % 2 == 1)
        .then(pl.lit("Mann"))
        .when(kjonn_siffer % 2 == 0)
        .then(pl.lit("Kvinne"))
        .otherwise(None)
        .alias("kjønn")
    )

    return [fodsels_dato, kjonn]
