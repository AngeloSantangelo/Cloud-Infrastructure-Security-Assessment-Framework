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




# import json
# from datetime import datetime, timezone
# from azure.identity import DefaultAzureCredential
# from azure.mgmt.resource import ResourceManagementClient
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.keyvault import KeyVaultManagementClient
# from azure.mgmt.network import NetworkManagementClient
# from azure.mgmt.web import WebSiteManagementClient
# from azure.mgmt.sql import SqlManagementClient
# from azure.mgmt.containerregistry import ContainerRegistryManagementClient
# from azure.mgmt.cosmosdb import CosmosDBManagementClient

# # ====== CONFIG ======
# SUBSCRIPTION_ID = "507c29d9-8bd6-4976-8e7b-5b3e56f25bf8"   # <-- metti la tua subscription
# RESOURCE_GROUP  = "rg-miscfg-lab"                           # <-- il tuo RG
# OUTPUT_PATH     = "rg-inventory.json"                       # <-- file output
# # ====================

# cred = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
# res_client  = ResourceManagementClient(cred, SUBSCRIPTION_ID)
# st_client   = StorageManagementClient(cred, SUBSCRIPTION_ID)
# kv_client   = KeyVaultManagementClient(cred, SUBSCRIPTION_ID)
# net_client  = NetworkManagementClient(cred, SUBSCRIPTION_ID)
# web_client  = WebSiteManagementClient(cred, SUBSCRIPTION_ID)

# def safe_bool(x): return None if x is None else bool(x)

# def check_storage(account):
#     rg = account.id.split("/")[4]
#     props = st_client.storage_accounts.get_properties(rg, account.name)
#     return {
#         "public_access": safe_bool(getattr(props, "allow_blob_public_access", None)),
#         "https_only": safe_bool(getattr(props, "supports_https_traffic_only", None)),
#         "minimum_tls_version": getattr(props, "minimum_tls_version", None),
#         "network_default_action": getattr(
#             getattr(props, "network_rule_set", None), "default_action", None
#         )
#     }

# def check_keyvault(vault):
#     rg = vault.id.split("/")[4]
#     kv = kv_client.vaults.get(rg, vault.name)
#     props = kv.properties
#     return {
#         "public_network_access": getattr(props, "public_network_access", None),
#         "network_default_action": getattr(
#             getattr(props, "network_acls", None), "default_action", None
#         )
#     }

# def check_nsg(nsg):
#     rg = nsg.id.split("/")[4]
#     n = net_client.network_security_groups.get(rg, nsg.name)
#     ssh = False
#     rdp = False
#     for rule in (n.security_rules or []):
#         if rule.direction == "Inbound" and rule.access == "Allow":
#             if rule.source_address_prefix in ["*", "0.0.0.0/0", "Internet"]:
#                 if str(rule.destination_port_range) in ["22", "22-22"]:
#                     ssh = True
#                 if str(rule.destination_port_range) in ["3389", "3389-3389"]:
#                     rdp = True
#     return {"nsg_allows_ssh_any": ssh, "nsg_allows_rdp_any": rdp}

# def check_webapp(site):
#     rg = site.id.split("/")[4]
#     s = web_client.web_apps.get(rg, site.name)
#     return {"https_only": safe_bool(s.https_only)}

# sql_client = SqlManagementClient(cred, SUBSCRIPTION_ID)
# def check_sql_server(srv):
#     rg = srv.id.split("/")[4]
#     try:
#         rules = sql_client.server_firewall_rules.list_by_server(rg, srv.name)
#         for r in rules:
#             s = str(getattr(r, "start_ip_address", "")).strip()
#             e = str(getattr(r, "end_ip_address", "")).strip()
#             if s in ("0.0.0.0", "0.0.0.0/0") or e in ("0.0.0.0", "0.0.0.0/0"):
#                 return {"sql_firewall_allows_internet": True}
#         return {"sql_firewall_allows_internet": False}
#     except Exception:
#         return {"sql_firewall_allows_internet": None}
    

