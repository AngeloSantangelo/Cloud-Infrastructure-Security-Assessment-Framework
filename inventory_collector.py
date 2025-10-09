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
import props
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
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.network import NetworkManagementClient

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

def _pick(d, *keys, default=None):
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return default

def check_storage(account):
    rg = account.id.split("/")[4]
    props = st_client.storage_accounts.get_properties(rg, account.name)

    # usa as_dict() per evitare differenze tra versioni dell’SDK
    p = props.as_dict()

    https_only = _pick(
        p,
        "supports_https_traffic_only",   # nomi nuovi
        "enable_https_traffic_only",     # nomi vecchi
        default=None
    )
    return {
        "public_access": _pick(p, "allow_blob_public_access"),
        "https_only": None if https_only is None else bool(https_only),
        "minimum_tls_version": _pick(p, "minimum_tls_version"),
        "network_default_action": _pick(p.get("network_rule_set", {}) if p.get("network_rule_set") else {}, "default_action")
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

    def _any_internet(src_prefix, src_prefixes):
        ANY = {"*", "0.0.0.0/0", "Internet"}
        return (src_prefix in ANY) or bool(set((src_prefixes or [])) & ANY)

    def _has_port(rule, target):
        # supporta singolo valore o lista/range
        if rule.destination_port_range:
            return str(rule.destination_port_range).split('-')[0] == str(target)
        if rule.destination_port_ranges:
            return str(target) in {str(p).split('-')[0] for p in rule.destination_port_ranges}
        return False

    open_ssh = open_rdp = open_http = open_sql = False
    for rule in (n.security_rules or []):
        if rule.direction == "Inbound" and rule.access == "Allow" and rule.protocol in ("Tcp", "*"):
            if _any_internet(getattr(rule, "source_address_prefix", None),
                             getattr(rule, "source_address_prefixes", None)):
                open_ssh  |= _has_port(rule, 22)
                open_rdp  |= _has_port(rule, 3389)
                open_http |= _has_port(rule, 80)
                open_sql  |= _has_port(rule, 1433)

    return {
        "nsg_allows_ssh_any": open_ssh,
        "nsg_allows_rdp_any": open_rdp,
        "nsg_allows_http_any": open_http,
        "nsg_allows_sql_any": open_sql,
    }

def check_webapp(site):
    rg = site.id.split("/")[4]
    s = web_client.web_apps.get(rg, site.name)
    cfg = web_client.web_apps.get_configuration(rg, site.name)
    return {
        "https_only": safe_bool(s.https_only),
        "ftps_state": getattr(cfg, "ftps_state", None),   # es. AllAllowed / FtpsOnly / Disabled
        "always_on": safe_bool(getattr(cfg, "always_on", None)),
    }

sql_client = SqlManagementClient(cred, SUBSCRIPTION_ID)
def check_sql_server(srv):
    rg = srv.id.split("/")[4]
    try:
        # L'operazione corretta nell'SDK è firewall_rules
        rules = list(sql_client.firewall_rules.list_by_server(rg, srv.name))

        def _is_internet_rule(r):
            s = str(getattr(r, "start_ip_address", "")).strip()
            e = str(getattr(r, "end_ip_address", "")).strip()
            # Copre sia la regola "AllowAllWindowsAzureIps" (0.0.0.0)
            # sia range larghi fino a 255.255.255.255
            return (
                s in ("0.0.0.0", "0.0.0.0/0")
                or e in ("255.255.255.255", "0.0.0.0/0")
            )

        return {
            "sql_firewall_allows_internet": any(_is_internet_rule(r) for r in rules),
            "sql_fw_rules_count": len(rules),
            "sql_fw_sample": [getattr(r, "name", None) for r in rules[:3]],  # utile per debug
        }
    except Exception as ex:
        return {"sql_firewall_allows_internet": None, "sql_fw_error": f"{type(ex).__name__}: {ex}"}
    

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

def check_public_ip(resource):
    # arricchisci con l’indirizzo
    rg = resource.id.split("/")[4]
    name = resource.name
    pip = net_client.public_ip_addresses.get(rg, name)
    return {"public_ip": True, "ip_address": getattr(pip, "ip_address", None)}

def main():
    items = []
    now = datetime.now(timezone.utc).isoformat()

    for r in res_client.resources.list_by_resource_group(RESOURCE_GROUP):
        entry = {
            "resource_id": r.id,
            "name": r.name,
            "type": r.type,
            "region": r.location,
            "collected_at": now
        }

        t = r.type.lower()
        try:
            if t == "microsoft.storage/storageaccounts":
                entry.update(check_storage(r))
            elif t == "microsoft.keyvault/vaults":
                entry.update(check_keyvault(r))
            elif t == "microsoft.network/networksecuritygroups":
                entry.update(check_nsg(r))
            elif t == "microsoft.web/sites":
                entry.update(check_webapp(r))
            elif t == "microsoft.network/publicipaddresses":
                entry.update(check_public_ip(r))   # se hai aggiunto questa funzione
            elif t == "microsoft.sql/servers":
                entry.update(check_sql_server(r))  # ← QUI
            # opzionale: ignora esplicitamente i database SQL
            # elif t == "microsoft.sql/servers/databases":
            #     pass

        except Exception as e:
            entry["note"] = f"Errore nel parsing: {e}"

        items.append(entry)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"[OK] Salvato inventario compatto in {OUTPUT_PATH} ({len(items)} risorse)")

