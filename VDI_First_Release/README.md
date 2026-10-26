# IKT213 – Visual Defect Inspector

Dette er første release av Visual Defect Inspector, prosjektet vårt for å undersøke skjermbeskyttere i en boks med fast kamera og belysning.

For at programvaren skal kunne kjøres og testes uten det fysiske utstyret vårt, har jeg lagt ved en Linux-demo med simulert kamera og en placeholder for defektmodellen. Nano-versjonen er prosjektet som er satt opp for kameraet og boksen vår, med de trente modellene inkludert.

| Mappe | Bruk |
| --- | --- |
| `project/linux-demo` | Demo som kan kjøres på en vanlig Linux-maskin uten kamera, boks eller trente modeller. |
| `project/nano` | Versjon for Jetson Nano og det fysiske inspeksjonsoppsettet, med formmodell og defektmodell. |

## Sammenheng med testplanen i rapporten

Rapportens kapittel 3.3 omfatter både programvareflyten og hvor godt systemet finner virkelige feil. Linux-demoen lar vurdereren teste programvareflyten uten riggen. Modellens nøyaktighet og den fysiske bildefangsten må vurderes separat med ekte bilder og det fysiske oppsettet.

Se [TESTPLAN.md](project/TESTPLAN.md) for koblingen mellom funksjonene, testtilfellene og forventede resultater. [TESTRESULTATER.md](project/TESTRESULTATER.md) beskriver hva som faktisk er kjørt. [Den manuelle testloggen](project/test-results/MANUELL_TESTLOGG.csv) kan brukes til å registrere observert resultat og bestått/ikke bestått ved videre testing. Tester som ikke er gjennomført, er ikke merket som bestått.

## Linux-demo uten kamera

Bruk en Linux-maskin med grafisk skrivebord og Python 3.10–3.12. Installasjonen trenger internettilgang. PyCharm er ikke nødvendig.

Åpne en terminal i roten av repoet og kjør:

```bash
sudo apt update
sudo apt install -y python3-venv python3-tk
cd project/linux-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python test_on_pc.py
```

Programmet åpner GUI-et i TEST MODE. Verken kamera eller modellfiler skal installeres for denne demoen.

Ved senere oppstart, fra roten av repoet:

```bash
cd project/linux-demo
source .venv/bin/activate
python test_on_pc.py
```

### Hva demoen gjør

Kameraet erstattes med genererte testbilder. Placeholderen gir forhåndsbestemte resultater for riper og sprekker, slik at arbeidsflyten kan testes. Den er ikke en trent modell som finner disse feilene i et vilkårlig bilde.

OpenCV-kontrollene for tilstedeværelse, form og mål kjøres på de genererte bildene. GUI, operatørvalg, historikk og lagring i SQLite bruker den vanlige programkoden. Demoens kunstige mål og kalibrering gjelder bare testbildene.

### Manuell testplan

1. Trykk på knappen for å ta bilde og analysere neste skjermbeskytter.
2. Kontroller at programmet viser at det arbeider, og deretter viser bilde og resultat.
3. Velg Pass eller Reject når GUI-et tillater det. Dette lagres som operatørens vurdering, separat fra den automatiske vurderingen.
4. Gjenta for å gå videre til neste testtilfelle. Tilfellene under kommer automatisk i denne rekkefølgen i en ny testøkt.
5. Åpne History og kontroller at resultat og operatørvalg er lagret. Kontroller også Statistics og eksportfunksjonene.

| Testtilfelle | Forventet automatisk resultat |
| --- | --- |
| Ren skjermbeskytter | PASS |
| Ripe | REJECT, Scratch |
| Sprekk | REJECT, Crack |
| Ripe og sprekk | REJECT, Scratch + Crack |
| Ingen skjermbeskytter | REJECT |
| Feil form | REJECT |
| Manglende bit | REJECT |
| Feil mål | REJECT |
| Rotert skjermbeskytter | PASS |
| Simulert modellfeil | ERROR |

Testrekken starter på nytt når programmet startes på nytt. Hvis en tidligere analyse venter på operatørvalg, vises den først. Fullfør valget før neste analyse. Ved en feil skal programmet vise feilen, ikke godkjenne inspeksjonen.

Demodata opprettes lokalt i `project/linux-demo/data/demo.sqlite3`. Testresultatene viser programvarens oppførsel med testdata; de måler ikke hvor nøyaktig den trente modellen finner virkelige skader.

### Automatiske programvaretester

Fra `project/linux-demo`, med miljøet aktivert:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tester som krever et grafisk display hoppes over dersom display ikke er tilgjengelig.

## Jetson Nano med fysisk kamera

Denne versjonen ligger i `project/nano`. Den er satt opp for Jetson Nano med Linux, Razer Kiyo Pro og boksen med fast belysning. Den inkluderer de trente modellene for form og for defektene Scratch og Crack. Modellene kjøres på CPU gjennom ONNX Runtime.

Åpne en terminal på Nanoens grafiske skrivebord. Fra roten av repoet:

```bash
cd project/nano
bash START_NANO.sh
```

Første oppstart installerer nødvendige avhengigheter, oppretter `.nano-venv` og kontrollerer modellene mot de fire vedlagte eksempelbildene. Deretter åpnes GUI-et. Installasjonen kan be om sudo-passord. Senere oppstarter bruker det samme miljøet.

Python 3.6 på den opprinnelige Nanoen bruker de inkluderte ARM64-pakkene. Manglende Ubuntu-pakker krever apt-tilgang. Oppstartsskriptet setter også ARMV8-innstillingen som omgår NumPy/OpenBLAS-feilen med «Illegal instruction» på Nano.

`INSTALL_MODELS.sh` kjører bare installasjon og modellkontroll. Bruk `START_NANO.sh` for å åpne GUI-et.

### Kamera, lys og kalibrering

Kamerainnstillingene ligger i `project/nano/config/inspection.json`. Oppsettet bruker blant annet 1920 × 1080 YUYV, fokus 157, eksponering 2047 og gain 0. Kameraet søkes opp via en fast enhetssti for Kiyo Pro.

Disse innstillingene er valgt for kameraet og lysforholdene i boksen vår. Et annet kamera, en annen avstand eller annen belysning krever at oppsettet tilpasses og kontrolleres på nytt. Linux-demoen er derfor laget for at arbeidsflyten skal kunne testes uten riggen.

Den fysiske målekalibreringen er ikke ferdig utfylt i konfigurasjonen som følger med. Referansebilde, millimeter per piksel, nominelle mål og toleranser må settes med det faktiske oppsettet gjennom kalibreringsverktøyet. Et bilde uten påviste feil kan derfor få INCOMPLETE fremfor en full automatisk PASS før målekalibreringen er fullført.

Nano-versjonen er under fysisk utprøving. Modellene er kontrollert på vedlagte eksempelbilder i byggemiljøet, men dette er ikke en ferdig verifikasjon av hele systemet med Nano, kamera og boks.

### Modellkontroll uten kamerabilde

Etter installasjonen kan modellene også kontrolleres med de lagrede eksempelbildene. Fra `project/nano`:

```bash
.nano-venv/bin/python tools/check_models.py
```

Dette krever ikke kamera, men erstatter ikke testing på det fysiske oppsettet.

## Innlevering

Første release kan legges på branchen `project-first-release`. Lever lenken til den branchen på Canvas, slik at riktig versjon av både kode og installasjonsveiledning er tydelig. Begge prosjektmappene og denne README-filen skal være med.
