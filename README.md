# Cloud-Infrastructure-Security-Assessment-Framework

## Requirements
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) per eseguire il provisioning dell'infrastruttura.
- Account/Sottoscrizione Azure (i.e. Azure for Students).
- Requisiti per l'Inventory Collector:
```bash

pip install -r requirements.txt

```
## Configurazione dell'infrastruttura di Azure
Per automatizzare la procedura di provisioning delle risorse, è stato sviluppato uno script Bash (create_lab.sh). Puoi personalizzare sia le risorse sia le variabili d'ambiente, specificando i valori appropriati per la propria architettura. Una volta completata la configurazione, esegui il seguente comando per avviare il processo di installazione:
```bash

bash create_lab.sh

```
Questo comando garantirà l'esecuzione del provisioning dell'infrastruttura con le impostazioni personalizzate definite nel file "create_lab.sh".

Un ulteriore script Bash (uninstall.sh) è stato implementato per automatizzare il processo di eliminazione di tutte le risorse precedentemente create. Analogamente al processo di installazione, è necessario personalizzare sia le risorse che le variabili d'ambiente per la propria architettura. Per avviare questa procedura, esegui il seguente comando:
```bash

bash uninstall.sh

```
L'esecuzione di questo comando garantirà la corretta eliminazione di tutte le risorse create durante il provisioning, semplificando così il processo di deprovisioning dell'infrastruttura.