if __name__ == "__main__":
    main()



# #!/usr/bin/env python3
# """
# inventory_collector_improved.py
# Raccolta inventario risorse Azure - versione più robusta del tuo script.
# Uso:
#   python inventory_collector_improved.py --subscription SUB --resource-group RG --output rg-inventory.json
# """

# import json
# import time
# import argparse
# import logging
# import re
# from datetime import datetime, timezone
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from functools import wraps

# from azure.identity import DefaultAzureCredential
# from azure.mgmt.resource import ResourceManagementClient
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.keyvault import KeyVaultManagementClient
# from azure.mgmt.network import NetworkManagementClient
# from azure.mgmt.web import WebSiteManagementClient
# from azure.mgmt.sql import SqlManagementClient
# from azure.mgmt.containerregistry import ContainerRegistryManagementClient
# from azure.mgmt.cosmosdb import CosmosDBManagementClient

# # --------- CONFIG & LOGGER ----------
# DEFAULT_WORKERS = 8
# logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# logger = logging.getLogger("inventory")

# def retry(retries=3, delay=2, backoff=2, allowed_exceptions=(Exception,)):
#     def deco(func):
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             _delay = delay
#             for attempt in range(1, retries+1):
#                 try:
#                     return func(*args, **kwargs)
#                 except allowed_exceptions as e:
#                     if attempt == retries:
#                         logger.debug("Retry exhausted for %s: %s", func.__name__, e)
#                         raise
#                     logger.debug("Transient error on %s (attempt %d/%d): %s - retrying in %ds",
#                                  func.__name__, attempt, retries, e, _delay)
#                     time.sleep(_delay)
#                     _delay *= backoff
#         return wrapper
#     return deco

# # --------- Utils ----------
# def parse_rg_from_id(resource_id: str):
#     """
#     Estrae il resource group da un resourceId ARM in modo robusto.
#     Esempio: /subscriptions/.../resourceGroups/<RG>/providers/...
#     """
#     if not resource_id:
#         return None
#     m = re.search(r"/resourceGroups/([^/]+)", resource_id, flags=re.IGNORECASE)
#     return m.group(1) if m else None

# def safe_get(obj, *attrs, default=None):
#     """Recupera nested attribute in modo sicuro."""
#     cur = obj
#     for a in attrs:
#         if cur is None:
#             return default
#         cur = getattr(cur, a, None)
#     return cur if cur is not None else default

# # --------- Resource checks (con retry su chiamate API potenzialmente fragili) ----------
# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_storage(st_client, account):
#     rg = parse_rg_from_id(account.id) or ""
#     props = st_client.storage_accounts.get_properties(rg, account.name)
#     network_rule_set = getattr(props, "network_rule_set", None)
#     ip_rules = len(getattr(network_rule_set, "ip_rules", []) or [])
#     vnet_rules = len(getattr(network_rule_set, "virtual_network_rules", []) or [])
#     allow_blob_public = getattr(props, "allow_blob_public_access", None)
#     supports_https = getattr(props, "supports_https_traffic_only", None)
#     min_tls = getattr(props, "minimum_tls_version", None)
#     heur_public = None
#     if allow_blob_public is True:
#         heur_public = True
#     elif network_rule_set and getattr(network_rule_set, "default_action", None) == "Allow" and ip_rules == 0 and vnet_rules == 0:
#         heur_public = True
#     else:
#         heur_public = False if allow_blob_public is False else None

