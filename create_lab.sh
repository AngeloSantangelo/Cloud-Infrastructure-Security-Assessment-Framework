#!/usr/bin/env bash
set -euo pipefail

# === Parametri personalizzabili =================================================
LOCATION="westeurope"
SQL_LOCATION="northeurope"
ADMIN_USER="labadmin"
ADMIN_PASS="LabPassword123!"
SQL_USER="sqladminuser"
SQL_PASS="SqlPassword123!"

# === Suffix per nomi globalmente unici ==========================================
SUFFIX=$(date +%s)

# === Nomi risorse ================================================================
RG="rg-miscfg-lab"
ST="st${SUFFIX}miscfg"          
KV="kv${SUFFIX}miscfg"          
NSG="nsg-miscfg"
VNET="vnet-miscfg"
SUBNET="snet-miscfg"
PIP="pip-miscfg"
NIC="nic-miscfg"
VM="vm-miscfg"
SQL="sql${SUFFIX}miscfg"        
DB="miscfgdb"
ASP="asp-miscfg"
WEB="web${SUFFIX}miscfg"        

# Ambiente di PRODUZIONE con dati ad ALTA sensibilità
TAGS_PROD_HIGH="env=prod sensitivity=high project=azure-misconfig-lab owner=student"

# Ambiente di PRODUZIONE con dati CRITICI (es. Key Vault, SQL)
TAGS_PROD_CRIT="env=prod sensitivity=critical project=azure-misconfig-lab owner=student"

# Ambiente di STAGE / PRE-PROD, sensibilità MEDIA
TAGS_STAGE="env=stage project=azure-misconfig-lab owner=student"

# Ambiente di DEV / sensibilità BASSA
TAGS_DEV="env=dev project=azure-misconfig-lab owner=student"


echo "==> Login e subscription correnti"
az account show -o table || true

echo "==> 1) Resource Group"
az group create -n "$RG" -l "$LOCATION" --tags $TAGS_PROD_HIGH -o table


echo "==> 2) Storage Account con accesso pubblico ai blob e TLS1.0 (MISCONFIG)"
az storage account create \
  -g "$RG" -n "$ST" -l "$LOCATION" \
  --sku Standard_LRS \
  --https-only false \
  --allow-blob-public-access true \
  --tags $TAGS_PROD_HIGH \
  -o table

# assicura che le Shared Key siano abilitate
az storage account update -g "$RG" -n "$ST" --min-tls-version TLS1_0 --allow-shared-key-access true -o table

echo "==> Recupero account key"
SAKEY="$(az storage account keys list -g "$RG" -n "$ST" --query "[0].value" -o tsv || true)"

# crea il container 'public' in uno dei due modi
echo "==> Crea container 'public' (MISCONFIG: pubblico)"
if [ -n "$SAKEY" ]; then
  az storage container create \
    --account-name "$ST" \
    --account-key "$SAKEY" \
    -n "public" \
    --public-access blob \
    -o table || FALLBACK_AD=1
else
  FALLBACK_AD=1
fi

# fallback: usa l’identità con RBAC/Azure AD
if [ "${FALLBACK_AD:-0}" = "1" ]; then
  echo "Key non utilizzabile: passo ad Azure AD (--auth-mode login)"
  # Assicurati di avere il ruolo RBAC: Storage Blob Data Contributor sullo scope dell'account
  az storage container create \
    --account-name "$ST" \
    -n "public" \
    --public-access blob \
    --auth-mode login \
    -o table
fi


echo "==> 3) Key Vault con Public Network Access abilitato e firewall permissivo (MISCONFIG)"
az keyvault create -n "$KV" -g "$RG" -l "$LOCATION" --public-network-access Enabled --tags $TAGS_PROD_CRIT -o table
# Imposta default action Allow e bypass (praticamente aperto da Internet, autenticazione a parte)
az keyvault update -n "$KV" --default-action Allow --bypass AzureServices -o table

echo "==> 4) Network Security Group con porte aperte da Internet (MISCONFIG)"
az network nsg create -g "$RG" -n "$NSG" -l "$LOCATION" --tags $TAGS_PROD_HIGH -o table
# SSH 22
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n "allow-ssh" \
  --priority 100 --access Allow --protocol Tcp --direction Inbound \
  --source-address-prefixes "*" --source-port-ranges "*" \
  --destination-port-ranges 22 -o table
# RDP 3389
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n "allow-rdp" \
  --priority 110 --access Allow --protocol Tcp --direction Inbound \
  --source-address-prefixes "*" --source-port-ranges "*" \
  --destination-port-ranges 3389 -o table
# HTTP 80
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n "allow-http" \
  --priority 120 --access Allow --protocol Tcp --direction Inbound \
  --source-address-prefixes "*" --source-port-ranges "*" \
  --destination-port-ranges 80 -o table
