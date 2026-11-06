"""Testscript for å verifisere utsending fra et alias/annen Workspace-adresse."""

from pathlib import Path
from utilities import send_email

# 1. Mottaker for testen
TEST_RECIPIENT = "jviksaas@yahoo.no"

# 2. Avsenderadresse:
# Dette må være en adresse som er registrert under "Send e-post som" i Gmail.
# Alternativ A: Kun e-postadresse
# SENDER = "post@organisasjonen.no"

# Alternativ B: Med visningsnavn (anbefalt for profesjonelt utseende)
# SENDER = "Mikaelkirken, Kristensamfunnet i Oslo <post@mikaelkirken.no>"
SENDER = '"Mikaelkirken, Kristensamfunnet i hovedstaden" <post@mikaelkirken.no>'
# SENDER = "post@mikaelkirken.no"


def main():
    print(f"Sender test-epost...")
    print(f"  Fra: {SENDER}")
    print(f"  Til: {TEST_RECIPIENT}")

    try:
        melding = send_email(
            sender=SENDER,  # <-- Her overstyrer du "me" med ønsket alias/adresse
            to=TEST_RECIPIENT,
            subject="Test fra alias / Workspace-adresse",
            body_text=f"Hei!\nDette er en test sendt fra avsenderen: {SENDER}",
            body_html=f"""
            <div style="font-family: sans-serif; padding: 15px; border-left: 4px solid #2196F3;">
                <h2>Test av alias-avsender! ✉️</h2>
                <p>Denne e-posten ble sendt via <code>send_email()</code> med egendefinert <code>sender</code>:</p>
                <ul>
                    <li><strong>Avsender:</strong> <code>{SENDER}</code></li>
                    <li><strong>Mottaker:</strong> <code>{TEST_RECIPIENT}</code></li>
                </ul>
                <p>Sjekk 'Fra'-feltet i innboksen din for å bekrefte at aliaset vises riktig.</p>
            </div>
            """,
        )

        print("\n✅ E-post ble sendt!")
        print(f"Melding-ID: {melding.id}")

    except Exception as e:
        print(f"\n❌ Feil under sending: {e}")


if __name__ == "__main__":
    main()