#     return {
#         "kind": getattr(props, "kind", None),
#         "public_access_heuristic": heur_public,
#         "allow_blob_public_access": allow_blob_public,
#         "https_only": supports_https,
#         "minimum_tls_version": min_tls,
#         "network_default_action": safe_get(props, "network_rule_set", "default_action", default=None),
#         "network_ip_rules_count": ip_rules,
#         "network_vnet_rules_count": vnet_rules
#     }

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_keyvault(kv_client, vault):
#     rg = parse_rg_from_id(vault.id) or ""
#     kv = kv_client.vaults.get(rg, vault.name)
#     props = kv.properties
#     pna = getattr(props, "public_network_access", None)
#     acls = getattr(props, "network_acls", None)
#     default_action = getattr(acls, "default_action", None) if acls else None
#     # fallback via CLI se ancora None
#     if default_action is None:
#         import subprocess, json as _json
#         try:
#             out = subprocess.check_output(["az","keyvault","show","-n",vault.name,"-g",rg,"-o","json"], text=True)
#             default_action = _json.loads(out).get("properties",{}).get("networkAcls",{}).get("defaultAction")
#         except Exception:
#             pass
#     return {
#         "public_network_access": pna,
#         "network_default_action": default_action,
#         "access_policies_count": len(getattr(props, "access_policies", []) or [])
#     }

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_nsg(net_client, nsg):
#     rg = parse_rg_from_id(nsg.id) or ""
#     n = net_client.network_security_groups.get(rg, nsg.name)
#     allows = {"ssh_any": False, "rdp_any": False, "http_any": False}
#     for rule in (n.security_rules or []):
#         direction = getattr(rule, "direction", "").lower()
#         access = getattr(rule, "access", "")
#         src_prefix = getattr(rule, "source_address_prefix", None) or getattr(rule, "source_address_prefixes", None)
#         dst_port = getattr(rule, "destination_port_range", None) or getattr(rule, "destination_port_ranges", None)
#         if direction == "inbound" and access == "Allow":
#             # normalizza src_prefix in stringa
#             sp = None
#             if isinstance(src_prefix, (list, tuple)):
#                 sp = ",".join(src_prefix)
#             else:
#                 sp = str(src_prefix)
#             if sp in ("*", "0.0.0.0/0", "Internet"):
#                 dr = str(dst_port)
#                 if "22" in dr:
#                     allows["ssh_any"] = True
#                 if "3389" in dr:
#                     allows["rdp_any"] = True
#                 if "80" in dr or "443" in dr:
#                     allows["http_any"] = True
#     return allows

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_webapp(web_client, site):
#     rg = parse_rg_from_id(site.id) or ""
#     # get() + get_configuration(): alcune proprieta' sono in config
#     s = web_client.web_apps.get(rg, site.name)
#     cfg = web_client.web_apps.get_configuration(rg, site.name)
#     https_only = getattr(s, "https_only", None)
#     ftps_state = getattr(cfg, "ftps_state", None) or getattr(s, "ftps_state", None)
#     min_tls = getattr(cfg, "min_tls_version", None)
#     return {"https_only": https_only, "ftps_state": ftps_state, "min_tls_version": min_tls}

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_sql_server(sql_client, srv):
#     rg = parse_rg_from_id(srv.id) or ""
#     try:
#         rules = list(sql_client.server_firewall_rules.list_by_server(rg, srv.name))
#         return {
#             "sql_firewall_allows_internet": any(
#                 str(getattr(r, "start_ip_address","")).strip() in ("0.0.0.0","0.0.0.0/0") or
#                 str(getattr(r, "end_ip_address","")).strip() in ("255.255.255.255","0.0.0.0")
#                 for r in rules
#             ),
#             "firewall_rules_count": len(rules)
#         }
#     except Exception:
#         # Fallback via CLI (richiede 'az' e permessi lettura)
#         import subprocess, json as _json
#         try:
#             out = subprocess.check_output(
#                 ["az","sql","server","firewall-rule","list","-g",rg,"-s",srv.name,"-o","json"], text=True
#             )
#             rules = _json.loads(out)
#             allows = any(
#                 (r.get("startIpAddress") in ("0.0.0.0","0.0.0.0/0") or
#                  r.get("endIpAddress")   in ("255.255.255.255","0.0.0.0"))
#                 for r in rules
#             )
#             return {"sql_firewall_allows_internet": allows, "firewall_rules_count": len(rules)}
#         except Exception:
#             return {"sql_firewall_allows_internet": None}

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_acr(acr_client, reg):
#     rg = parse_rg_from_id(reg.id) or ""
#     props = acr_client.registries.get(rg, reg.name)
#     admin = getattr(props, "admin_user_enabled", None)
#     return {"acr_admin_user_enabled": None if admin is None else bool(admin)}

# @retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
# def check_cosmos(cosmos_client, account):
#     rg = parse_rg_from_id(account.id) or ""
#     props = cosmos_client.database_accounts.get(rg, account.name)
#     ipf = getattr(props, "ip_range_filter", None) or getattr(props, "ipRangeFilter", None)
#     return {"cosmos_ip_range_filter": ipf}

