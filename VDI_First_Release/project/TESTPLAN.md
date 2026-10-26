# Testplan for første release

Planen følger temaene i rapportens kapittel 3.3. Kravene er angitt med beskrivende navn. TP-numrene nedenfor er test-ID-er, ikke nye kravnumre. PASS betyr at programmet godkjenner en skjermbeskytter; bestått betyr at en test gir det forventede resultatet. En test som skal gi REJECT eller ERROR er dermed bestått når riktig avvisning eller feilmelding kommer.

## Tester vurdereren kan kjøre på Linux

Installer og start demoen som beskrevet i [README](../README.md#linux-demo-uten-kamera). De ti GUI-tilfellene kjøres automatisk i rekkefølgen oppgitt der. For hver test skal forventet og observert resultat sammenlignes. Registrer resultatet i [MANUELL_TESTLOGG.csv](test-results/MANUELL_TESTLOGG.csv).

| ID | Funksjonelt krav / tema i rapporten | Gjennomføring | Forventet resultat |
| --- | --- | --- | --- |
| TP01 | Korrekt PASS/FAIL og sammenhengende inspeksjon | Kjør demoens rene bilde. | Automatisk PASS, bilde og resultat vises. Operatørvalget lagres separat. Programmet bruker teksten REJECT for rapportens FAIL. |
| TP02 | Klassifisering av riper, sprekker og kombinasjoner | Kjør GUI-tilfelle 2, 3 og 4. | REJECT med henholdsvis Scratch, Crack og Scratch + Crack. Defektutdata er simulerte; dette tester videre behandling og visning, ikke modellnøyaktighet. |
| TP03 | Kontroll av tilstedeværelse | Kjør tilfellet uten skjermbeskytter. | REJECT med feil i tilstedeværelseskontrollen. Defektmodellen hoppes over. |
| TP04 | Formkontroll, feil form og manglende del | Kjør tilfellene med feil form og manglende bit. | REJECT med feil i formkontrollen. Konturen beregnes med OpenCV på syntetiske bilder. |
| TP05 | Mål og toleranser | Sammenlign ren beskytter med tilfellet med feil mål. | Ren beskytter gir omtrent 70 × 150 mm i demoens kunstige kalibrering. Feil mål gir REJECT. Dette er ikke kalibrering av riggen. |
| TP06 | Robusthet ved rotasjon | Kjør tilfellet med rotert beskytter. | PASS med demoens kalibrering. Flere fysiske plasseringer testes separat. |
| TP07 | Bildelagring og metadata | Kjør en analyse, åpne History og start appen på nytt. | Bilde og automatisk resultat kan hentes igjen under samme ID. Operatørvalg og tidsstempler bevares. |
| TP08 | Resultatvisning og operatørens valg | Observer en analyse. Velg deretter Pass eller Reject og fortsett. | Lasteindikator under behandling, riktig bilde og resultat etterpå. Neste opptak venter på operatørvalg. Ved omstart vises et eventuelt uferdig valg. |
| TP09 | Ugyldige filer og lagringsfeil | Kjør de automatiske feiltestene nedenfor. | Ugyldige bilder gir feil. Feil ved første lagring stopper analysen. Hvis sluttresultatet ikke kan lagres, skal programmet ikke bekrefte en lagret PASS. |
| TP10 | Håndtering av feil i modellen | Kjør GUI-tilfelle 10. | ERROR og forklaring på feilen. Feilen skal ikke bli en automatisk PASS når operatøren avslutter vurderingen. |
| TP11 | Historikk, statistikk og eksport | Lagre både Pass- og Reject-valg. Se History/Statistics og eksporter CSV og avviste bilder. | Lagrede valg og automatiske resultater kan skilles. Eksporten inneholder tilhørende data og riktige avviste bilder. |

Kjør hele Linux-testsuiten fra `project/linux-demo`, med det installerte miljøet aktivert:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

For bare fil- og lagringsfeiltestene:

```bash
python -m pytest -q tests/test_pipeline.py -k 'invalid_import or failed_initial_storage or failed_result_storage'
```

De relevante testfilene er [test_pipeline.py](linux-demo/tests/test_pipeline.py), [test_operator_pipeline.py](linux-demo/tests/test_operator_pipeline.py), [test_adapters.py](linux-demo/tests/test_adapters.py) og [test_gui.py](linux-demo/tests/test_gui.py). Kameraadaptertestene bruker testdobler. Tk-testene krever display; en test som hoppes over, regnes ikke som bestått GUI-testing.

## Modell- og riggtester

Disse dekker resten av rapportens testplan. Linux-demoens placeholder kan ikke dokumentere at de er bestått.

| ID | Funksjonelt krav / tema i rapporten | Gjennomføring | Forventet resultat / dokumentasjon |
| --- | --- | --- | --- |
| TP12 | Modellintegrasjon | Etter installasjon, kjør `.nano-venv/bin/python tools/check_models.py` fra `project/nano`. | De fire vedlagte eksempelbildene gir de forventede formklassene og defektklassene. Dette er en regresjonskontroll, ikke en måling av presisjon på et uavhengig testsett. |
| TP13 | Automatisk håndtering av overlappende deteksjoner | Kjør testen `test_scratch_duplicate_filter_preserves_crack_boxes` i `project/nano/tests/test_trained_models.py`. Kontroller deretter deteksjonsbokser på ekte bilder med overlapp. | Den programmerte filtreringen fjerner dupliserte Scratch-bokser i testtilfellet uten å fjerne Crack-bokser. Bevaring av faktiske skader må kontrolleres mot annotasjoner. |
| TP14 | Modellens precision, recall, falske alarmer og oversette skader | Bruk merkede bilder av riper, sprekker, kombinasjoner og rene beskyttere i et separat testsett. Sammenlign klasse og boks med manuelle annotasjoner. | Registrer TP, FP og FN og beregn precision og recall per defektklasse. Registrer også antall rene bilder med falsk alarm og skadde bilder uten deteksjon. Et numerisk beståttkrav må fastsettes før evalueringen. |
| TP15 | Trening, validering og uavhengig test | Dokumenter hvilke bilder som tilhører hvert sett. Velg modell/innstillinger på trenings- og valideringssettet; evaluer deretter på testsettet. | Ingen videre tilpasning til resultatene på testsettet. De fire modellkontrollbildene regnes ikke automatisk som et uavhengig testsett. Datasettinndelingen og en full evalueringsrapport følger ikke med denne pakken. |
| TP16 | Form, plassering, støy og usikre resultater på ekte bilder | Ta bilder av korrekt modell, feil modell, manglende deler og tom boks. Varier rotasjon/plassering og kontroller med støy eller svak kontur. | Kontroller om glasskanten følger beskytteren. Ved manglende kalibrering, analysefeil eller usikkert resultat skal systemet vise begrensningen fremfor å hevde en full automatisk PASS. Registrer feilsituasjonene og nødvendige justeringer. |
| TP17 | Fysisk prosess fra opptak til lagret resultat | Kjør `bash START_NANO.sh` på Nanoen med riggen. Kalibrer de fysiske målene. Kontroller opptak, analyse, GUI, SQLite og operatørvalg. | Riktig bilde, metadata og resultat hører til samme inspeksjon. Både riktig godkjenning og avvisning må prøves med faktiske beskyttere. Krever kamera, boks og tilsvarende lysoppsett. |
| TP18 | Behandlingstid | Registrer `elapsed_ms` og mål i tillegg hele prosessen fra start av opptak til resultatet er ferdig lagret og vist. Gjenta på Nanoen. | Oppgi målemetode, antall kjøringer, maskinvare og tider. `elapsed_ms` måles før den siste resultatlagringen og dekker ikke hele GUI-forløpet. Demotid på PC skal ikke oppgis som Nanoens inspeksjonstid. |

Ved beregning av modellens precision/recall må regelen for matching mellom annoterte bokser og deteksjoner være bestemt på forhånd. IoU-terskelen for slik evaluering er en egen beslutning og skal ikke forveksles med IoU-innstillingen for NMS i programmet.

## Registrering av forventet og observert resultat

For hver gjennomført test registreres test-ID, kravet/funksjonen, versjon og miljø, forventet resultat, faktisk resultat, bestått/ikke bestått og eventuelle avvik. Bruk Ikke utført der testen ikke er kjørt. Automatiske programvaretester, manuelle GUI-tester og fysiske modelltester dokumenteres hver for seg.

En fungerende demo dokumenterer programvareintegrasjonen. Den dokumenterer ikke alle de fysiske kravene eller at modellen har nådd ønsket nøyaktighet.
