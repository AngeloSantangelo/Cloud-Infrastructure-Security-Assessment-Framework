# import json
# from datetime import datetime, timezone

# from azure.identity import DefaultAzureCredential
# from azure.mgmt.resource import ResourceManagementClient
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.keyvault import KeyVaultManagementClient

# # ======= CONFIG =======
# SUBSCRIPTION_ID = "507c29d9-8bd6-4976-8e7b-5b3e56f25bf8"   # <-- metti la tua subscription
# RESOURCE_GROUP  = "rg-miscfg-lab"                           # <-- il tuo RG
# OUTPUT_PATH     = "rg-inventory.json"                       # <-- file output
# # ======================

# cred = DefaultAzureCredential(exclude_shared_token_cache_credential=True)

# res_client   = ResourceManagementClient(cred, SUBSCRIPTION_ID)
# st_client    = StorageManagementClient(cred, SUBSCRIPTION_ID)
# kv_client    = KeyVaultManagementClient(cred, SUBSCRIPTION_ID)

# def bool_or_none(x):
#     return None if x is None else bool(x)

# def storage_public_access(account):
#     """
#     Heuristics “public_access” per Storage Account:
#     - allow_blob_public_access == True  -> True
#     - network_rule_set.default_action == 'Allow' AND nessuna regola IP/VNet -> True
#     - altrimenti False
#     """
#     try:
#         props = st_client.storage_accounts.get_properties(account.id.split('/')[4], account.name)  # rg from ID
#         allow_blob_public = getattr(props, "allow_blob_public_access", None)
#         nrs = getattr(props.network_rule_set, "default_action", None) if getattr(props, "network_rule_set", None) else None
#         ip_rules   = len(props.network_rule_set.ip_rules) if getattr(props, "network_rule_set", None) and props.network_rule_set.ip_rules else 0
#         vnet_rules = len(props.network_rule_set.virtual_network_rules) if getattr(props, "network_rule_set", None) and props.network_rule_set.virtual_network_rules else 0

#         if allow_blob_public is True:
#             return True
#         if nrs == "Allow" and ip_rules == 0 and vnet_rules == 0:
#             return True
#         return False
#     except Exception:
#         # in caso di permessi/feature mancanti -> indeterminato
#         return None

# def keyvault_public_access(vault):
#     """
#     Heuristics “public_access” per Key Vault:
#     - properties.public_network_access == 'Enabled' E
#     - (network_acls.default_action == 'Allow' O assenti regole)
#     -> True
#     """
#     try:
#         rg_name = vault.id.split('/')[4]
#         v = kv_client.vaults.get(rg_name, vault.name)
#         pna = getattr(v.properties, "public_network_access", None)   # 'Enabled' | 'Disabled' | None
#         acls = getattr(v.properties, "network_acls", None)
#         default_action = getattr(acls, "default_action", None) if acls else None
#         if pna == "Enabled" and (default_action in (None, "Allow")):
#             return True
#         if pna == "Disabled":
#             return False
#         return None
#     except Exception:
#         return None

# def safe_get_creation_date(resource):
#     """
#     La 'creation_date' non è standard su tutte le risorse.
#     Proviamo:
#     - tag comuni (creationDate, created, CreatedDate)
#     - altrimenti None
#     """
#     tags = getattr(resource, "tags", None) or {}
#     for k in ["creationDate", "created", "CreatedDate"]:
#         if k in tags:
#             return str(tags[k])
#     return None

# def enrich_public_access(res):
#     t = res.type.lower()
#     if t == "microsoft.storage/storageaccounts":
#         return storage_public_access(res)
#     if t == "microsoft.keyvault/vaults":
#         return keyvault_public_access(res)
#     # per altri tipi lascia indeterminato (None)
#     return None

# def main():
#     items = []
#     collected_at = datetime.now(timezone.utc).isoformat()

#     for r in res_client.resources.list_by_resource_group(RESOURCE_GROUP):
#         entry = {
#             "resource_id": r.id,
#             "name": r.name,
#             "type": r.type,            # es: "Microsoft.Storage/storageAccounts"
#             "region": r.location,
#             "subscription_id": SUBSCRIPTION_ID,
#             "resource_group": RESOURCE_GROUP,
#             "tags": r.tags or {},
#             "public_access": enrich_public_access(r),  # True/False/None
#             "creation_date": safe_get_creation_date(r),# se trovata in tag, altrimenti None
#             "collected_at": collected_at,
#         }
#         items.append(entry)

#     with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
#         json.dump(items, f, ensure_ascii=False, indent=2)

#     print(f"[OK] Salvato inventario: {OUTPUT_PATH} ({len(items)} risorse)")

# if __name__ == "__main__":
#     main()




import json
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient

# ====== CONFIG ======
SUBSCRIPTION_ID = "507c29d9-8bd6-4976-8e7b-5b3e56f25bf8"   # <-- metti la tua subscription
RESOURCE_GROUP  = "rg-miscfg-lab"                           # <-- il tuo RG
OUTPUT_PATH     = "rg-inventory.json"                       # <-- file output
# ====================

