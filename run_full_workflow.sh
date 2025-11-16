#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Script unico per:
#  1) (opzionale) Creare il lab Azure (create_lab.sh)
#  2) Raccogliere l'inventario (inventory_collector/inventory_collector.py)
#  3) Eseguire il Configuration Analyzer (configuration_analyzer/validate.py)
#  4) Eseguire il Compliance Benchmark Evaluator (compliance_benchmark_evaluator/compliance.py)
#  5) Calcolare il Risk Score (risk_scorer/risk_scorer.py)
#  6) Generare il report PDF (reporting_engine/reporting_engine.py)
#
# Uso:
#   ./run_full_workflow.sh <SUBSCRIPTION_ID>
###############################################################################

if [ $# -ne 1 ]; then
  echo "Uso: $0 <SUBSCRIPTION_ID>"
  exit 1
fi

SUBSCRIPTION_ID="$1"

# Resource group
RESOURCE_GROUP="rg-miscfg-lab"

# File di output
INVENTORY_FILE="inventory_collector/inventory.json"
FINDINGS_FILE="configuration_analyzer/report.json"
COMPLIANCE_FILE="compliance_benchmark_evaluator/compliance.json"
RISK_FILE="risk_scorer/risk.json"
REPORTING_FILE="reporting_engine/report.pdf"

# File di configurazione
RULES_FILE="configuration_analyzer/rules.yaml"
COMPLIANCE_MAPPING_FILE="compliance_benchmark_evaluator/compliance_mapping_cis.yaml"

# echo "==> Imposto la subscription Azure su: $SUBSCRIPTION_ID"
# az account set --subscription "$SUBSCRIPTION_ID"

# echo
# echo "==> 2) Raccolta inventario Azure (inventory_collector/inventory_collector.py)"
# python3 inventory_collector/inventory_collector.py \
#   --subscription-id "$SUBSCRIPTION_ID" \
#   --resource-group "$RESOURCE_GROUP" \
#   --output "$INVENTORY_FILE"

echo
echo "==> 3) Configuration Analyzer (configuration_analyzer/validate.py -> $FINDINGS_FILE)"
python3 configuration_analyzer/validate.py \
  "$INVENTORY_FILE" \
  "$RULES_FILE" \
  "$FINDINGS_FILE"

echo
echo "==> 4) Compliance Benchmark Evaluator (compliance_benchmark_evaluator/compliance.py -> $COMPLIANCE_FILE)"
python3 compliance_benchmark_evaluator/compliance.py \
  "$FINDINGS_FILE" \
  "$COMPLIANCE_MAPPING_FILE" \
  "$COMPLIANCE_FILE"

echo
echo "==> 5) Risk Scorer (risk_scorer/risk_scorer.py -> $RISK_FILE)"
python3 risk_scorer/risk_scorer.py \
  "$INVENTORY_FILE" \
  "$FINDINGS_FILE" \
  "$COMPLIANCE_FILE" \
  "$RISK_FILE"

echo
echo "==> 6) Reporting Engine (reporting_engine/reporting_engine.py -> $REPORTING_FILE)"
python3 reporting_engine/reporting_engine.py \
  "$INVENTORY_FILE" \
  "$RISK_FILE" \
  "$COMPLIANCE_FILE" \
  "$REPORTING_FILE"

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