# acr_client = ContainerRegistryManagementClient(cred, SUBSCRIPTION_ID)
# def check_acr(reg):
#     rg = reg.id.split("/")[4]
#     try:
#         props = acr_client.registries.get(rg, reg.name)
#         admin = getattr(props, "admin_user_enabled", None)
#         return {"acr_admin_user_enabled": None if admin is None else bool(admin)}
#     except Exception:
#         return {"acr_admin_user_enabled": None}
    

# cosmos_client = CosmosDBManagementClient(cred, SUBSCRIPTION_ID)
# def check_cosmos(account):
#     rg = account.id.split("/")[4]
#     try:
#         props = cosmos_client.database_accounts.get(rg, account.name)
#         # alcuni SDK esprimono come props.ip_range_filter
#         ipf = getattr(props, "ip_range_filter", None) or getattr(props, "ipRangeFilter", None)
#         return {"cosmos_ip_range_filter": ipf}
#     except Exception:
#         return {"cosmos_ip_range_filter": None}

# def main():
#     items = []
#     now = datetime.now(timezone.utc).isoformat()

#     for r in res_client.resources.list_by_resource_group(RESOURCE_GROUP):
#         entry = {
#             "resource_id": r.id,
#             "type": r.type,
#             "region": r.location,
#             "collected_at": now
#         }

#         t = r.type.lower()
#         try:
#             if "microsoft.storage/storageaccounts" in t:
#                 entry.update(check_storage(r))
#             elif "microsoft.keyvault/vaults" in t:
#                 entry.update(check_keyvault(r))
#             elif "microsoft.network/networksecuritygroups" in t:
#                 entry.update(check_nsg(r))
#             elif "microsoft.web/sites" in t:
#                 entry.update(check_webapp(r))
#             elif "microsoft.network/publicipaddresses" in t:
#                 entry["public_ip"] = True  # semplice flag
#         except Exception as e:
#             entry["note"] = f"Errore nel parsing: {e}"

#         items.append(entry)

#     with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
#         json.dump(items, f, ensure_ascii=False, indent=2)

#     print(f"[OK] Salvato inventario compatto in {OUTPUT_PATH} ({len(items)} risorse)")

# if __name__ == "__main__":
#     main()



#!/usr/bin/env python3
"""
inventory_collector_improved.py
Raccolta inventario risorse Azure - versione più robusta del tuo script.
Uso:
  python inventory_collector_improved.py --subscription SUB --resource-group RG --output rg-inventory.json
"""

import json
import time
import argparse
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient

# --------- CONFIG & LOGGER ----------
DEFAULT_WORKERS = 8
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("inventory")

def retry(retries=3, delay=2, backoff=2, allowed_exceptions=(Exception,)):
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(1, retries+1):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    if attempt == retries:
                        logger.debug("Retry exhausted for %s: %s", func.__name__, e)
                        raise
                    logger.debug("Transient error on %s (attempt %d/%d): %s - retrying in %ds",
                                 func.__name__, attempt, retries, e, _delay)
                    time.sleep(_delay)
                    _delay *= backoff
        return wrapper
    return deco

# --------- Utils ----------
def parse_rg_from_id(resource_id: str):
    """Estrai resource group da un resourceId in modo robusto."""
    marker = "/resourceGroups/"
    try:
        start = resource_id.lower().index(marker) + len(marker)
        rest = resource_id[start:]
        return rest.split("/", 1)[0]
    except ValueError:
        return None

def safe_get(obj, *attrs, default=None):
    """Recupera nested attribute in modo sicuro."""
    cur = obj
    for a in attrs:
        if cur is None:
            return default
        cur = getattr(cur, a, None)
    return cur if cur is not None else default

