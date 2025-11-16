#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Script unico per:
#  1) Creare il lab Azure (create_lab.sh)
#  2) Raccogliere l'inventario (inventory_collector.py)
#  3) Eseguire il Configuration Analyzer (validate.py)
#  4) Eseguire il Compliance Benchmark Evaluator (compliance.py)
#  5) Calcolare il Risk Score (risk_scorer.py)
#
# Uso:
#   ./run_full_workflow.sh <SUBSCRIPTION_ID>
#
# Output generati:
#   - inventory.json
#   - findings.json
#   - compliance.json
#   - risk.json
###############################################################################

if [ $# -ne 1 ]; then
  echo "Uso: $0 <SUBSCRIPTION_ID>"
  exit 1
fi

SUBSCRIPTION_ID="$1"

# Nomi del Resource Group e dei file di output
RESOURCE_GROUP="rg-miscfg-lab"
INVENTORY_FILE="inventory.json"
FINDINGS_FILE="report.json"
COMPLIANCE_FILE="compliance.json"
RISK_FILE="risk.json"
REPORTING_FILE="report.pdf"

echo "==> Imposto la subscription Azure su: $SUBSCRIPTION_ID"
az account set --subscription "$SUBSCRIPTION_ID"

echo
echo "==> 2) Raccolta inventario Azure (inventory_collector.py)"
python3 inventory_collector.py \
  --subscription-id "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --output "$INVENTORY_FILE"

echo
echo "==> 3) Configuration Analyzer (validate.py -> $FINDINGS_FILE)"
python3 validate.py \
  "$INVENTORY_FILE" \
  "rules.yaml" \
  "$FINDINGS_FILE"

echo
echo "==> 4) Compliance Benchmark Evaluator (compliance.py -> $COMPLIANCE_FILE)"
python3 compliance.py \
  "$FINDINGS_FILE" \
  "compliance_mapping_cis.yaml" \
  "$COMPLIANCE_FILE"

echo
echo "==> 5) Risk Scorer (risk_scorer.py -> $RISK_FILE)"
python3 risk_scorer.py \
  "$INVENTORY_FILE" \
  "$FINDINGS_FILE" \
  "$COMPLIANCE_FILE" \
  "$RISK_FILE"

echo
echo "==> 6) Reporting Engine (reporting_engine.py -> $REPORTING_FILE)"
python3 reporting_engine.py \
  "$INVENTORY_FILE" \
  "$RISK_FILE" \
  "$COMPLIANCE_FILE" \
  "$REPORTING_FILE" \

echo
echo "=================================================================="
echo "Pipeline completata."
echo "File generati:"
echo "  - $INVENTORY_FILE   (inventario Azure)"
echo "  - $FINDINGS_FILE    (risultati Configuration Analyzer)"
echo "  - $COMPLIANCE_FILE  (stato CIS PASS/FAIL per controllo)"
echo "  - $RISK_FILE        (punteggio di rischio complessivo)"
echo "  - $REPORTING_FILE   (report PDF pronto per l'utente)"
echo "=================================================================="
