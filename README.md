# Xemex voor Home Assistant

Lees je Xemex Smart Connect uit in Home Assistant via MQTT of Modbus TCP. Je kiest de verbinding bij het toevoegen van de integratie. Versie: 0.2.0.

## Functies

- Sensoren voor vermogen, spanning, stroom en, afhankelijk van het profiel, energie.
- Ondersteuning voor één- en driefasige aansluitingen.
- MQTT met automatische ontdekking of handmatig ingestelde basistopic. Bestaande MQTT-configuraties blijven behouden.
- Modbus TCP met instelbaar meetinterval van 1–3600 seconden (standaard 10 seconden). Alleen uitlezen: geen wijzigingen aan apparaatinstellingen of firmware.
- Modbus-profielen Basis (spanning, stroom en vermogen) en Uitgebreid (ook energie en aanvullende metingen).

## Installeren

### Via HACS (voorkeur)

Let op: deze repository staat nu alleen lokaal en is nog niet geschikt voor installatie via HACS. Daarvoor moet de integratie eerst in de juiste HACS-mapstructuur op GitHub worden gepubliceerd. Er is nog geen repository-URL om toe te voegen.

Zodra die beschikbaar is:

1. Open HACS in Home Assistant en kies via het menu rechtsboven **Aangepaste repositories**.
2. Voeg de GitHub-repository-URL toe met type **Integratie**.
3. Zoek **Xemex** in HACS en download de integratie.
4. Herstart Home Assistant.
5. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen → Xemex**.
6. Kies **MQTT** of **Modbus TCP** en vul de verbindingsgegevens in.

### Handmatig kopiëren (alternatief)

1. Kopieer de map `candidate/custom_components/xemex` uit deze repository naar `custom_components/xemex` in de configuratiemap van Home Assistant. Het bestand staat daarna op `/config/custom_components/xemex/manifest.json` bij een standaardinstallatie. Vervang bij een update de bestaande integratiemap; maak vooraf een back-up.
2. Herstart Home Assistant.
3. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen → Xemex**.
4. Kies **MQTT** of **Modbus TCP** en vul de verbindingsgegevens in.

### MQTT instellen

Configureer eerst de MQTT-integratie van Home Assistant en laat de Smart Connect naar dezelfde broker publiceren. Vul als basistopic `devices/<site>/smart-connect/<serienummer>` in, zonder `/data/power_instant`.

### Modbus TCP instellen

Vul het IP-adres of de hostnaam, de TCP-poort (standaard 502) en het Smart Connect-serienummer van het etiket in. Kies het meetinterval, het aantal fasen en het registerprofiel.

Kies bij energie-eenheid **Wh** voor firmware V5.1.x of nieuwer en **kWh** voor oudere firmware. Controleer hiervoor de firmwareversie van je apparaat.

De Smart Connect ondersteunt maar één Modbus TCP-client tegelijk. Gebruik deze verbinding niet tegelijk met een laadpaal, EMS of andere Modbus-client. Een interval van 1 seconde betekent niet dat de meter elke seconde nieuwe gegevens levert.

## Goed om te weten

Voeg hetzelfde serienummer niet tweemaal toe, ook niet via verschillende verbindingen. Modbus-instellingen kun je later via **Herconfigureren** aanpassen; het serienummer blijft vast.

Bij oudere firmware die MQTT-energie in kWh publiceert kan de bestaande MQTT-omrekening een te lage energiewaarde geven. De firmwarekeuze hierboven geldt alleen voor Modbus.

## Ontwikkeling

De integratie staat in `candidate/custom_components/xemex/` en de tests in `tests/`. `baseline/` bevat de oorspronkelijke MQTT-broncode voor regressietests; installeer die map niet. Testafhankelijkheden staan in `requirements-test.txt`. De lokale tests zijn opgezet voor Home Assistant 2026.10.4 en Python 3.14; andere versies zijn niet gevalideerd.

Voer vanuit de repository `python -m pytest tests -v` uit in een omgeving met deze afhankelijkheden. De tests gebruiken lokale simulators; ze vervangen geen controle met de fysieke Smart Connect.