# --------- Resource checks (con retry su chiamate API potenzialmente fragili) ----------
@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_storage(st_client, account):
    rg = parse_rg_from_id(account.id) or ""
    props = st_client.storage_accounts.get_properties(rg, account.name)
    network_rule_set = getattr(props, "network_rule_set", None)
    ip_rules = len(getattr(network_rule_set, "ip_rules", []) or [])
    vnet_rules = len(getattr(network_rule_set, "virtual_network_rules", []) or [])
    allow_blob_public = getattr(props, "allow_blob_public_access", None)
    supports_https = getattr(props, "supports_https_traffic_only", None)
    min_tls = getattr(props, "minimum_tls_version", None)
    heur_public = None
    if allow_blob_public is True:
        heur_public = True
    elif network_rule_set and getattr(network_rule_set, "default_action", None) == "Allow" and ip_rules == 0 and vnet_rules == 0:
        heur_public = True
    else:
        heur_public = False if allow_blob_public is False else None

    return {
        "kind": getattr(props, "kind", None),
        "public_access_heuristic": heur_public,
        "allow_blob_public_access": allow_blob_public,
        "https_only": supports_https,
        "minimum_tls_version": min_tls,
        "network_default_action": safe_get(props, "network_rule_set", "default_action", default=None),
        "network_ip_rules_count": ip_rules,
        "network_vnet_rules_count": vnet_rules
    }

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_keyvault(kv_client, vault):
    rg = parse_rg_from_id(vault.id) or ""
    kv = kv_client.vaults.get(rg, vault.name)
    props = kv.properties
    pna = getattr(props, "public_network_access", None)
    acls = getattr(props, "network_acls", None)
    default_action = getattr(acls, "default_action", None) if acls else None
    return {
        "public_network_access": pna,
        "network_default_action": default_action,
        "access_policies_count": len(getattr(props, "access_policies", []) or [])
    }

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_nsg(net_client, nsg):
    rg = parse_rg_from_id(nsg.id) or ""
    n = net_client.network_security_groups.get(rg, nsg.name)
    allows = {"ssh_any": False, "rdp_any": False, "http_any": False}
    for rule in (n.security_rules or []):
        direction = getattr(rule, "direction", "").lower()
        access = getattr(rule, "access", "")
        src_prefix = getattr(rule, "source_address_prefix", None) or getattr(rule, "source_address_prefixes", None)
        dst_port = getattr(rule, "destination_port_range", None) or getattr(rule, "destination_port_ranges", None)
        if direction == "inbound" and access == "Allow":
            # normalizza src_prefix in stringa
            sp = None
            if isinstance(src_prefix, (list, tuple)):
                sp = ",".join(src_prefix)
            else:
                sp = str(src_prefix)
            if sp in ("*", "0.0.0.0/0", "Internet"):
                dr = str(dst_port)
                if "22" in dr:
                    allows["ssh_any"] = True
                if "3389" in dr:
                    allows["rdp_any"] = True
                if "80" in dr or "443" in dr:
                    allows["http_any"] = True
    return allows

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_webapp(web_client, site):
    rg = parse_rg_from_id(site.id) or ""
    s = web_client.web_apps.get(rg, site.name)
    # https_only boolean: alcuni SDK espongono s.https_only (bool) o s.site_config
    https_only = getattr(s, "https_only", None)
    try:
        if https_only is None:
            cfg = getattr(s, "site_config", None)
            https_only = safe_get(cfg, "min_tls_version", default=None) is not None or getattr(s, "https_only", None)
    except Exception:
        https_only = None
    ftps_state = safe_get(s, "ftps_state", None)
    return {"https_only": https_only, "ftps_state": ftps_state}

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_sql_server(sql_client, srv):
    rg = parse_rg_from_id(srv.id) or ""
    try:
        rules = list(sql_client.server_firewall_rules.list_by_server(rg, srv.name))
        # heuristica: se una regola ha start 0.0.0.0 e end 255.255.255.255 o simili -> internet open
        for r in rules:
            s = str(getattr(r, "start_ip_address", "")).strip()
            e = str(getattr(r, "end_ip_address", "")).strip()
            if (s in ("0.0.0.0", "0.0.0.0/0") or e in ("255.255.255.255", "0.0.0.0")):
                return {"sql_firewall_allows_internet": True, "firewall_rules_count": len(rules)}
        return {"sql_firewall_allows_internet": False, "firewall_rules_count": len(rules)}
    except Exception:
        return {"sql_firewall_allows_internet": None}

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_acr(acr_client, reg):
    rg = parse_rg_from_id(reg.id) or ""
    props = acr_client.registries.get(rg, reg.name)
    admin = getattr(props, "admin_user_enabled", None)
    return {"acr_admin_user_enabled": None if admin is None else bool(admin)}

