set -euo pipefail

# Se presente, carica l'env generato in creazione
if [[ -f ".lab_env_${RG:-rg-miscfg-lab}.sh" ]]; then
  source ".lab_env_${RG:-rg-miscfg-lab}.sh"
fi

RG="${RG:-rg-miscfg-lab}"
NOWAIT="${NOWAIT:-true}"

echo "==> Verifica Azure CLI / login"
command -v az >/dev/null 2>&1 || { echo "Azure CLI (az) non trovato."; exit 1; }
az account show >/dev/null 2>&1 || { echo "Esegui prima: az login"; exit 1; }

echo "==> Elimino Resource Group: $RG"
if [[ "${NOWAIT}" == "true" ]]; then
  az group delete -n "$RG" --yes --no-wait
  echo "Richiesta di eliminazione inviata (asincrona)."
else
  az group delete -n "$RG" --yes
  echo "Resource Group eliminato."
fi

# opzionale: rimuovi il file env
ENVFILE=".lab_env_${RG}.sh"
if [[ -f "$ENVFILE" ]]; then
  rm -f "$ENVFILE"
fi