# SQL 1433
az network nsg rule create -g "$RG" --nsg-name "$NSG" -n "allow-sql" \
  --priority 130 --access Allow --protocol Tcp --direction Inbound \
  --source-address-prefixes "*" --source-port-ranges "*" \
  --destination-port-ranges 1433 -o table

echo "==> 5) Rete + IP pubblico (Statico) + NIC associata al NSG (MISCONFIG)"
az network public-ip create -g "$RG" -n "$PIP" -l "$LOCATION" --sku Standard --allocation-method Static --tags $TAGS_PROD_HIGH -o table
az network vnet create -g "$RG" -n "$VNET" -l "$LOCATION" --address-prefix 10.10.0.0/16 \
  --subnet-name "$SUBNET" --subnet-prefix 10.10.1.0/24 --tags $TAGS_PROD_HIGH -o table
az network nic create -g "$RG" -n "$NIC" --vnet-name "$VNET" --subnet "$SUBNET" \
  --network-security-group "$NSG" --public-ip-address "$PIP" --tags $TAGS_PROD_HIGH -o table

echo "==> 6) VM Linux con password auth (MISCONFIG) e IP pubblico"
az vm create -g rg-miscfg-lab -n vm-miscfg \
  --image Ubuntu2204 \
  --admin-username labadmin \
  --admin-password 'LabPassword123!' \
  --authentication-type password \
  --nics nic-miscfg \
  --size Standard_B1s \
  --public-ip-sku Standard \
  --tags $TAGS_DEV \
  -o table

echo "==> 7) Azure SQL Server + DB con firewall 0.0.0.0/0 e public network access (MISCONFIG)"
if ! az sql server create -l "$SQL_LOCATION" -g "$RG" -n "$SQL" \
  --admin-user "$SQL_USER" --admin-password "$SQL_PASS" --tags $TAGS_PROD_CRIT \
  -o table; then
  echo "Creazione SQL server fallita in $SQL_LOCATION; provo a UK South..."
  SQL_LOCATION="uksouth"
  az sql server create -l "$SQL_LOCATION" -g "$RG" -n "$SQL" \
    --admin-user "$SQL_USER" --admin-password "$SQL_PASS" -o table
fi

# Rete pubblica: molte CLI recenti abilitano già la public network; in caso contrario, prova l'update
az sql server update -g "$RG" -n "$SQL" --enable-public-network true -o table || true

# Regola firewall TUTTI gli IP (MISCONFIG)
az sql server firewall-rule create -g "$RG" -s "$SQL" -n "AllowAll" \
  --start-ip-address 0.0.0.0 --end-ip-address 255.255.255.255 -o table

az sql db create -g "$RG" -s "$SQL" -n "$DB" --service-objective Basic --tags $TAGS_PROD_HIGH -o table || \
az sql db create -g "$RG" -s "$SQL" -n "$DB" --service-objective S0 --tags $TAGS_PROD_HIGH -o table


echo "==> 8) App Service Plan + Web App con HTTPS-only DISABILITATO e FTP consentito (MISCONFIG)"

# Regione dedicata per App Service
APP_LOCATION="northeurope"

# App Service Plan (Linux)
az appservice plan create -g "$RG" -n "$ASP" -l "$APP_LOCATION" --sku F1 --is-linux --tags $TAGS_STAGE -o table

# Web App
az webapp create -g "$RG" -p "$ASP" -n "$WEB" --runtime "PYTHON:3.11" --tags $TAGS_STAGE -o table

# Misconfig intenzionali
az webapp update -g "$RG" -n "$WEB" --https-only false -o table
az webapp config set -g "$RG" -n "$WEB" --ftps-state AllAllowed -o table
az webapp config set -g "$RG" -n "$WEB" --always-on false -o table || true

echo "Web App URL:"
az webapp show -g "$RG" -n "$WEB" --query "defaultHostName" -o tsv


echo
echo "====================== RIEPILOGO (MISCONFIG) ======================"
echo "Resource Group:     $RG  ($LOCATION)"
echo "Storage Account:    $ST  [public blob access, TLS1.0, https-only DISABILITATO]"
echo "Key Vault:          $KV  [Public Network Access Enabled; firewall Allow]"
echo "NSG:                $NSG [22, 3389, 80, 1433 aperte da Internet]"
echo "Public IP:          $(az network public-ip show -g "$RG" -n "$PIP" --query ipAddress -o tsv)"
echo "VM:                 $VM  [password auth abilitata]"
echo "SQL Server:         $SQL [firewall 0.0.0.0/0]  DB=$DB"
echo "Web App:            $WEB [HTTPS-only OFF, FTP/FTPS ON]"
echo
echo "Credenziali di laboratorio (NON SICURE):"
echo "  VM -> $ADMIN_USER / $ADMIN_PASS"
echo "  SQL -> $SQL_USER / $SQL_PASS"
echo
echo "FINISH"