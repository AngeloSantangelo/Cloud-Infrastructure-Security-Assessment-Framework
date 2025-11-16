# Cloud-Infrastructure-Security-Assessment-Framework
Il presente lavoro presenta un framework per la valutazione di sicurezza delle configurazioni cloud focalizzato sul provider **Microsoft Azure**. Il framework implementa cinque componenti chiave:
- **Cloud Inventory Collector**: enumerazione e raccolta delle configurazioni delle risorse in un Resource Group;
- **Configuration Analyzer**: validazione di regole di sicurezza sulle configurazioni raccolte.
- **Compliance Benchmark Evaluator**: aggregazione dei findings rispetto a un benchmark di riferimento (CIS Microsoft Azure Benchmark) e generazione di un report di compliance.
- **Risck Scorer**: calcolatore punteggio di rischio del Resource Group.
- **Reporting Engine**: aggregazione di risultati e creazione di un report pronto per l'utente.
L’**obiettivo** è automatizzare la discovery e il controllo delle principali misconfigurations che espongono l’ambiente a rischi (es. porte aperte, firewall permissivi, password deboli, ecc.).

## Architettura
<img width="464" height="675" alt="image" src="https://github.com/user-attachments/assets/82fdb2c7-cd81-4e2c-acfe-a0a8efb04adf" />

## Flusso del Framework
<img width="1472" height="948" alt="image" src="https://github.com/user-attachments/assets/5aec6cdf-44ed-4fd2-89a8-02b88c2ff780" />


## Requirements
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) per eseguire il provisioning dell'infrastruttura.
- Account/Sottoscrizione Azure (i.e. Azure for Students).
- [Python (v^3)](https://www.python.org/downloads/)
- Altri Requisiti:
```bash

pip install -r requirements.txt

```
## Descrizione dei File
Ogni cartella rappresenta un modulo del Framework contenente i corrispondenti file di codice per la loro operatività.
- **create_lab.sh**: rappresenta il file per automatizzare il provisioning dell'infrastruttura (creazione del Resource Group su Azure)
- **unistall.sh**: rappresenta il file per automatizzare il de-provisioning dell'infrastruttura.
- **inventory_collector.py**: rappresenta l'Inventory Collector. Enumera tutte le risorse, con le relative proprietà e configurazioni, sottoforma di inventario JSON.
- **rules.yaml**: rappresenta il file contenente le regole YAML.
- **validate.py**: rappresenta il Configuration Analyzer. Valida le configurazioni delle risorse Azure confrontandole con le regole definite in YAML e genera un report JSON contenente esclusivamente le risorse non conformi.
- **compliance_mapping_cis.yaml**: rappresenta il file contenente le regole esistenti nel benchmark "CIS Microsoft Azure Benchmark" corrispondenti alle regole YAML nel file "rules.yaml".
- **compliance.py**: rappresenta il Compliance Benchmark Evaluator, il modulo che valuta la mappatura delle regole YAML con le regole del benchmark CIS.
- **risk_scorer.py**: rappresenta il Risk Scorer, il modulo che, sulla base delle configurazioni raccolte circa le risorse Azure, calcola un punteggio di rischio riguardo l'ambiente.
- **reporting_engine.py**: rappresenta il Reporting Engine, il modulo che raccoglie tutti i risultati e li aggrega in un unico file PDF pronto per l'utente.

## Clonazione del Progetto e Configurazione dell'infrastruttura di Azure
Per iniziare, clona il repository sul tuo Computer locale utilizzando il comando `git clone` nel seguente modo:

```bash

git clone https://github.com/AngeloSantangelo/Cloud-Infrastructure-Security-Assessment-Framework.git

```
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

## Esecuzione del Framework
Per automatizzare l'esecuzione di ogni modulo, e quindi dell'intero framework, bisogna fare riferimento al file "run_full_workflow.sh", il quale è in grado di eseguire tutti i moduli insieme e portare l'utente a visulizzare subito i risultati. 
Prima di tutto, bisogna inferire i permessi di esecuzione al file con il seguente comando:
```bash

chmod +x run_full_workflow.sh

```
Successivamente, può essere lanciato con il seguente comando:
```bash

./run_full_workflow.sh <SUBSCRIPTION_ID>

```
