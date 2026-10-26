# Visual Defect Inspector

Prosjektet undersøker skjermbeskyttere med kamera i en boks med fast belysning. Det følger med to versjoner:

- `project/linux-demo`: demo med simulert kamera og placeholder for defektmodellen. Denne kan kjøres uten utstyret vårt.
- `project/nano`: versjonen for Jetson Nano, med de trente modellene og oppsettet for Razer Kiyo Pro.

## Linux-demo

Last ned og pakk ut branchen `project-first-release`. Åpne en terminal i mappen der denne README-filen ligger. Kommandoene er for Ubuntu 22.04/24.04 med grafisk skrivebord og systemets Python 3.10–3.12:

```bash
sudo apt update
sudo apt install -y python3-venv python3-tk
cd project/linux-demo
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python START_DEMO.py
```

PyCharm er ikke nødvendig. Ved senere oppstart åpnes en terminal i `project/linux-demo`, og følgende kjøres:

```bash
.venv/bin/python START_DEMO.py
```

Trykk på knappen for å ta bilde og analysere neste skjermbeskytter. Demoen går automatisk gjennom genererte eksempler med og uten feil. Velg Pass eller Reject etter analysen. Resultater og bilder lagres i SQLite og kan vises i History. Statistics og eksport kan også prøves.

Kameraet og defektmodellens svar er simulert. OpenCV-kontrollene for tilstedeværelse, form og mål kjøres på de genererte bildene. Demoen lar vurdereren prøve programvarefunksjonene og arbeidsflyten uten kamera og boks; den viser ikke modellens nøyaktighet på ekte skader.

## Jetson Nano

Last ned samme branch på Nanoen. Åpne en terminal i mappen der denne README-filen ligger, på Nanoens grafiske skrivebord:

```bash
cd project/nano
bash START_NANO.sh
```

Første start installerer avhengigheter og kontrollerer de inkluderte modellene før GUI-et åpnes. Installasjonen kan be om sudo-passord og trenger nett dersom Ubuntu-pakker mangler. Senere starter bruker det samme miljøet. Modellene kjøres på CPU med ONNX Runtime.

Kamera, avstand og belysning må tilpasses det fysiske oppsettet. Innstillingene ligger i `project/nano/config/inspection.json`. Fysisk målekalibrering er ikke ferdig utfylt i den vedlagte konfigurasjonen og må gjøres på riggen. Derfor kan en inspeksjon vise INCOMPLETE før kalibreringen er fullført. Linux-demoen brukes når dette utstyret ikke er tilgjengelig.