@retry(retries=3, delay=1, backoff=2, allowed_exceptions=(Exception,))
def check_cosmos(cosmos_client, account):
    rg = parse_rg_from_id(account.id) or ""
    props = cosmos_client.database_accounts.get(rg, account.name)
    ipf = getattr(props, "ip_range_filter", None) or getattr(props, "ipRangeFilter", None)
    return {"cosmos_ip_range_filter": ipf}

# --------- Main ----------
def collect_inventory(subscription_id, resource_group, output_path, workers=DEFAULT_WORKERS):
    cred = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
    res_client = ResourceManagementClient(cred, subscription_id)
    clients = {
        "storage": StorageManagementClient(cred, subscription_id),
        "keyvault": KeyVaultManagementClient(cred, subscription_id),
        "network": NetworkManagementClient(cred, subscription_id),
        "web": WebSiteManagementClient(cred, subscription_id),
        "sql": SqlManagementClient(cred, subscription_id),
        "acr": ContainerRegistryManagementClient(cred, subscription_id),
        "cosmos": CosmosDBManagementClient(cred, subscription_id)
    }

    now = datetime.now(timezone.utc).isoformat()
    resources = list(res_client.resources.list_by_resource_group(resource_group))
    logger.info("Trovate %d risorse in %s", len(resources), resource_group)

    items = []
    # thread pool per chiamate I/O-bound
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for r in resources:
            t = r.type.lower()
            # dispatch asincrono alle funzioni check_*
            if "microsoft.storage/storageaccounts" in t:
                futures[ex.submit(check_storage, clients["storage"], r)] = ("storage", r)
            elif "microsoft.keyvault/vaults" in t:
                futures[ex.submit(check_keyvault, clients["keyvault"], r)] = ("keyvault", r)
            elif "microsoft.network/networksecuritygroups" in t:
                futures[ex.submit(check_nsg, clients["network"], r)] = ("nsg", r)
            elif "microsoft.web/sites" in t:
                futures[ex.submit(check_webapp, clients["web"], r)] = ("web", r)
            elif "microsoft.network/publicipaddresses" in t:
                # semplice flag senza chiamata
                items.append({"resource_id": r.id, "type": r.type, "region": r.location,
                              "collected_at": now, "public_ip": True})
            elif "microsoft.sql/servers" in t:
                futures[ex.submit(check_sql_server, clients["sql"], r)] = ("sql", r)
            elif "microsoft.containerregistry/registries" in t:
                futures[ex.submit(check_acr, clients["acr"], r)] = ("acr", r)
            elif "microsoft.documentdb/databaseaccounts" in t or "microsoft.cosmosdb/databaseaccounts" in t:
                futures[ex.submit(check_cosmos, clients["cosmos"], r)] = ("cosmos", r)
            else:
                # entry minimal
                items.append({"resource_id": r.id, "type": r.type, "region": r.location,
                              "collected_at": now})

        # raccogli risultati
        for fut in as_completed(futures):
            kind, resource = futures[fut]
            try:
                result = fut.result()
            except Exception as e:
                logger.warning("Errore durante il check %s per %s: %s", kind, resource.name, e)
                entry = {"resource_id": resource.id, "type": resource.type, "region": resource.location,
                         "collected_at": now, "note": f"error: {str(e)}"}
            else:
                entry = {"resource_id": resource.id, "type": resource.type, "region": resource.location,
                         "collected_at": now}
                entry.update(result)
            items.append(entry)

    # salva output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"collected_at": now, "subscription_id": subscription_id, "resource_group": resource_group, "items": items}, f, ensure_ascii=False, indent=2)

    logger.info("Salvato inventario in %s (risorse processate: %d)", output_path, len(items))
    return output_path

def main():
    p = argparse.ArgumentParser(description="Azure RG inventory collector (improved)")
    p.add_argument("--subscription", "-s", required=True)
    p.add_argument("--resource-group", "-g", required=True)
    p.add_argument("--output", "-o", default="rg-inventory.json")
    p.add_argument("--workers", "-w", type=int, default=DEFAULT_WORKERS)
    args = p.parse_args()
    collect_inventory(args.subscription, args.resource_group, args.output, workers=args.workers)

if __name__ == "__main__":
    main()
