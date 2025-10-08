#!/usr/bin/env bash
set -euo pipefail

# ========= Parametri =========
RG="${RG:-rg-miscfg-lab}"          # override: RG=myrg ./create_lab.sh
LOC="${LOC:-westeurope}"
# suffisso molto univoco (timestamp + random)
SUFFIX="${SUFFIX:-$(date +%s)$RANDOM}"
TAGS="${TAGS:-project=thesis env=lab}"
: "${PLAN:=}"    # sempre definita, anche se salti la sezione WebApp
: "${APP:=}"     # idem
# =============================

echo "==> Verifica Azure CLI / login"
command -v az >/dev/null 2>&1 || { echo "Azure CLI (az) non trovato."; exit 1; }
az account show >/dev/null 2>&1 || { echo "Esegui prima: az login"; exit 1; }

echo "==> Crea/riusa Resource Group: $RG ($LOC)"
az group create -n "$RG" -l "$LOC" --tags $TAGS >/dev/null

# ---- 1) Storage Account con misconfig ----
STG="st${SUFFIX}miscfg"  # nome globale univoco
echo "==> Storage Account: $STG (httpsOnly=false, allowBlobPublicAccess=true, TLS1_0)"
az storage account create \
  -n "$STG" -g "$RG" -l "$LOC" \
  --sku Standard_LRS --kind StorageV2 \
  --https-only false \
  --allow-blob-public-access true \
  --tags $TAGS >/dev/null
# forza TLS1_0 dove possibile (se non supportato, ignora senza fermare lo script)
set +e
az storage account update -n "$STG" -g "$RG" --set minimumTlsVersion=TLS1_0 >/dev/null
set -e

# ---- 2) Key Vault pubblico ----
KV="kv${SUFFIX}miscfg"
echo "==> Key Vault: $KV (PublicNetworkAccess=Enabled, no firewall rules)"
az keyvault create \
  -n "$KV" -g "$RG" -l "$LOC" \
  --public-network-access Enabled \
  --tags $TAGS >/dev/null

# ---- 3) NSG con SSH/RDP aperti ----
NSG="nsg-miscfg"
echo "==> NSG: $NSG (regole SSH/RDP aperte da Internet)"
az network nsg create -g "$RG" -n "$NSG" -l "$LOC" --tags $TAGS >/dev/null

# SSH 22/tcp da qualsiasi IP
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n allow-ssh-any \
  --priority 1000 --direction Inbound --access Allow --protocol Tcp \
  --source-address-prefixes "*" --destination-port-ranges 22 >/dev/null

# RDP 3389/tcp da qualsiasi IP (la riga “tronca” va rimpiazzata con questa)
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n allow-rdp-any \
  --priority 1001 --direction Inbound --access Allow --protocol Tcp \
  --source-address-prefixes "*" --destination-port-ranges 3389 >/dev/null


# ---- 4) Public IP (creato PRIMA della Web App) ----
PIP="pip-miscfg"
echo "==> Public IP: $PIP (Standard, Static, non associato)"
az network public-ip create \
  -g "$RG" -n "$PIP" -l "$LOC" \
  --sku Standard --version IPv4 --allocation-method Static \
  --tags $TAGS >/dev/null

# ---- 5) App Service Plan + Web App (retry non bloccante) ----
PLAN="asp-free-miscfg"
APP="app${SUFFIX}miscfg"
echo "==> App Service Plan: $PLAN (F1) + Web App: $APP (httpsOnly=false)"
az appservice plan create -g "$RG" -n "$PLAN" --sku F1 -l "$LOC" --tags $TAGS >/dev/null

create_webapp() {
  local name="$1"
  if az webapp create -g "$RG" -p "$PLAN" -n "$name" --runtime "DOTNET:6" >/dev/null; then
    az webapp update -g "$RG" -n "$name" --set httpsOnly=false >/dev/null || \
      echo "WARN: set httpsOnly=false fallito per $name"
    echo "$name"
    return 0
  else
    return 1
  fi
}

