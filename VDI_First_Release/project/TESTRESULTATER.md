# Testresultater for første release

Dato: 26. oktober 2026.

## Kjørt på Linux i denne kontrollen

Et nytt virtuelt Python-miljø ble opprettet, og `requirements-dev.txt` fra Linux-demoen ble installert. Hele Linux-testsuiten ble deretter kjørt:

```bash
python -m pytest -q -ra --junitxml=../../test-results/linux-tests.xml
```

Resultat: **56 bestått, 8 hoppet over, 0 feil**. De åtte testene som ble hoppet over, er Tk/GUI-tester og krever et grafisk display. De regnes ikke som bestått GUI-testing. Det ble ikke åpnet et GUI-vindu i denne kontrollen.

Miljø: Linux x86_64, Python 3.12.14, NumPy 2.5.4, OpenCV 4.10.0, Pillow 12.3.0 og pytest 9.1.1.

- [Rå pytest-logg](test-results/linux-tests.txt)
- [JUnit-resultater](test-results/linux-tests.xml)
- [Forventet og observert resultat for de ti automatiske demotilfellene](test-results/AUTOMATISKE_DEMORESULTATER.csv)

CSV-resultatene er hentet fra de beståtte `test_end_to_end`-tilfellene. Testene sammenligner faktisk beslutning og den lagrede beslutningen med forventet verdi. De kontrollerer også at originalbildet kan hentes fra databasen. Tabellen dokumenterer automatisk programvaretesting med syntetiske bilder og placeholder, ikke manuelle GUI-observasjoner eller modellnøyaktighet.

Kjøringen omfatter blant annet PASS/REJECT/ERROR, tilstedeværelse, form og mål på syntetiske bilder, bilde- og metadatalagring, feil ved filinnlasting og lagring, operatørvalg og eksport. Kameraadapterne kontrolleres med testdobler. At en slik test består, dokumenterer ikke et faktisk USB-kameraopptak.

## Ikke utført i denne kontrollen

- Manuell gjennomgang av GUI på et grafisk skrivebord.
- Fysisk ende-til-ende-test på Jetson Nano med Kiyo Pro og boks.
- Ferdig fysisk målekalibrering.
- Full vurdering av precision, recall, falske alarmer og oversette skader på et dokumentert uavhengig testsett.
- Fysiske tester av variasjon i lys, plassering og støy.
- Måling av full fysisk behandlingstid på Nano.

Nano-pakken inneholder tidligere modellkontroller i `nano/docs/NANO_BUILD_CHECK.json` og `nano/docs/NANO_MODEL_CHECK.json`. Disse er kontroller fra byggemiljøet og skal ikke tolkes som nye Nano-/kameratester i denne kjøringen.

[MANUELL_TESTLOGG.csv](test-results/MANUELL_TESTLOGG.csv) er en mal for videre testing. Alle radene starter med Ikke utført. Fyll inn observerte resultater og teststatus når testene faktisk gjennomføres. Se [TESTPLAN.md](TESTPLAN.md) for kravkoblingen og fremgangsmåtene.