# # --------- Main ----------
# def collect_inventory(subscription_id, resource_group, output_path, workers=DEFAULT_WORKERS):
#     cred = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
#     res_client = ResourceManagementClient(cred, subscription_id)
#     clients = {
#     # storage: evita 2025-01-01 non supportato
#     "storage": StorageManagementClient(cred, subscription_id, api_version="2024-01-01"),
#     # key vault: evita 2025-05-01 non supportato
#     "keyvault": KeyVaultManagementClient(cred, subscription_id, api_version="2024-11-01"),
#     # network (per NSG): 2024-07-01 va bene
#     "network": NetworkManagementClient(cred, subscription_id, api_version="2024-07-01"),
#     # web: alcune installazioni falliscono con 2024-11-01, usa una stabile
#     "web": WebSiteManagementClient(cred, subscription_id, api_version="2023-12-01"),
#     # sql: mantieni default (oppure pin se serve)
#     "sql": SqlManagementClient(cred, subscription_id),
#     "acr": ContainerRegistryManagementClient(cred, subscription_id),
#     "cosmos": CosmosDBManagementClient(cred, subscription_id),
# }

#     now = datetime.now(timezone.utc).isoformat()
#     resources = list(res_client.resources.list_by_resource_group(resource_group))
#     logger.info("Trovate %d risorse in %s", len(resources), resource_group)

#     items = []
#     # thread pool per chiamate I/O-bound
#     with ThreadPoolExecutor(max_workers=workers) as ex:
#         futures = {}
#         for r in resources:
#             t = r.type.lower()
#             # dispatch asincrono alle funzioni check_*
#             if "microsoft.storage/storageaccounts" in t:
#                 futures[ex.submit(check_storage, clients["storage"], r)] = ("storage", r)
#             elif "microsoft.keyvault/vaults" in t:
#                 futures[ex.submit(check_keyvault, clients["keyvault"], r)] = ("keyvault", r)
#             elif "microsoft.network/networksecuritygroups" in t:
#                 futures[ex.submit(check_nsg, clients["network"], r)] = ("nsg", r)
#             elif "microsoft.web/sites" in t:
#                 futures[ex.submit(check_webapp, clients["web"], r)] = ("web", r)
#             elif "microsoft.network/publicipaddresses" in t:
#                 # semplice flag senza chiamata
#                 items.append({"resource_id": r.id, "type": r.type, "region": r.location,
#                               "collected_at": now, "public_ip": True})
#             elif "microsoft.sql/servers" in t:
#                 futures[ex.submit(check_sql_server, clients["sql"], r)] = ("sql", r)
#             elif "microsoft.containerregistry/registries" in t:
#                 futures[ex.submit(check_acr, clients["acr"], r)] = ("acr", r)
#             elif "microsoft.documentdb/databaseaccounts" in t or "microsoft.cosmosdb/databaseaccounts" in t:
#                 futures[ex.submit(check_cosmos, clients["cosmos"], r)] = ("cosmos", r)
#             else:
#                 # entry minimal
#                 items.append({"resource_id": r.id, "type": r.type, "region": r.location,
#                               "collected_at": now})

#         # raccogli risultati
#         for fut in as_completed(futures):
#             kind, resource = futures[fut]
#             try:
#                 result = fut.result()
#             except Exception as e:
#                 logger.warning("Errore durante il check %s per %s: %s", kind, resource.name, e)
#                 entry = {"resource_id": resource.id, "type": resource.type, "region": resource.location,
#                          "collected_at": now, "note": f"error: {str(e)}"}
#             else:
#                 entry = {"resource_id": resource.id, "type": resource.type, "region": resource.location,
#                          "collected_at": now}
#                 entry.update(result)
#             items.append(entry)

#     # salva output
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump({"collected_at": now, "subscription_id": subscription_id, "resource_group": resource_group, "items": items}, f, ensure_ascii=False, indent=2)

#     logger.info("Salvato inventario in %s (risorse processate: %d)", output_path, len(items))
#     return output_path

# def main():
#     p = argparse.ArgumentParser(description="Azure RG inventory collector (improved)")
#     p.add_argument("--subscription", "-s", required=True)
#     p.add_argument("--resource-group", "-g", required=True)
#     p.add_argument("--output", "-o", default="rg-inventory.json")
#     p.add_argument("--workers", "-w", type=int, default=DEFAULT_WORKERS)
#     args = p.parse_args()
#     collect_inventory(args.subscription, args.resource_group, args.output, workers=args.workers)

# if __name__ == "__main__":
#     main()