if ! CREATED_NAME="$(create_webapp "$APP")"; then
  echo "WARN: creazione Web App fallita per '$APP' (nome non unico o quota). Ritento con nome nuovo..."
  NEW_APP="app$(date +%s)$RANDOMmiscfg"
  if CREATED_NAME="$(create_webapp "$NEW_APP")"; then
    APP="$CREATED_NAME"
  else
    echo "WARN: anche il retry della Web App è fallito. Continuo senza Web App."
    APP=""
  fi
else
  APP="$CREATED_NAME"
fi

# # 6) Azure SQL Server (firewall aperto a Internet)
# SQL_SRV="sqlsrv${SUFFIX}miscfg"
# SQL_ADMIN="sqladmin$RANDOM"
# SQL_PW="$(tr -dc 'A-Za-z0-9!@#%^&*_=+' </dev/urandom | head -c 24)"
# echo "==> Azure SQL Server: $SQL_SRV (misconfig: firewall aperto a Internet)"
# set +e
# az sql server create -g "$RG" -n "$SQL_SRV" -l "$LOC" -u "$SQL_ADMIN" -p "$SQL_PW" --tags $TAGS --only-show-errors
# SQL_RC=$?
# if [[ $SQL_RC -ne 0 ]]; then
#   echo "ERR: creazione SQL Server fallita (rc=$SQL_RC)."
# else
#   az sql server firewall-rule create -g "$RG" -s "$SQL_SRV" -n AllowAll \
#     --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --only-show-errors || \
#     echo "WARN: firewall 'AllowAll' rifiutato (policy?)."
# fi
# set -e

# # 7) Azure Container Registry (ACR) con admin user abilitato
# ACR="acr${SUFFIX}miscfg"
# echo "==> ACR: $ACR (misconfig: admin user enabled)"
# set +e
# az acr create -n "$ACR" -g "$RG" -l "$LOC" --sku Basic --admin-enabled true --tags $TAGS >/dev/null 2>&1
# if [[ $? -ne 0 ]]; then
#   echo "WARN: creazione ACR fallita (nome non unico/quota). Continuo."
# fi
# set -e

# # 8) Cosmos DB (tentativo di rendere permissivo ipRangeFilter)
# COSMOS="cosmos${SUFFIX}miscfg"
# echo "==> CosmosDB: $COSMOS (misconfig: ipRangeFilter permissivo se consentito)"
# set +e
# az cosmosdb create -n "$COSMOS" -g "$RG" -l "$LOC" --kind GlobalDocumentDB --tags $TAGS --only-show-errors
# COS_RC=$?
# if [[ $COS_RC -ne 0 ]]; then
#   echo "ERR: creazione CosmosDB fallita (rc=$COS_RC)."
# else
#   # Evita valori non supportati. Se ti serve l’accesso dal tuo IP:
#   # MYIP=$(curl -s ifconfig.me)  # oppure passalo via env
#   # az cosmosdb network-rule add -g "$RG" -n "$COSMOS" --ip-address "$MYIP" --only-show-errors
#   :
# fi
# set -e


# ---- Salva variabili per distruzione comoda ----
ENVFILE=".lab_env_${RG}.sh"
cat > "$ENVFILE" <<EOF
export RG="$RG"
export LOC="$LOC"
export STG="$STG"
export KV="$KV"
export NSG="$NSG"
export PLAN="${PLAN:-}"
export APP="${APP:-}"
export PIP="${PIP:-}"
export SQL_SRV="${SQL_SRV:-}"
export ACR="${ACR:-}"
export COSMOS="${COSMOS:-}"
EOF

echo "==> Fatto."
echo "RG: $RG | LOC: $LOC"
echo "STORAGE: $STG | KEYVAULT: $KV | NSG: $NSG | PIP: $PIP"
if [[ -n "${APP:-}" ]]; then
  echo "WEBAPP: $APP (httpsOnly=false)"
else
  echo "WEBAPP: non creata (vedi WARN sopra)"
fi
echo "Variabili salvate in: $ENVFILE"