cred = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
res_client  = ResourceManagementClient(cred, SUBSCRIPTION_ID)
st_client   = StorageManagementClient(cred, SUBSCRIPTION_ID)
kv_client   = KeyVaultManagementClient(cred, SUBSCRIPTION_ID)
net_client  = NetworkManagementClient(cred, SUBSCRIPTION_ID)
web_client  = WebSiteManagementClient(cred, SUBSCRIPTION_ID)

def safe_bool(x): return None if x is None else bool(x)

def check_storage(account):
    rg = account.id.split("/")[4]
    props = st_client.storage_accounts.get_properties(rg, account.name)
    return {
        "public_access": safe_bool(getattr(props, "allow_blob_public_access", None)),
        "https_only": safe_bool(getattr(props, "supports_https_traffic_only", None)),
        "minimum_tls_version": getattr(props, "minimum_tls_version", None),
        "network_default_action": getattr(
            getattr(props, "network_rule_set", None), "default_action", None
        )
    }

def check_keyvault(vault):
    rg = vault.id.split("/")[4]
    kv = kv_client.vaults.get(rg, vault.name)
    props = kv.properties
    return {
        "public_network_access": getattr(props, "public_network_access", None),
        "network_default_action": getattr(
            getattr(props, "network_acls", None), "default_action", None
        )
    }

def check_nsg(nsg):
    rg = nsg.id.split("/")[4]
    n = net_client.network_security_groups.get(rg, nsg.name)
    ssh = False
    rdp = False
    for rule in (n.security_rules or []):
        if rule.direction == "Inbound" and rule.access == "Allow":
            if rule.source_address_prefix in ["*", "0.0.0.0/0", "Internet"]:
                if str(rule.destination_port_range) in ["22", "22-22"]:
                    ssh = True
                if str(rule.destination_port_range) in ["3389", "3389-3389"]:
                    rdp = True
    return {"nsg_allows_ssh_any": ssh, "nsg_allows_rdp_any": rdp}

def check_webapp(site):
    rg = site.id.split("/")[4]
    s = web_client.web_apps.get(rg, site.name)
    return {"https_only": safe_bool(s.https_only)}

sql_client = SqlManagementClient(cred, SUBSCRIPTION_ID)
def check_sql_server(srv):
    rg = srv.id.split("/")[4]
    try:
        rules = sql_client.server_firewall_rules.list_by_server(rg, srv.name)
        for r in rules:
            s = str(getattr(r, "start_ip_address", "")).strip()
            e = str(getattr(r, "end_ip_address", "")).strip()
            if s in ("0.0.0.0", "0.0.0.0/0") or e in ("0.0.0.0", "0.0.0.0/0"):
                return {"sql_firewall_allows_internet": True}
        return {"sql_firewall_allows_internet": False}
    except Exception:
        return {"sql_firewall_allows_internet": None}
    

acr_client = ContainerRegistryManagementClient(cred, SUBSCRIPTION_ID)
def check_acr(reg):
    rg = reg.id.split("/")[4]
    try:
        props = acr_client.registries.get(rg, reg.name)
        admin = getattr(props, "admin_user_enabled", None)
        return {"acr_admin_user_enabled": None if admin is None else bool(admin)}
    except Exception:
        return {"acr_admin_user_enabled": None}
    

cosmos_client = CosmosDBManagementClient(cred, SUBSCRIPTION_ID)
def check_cosmos(account):
    rg = account.id.split("/")[4]
    try:
        props = cosmos_client.database_accounts.get(rg, account.name)
        # alcuni SDK esprimono come props.ip_range_filter
        ipf = getattr(props, "ip_range_filter", None) or getattr(props, "ipRangeFilter", None)
        return {"cosmos_ip_range_filter": ipf}
    except Exception:
        return {"cosmos_ip_range_filter": None}

def main():
    items = []
    now = datetime.now(timezone.utc).isoformat()

    for r in res_client.resources.list_by_resource_group(RESOURCE_GROUP):
        entry = {
            "resource_id": r.id,
            "type": r.type,
            "region": r.location,
            "collected_at": now
        }

        t = r.type.lower()
        try:
            if "microsoft.storage/storageaccounts" in t:
                entry.update(check_storage(r))
            elif "microsoft.keyvault/vaults" in t:
                entry.update(check_keyvault(r))
            elif "microsoft.network/networksecuritygroups" in t:
                entry.update(check_nsg(r))
            elif "microsoft.web/sites" in t:
                entry.update(check_webapp(r))
            elif "microsoft.network/publicipaddresses" in t:
                entry["public_ip"] = True  # semplice flag
        except Exception as e:
            entry["note"] = f"Errore nel parsing: {e}"

        items.append(entry)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"[OK] Salvato inventario compatto in {OUTPUT_PATH} ({len(items)} risorse)")

if __name__ == "__main__":
    main()
