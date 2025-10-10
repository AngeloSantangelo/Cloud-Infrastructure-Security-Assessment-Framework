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
# from azure.mgmt.web import WebSiteManagementClient
# from azure.mgmt.sql import SqlManagementClient
# from azure.mgmt.network import NetworkManagementClient

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

# def _pick(d, *keys, default=None):
#     for k in keys:
#         if d.get(k) is not None:
#             return d[k]
#     return default

# def check_storage(account):
#     rg = account.id.split("/")[4]
#     props = st_client.storage_accounts.get_properties(rg, account.name)

#     # usa as_dict() per evitare differenze tra versioni dell’SDK
#     p = props.as_dict()

#     https_only = _pick(
#         p,
#         "supports_https_traffic_only",   # nomi nuovi
#         "enable_https_traffic_only",     # nomi vecchi
#         default=None
#     )
#     return {
#         "public_access": _pick(p, "allow_blob_public_access"),
#         "https_only": None if https_only is None else bool(https_only),
#         "minimum_tls_version": _pick(p, "minimum_tls_version"),
#         "network_default_action": _pick(p.get("network_rule_set", {}) if p.get("network_rule_set") else {}, "default_action")
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

#     def _any_internet(src_prefix, src_prefixes):
#         ANY = {"*", "0.0.0.0/0", "Internet"}
#         return (src_prefix in ANY) or bool(set((src_prefixes or [])) & ANY)

#     def _has_port(rule, target):
#         # supporta singolo valore o lista/range
#         if rule.destination_port_range:
#             return str(rule.destination_port_range).split('-')[0] == str(target)
#         if rule.destination_port_ranges:
#             return str(target) in {str(p).split('-')[0] for p in rule.destination_port_ranges}
#         return False

#     open_ssh = open_rdp = open_http = open_sql = False
#     for rule in (n.security_rules or []):
#         if rule.direction == "Inbound" and rule.access == "Allow" and rule.protocol in ("Tcp", "*"):
#             if _any_internet(getattr(rule, "source_address_prefix", None),
#                              getattr(rule, "source_address_prefixes", None)):
#                 open_ssh  |= _has_port(rule, 22)
#                 open_rdp  |= _has_port(rule, 3389)
#                 open_http |= _has_port(rule, 80)
#                 open_sql  |= _has_port(rule, 1433)

#     return {
#         "nsg_allows_ssh_any": open_ssh,
#         "nsg_allows_rdp_any": open_rdp,
#         "nsg_allows_http_any": open_http,
#         "nsg_allows_sql_any": open_sql,
#     }

# def check_webapp(site):
#     rg = site.id.split("/")[4]
#     s = web_client.web_apps.get(rg, site.name)
#     cfg = web_client.web_apps.get_configuration(rg, site.name)
#     return {
#         "https_only": safe_bool(s.https_only),
#         "ftps_state": getattr(cfg, "ftps_state", None),   # es. AllAllowed / FtpsOnly / Disabled
#         "always_on": safe_bool(getattr(cfg, "always_on", None)),
#     }

# sql_client = SqlManagementClient(cred, SUBSCRIPTION_ID)
# def check_sql_server(srv):
#     rg = srv.id.split("/")[4]
#     try:
#         # L'operazione corretta nell'SDK è firewall_rules
#         rules = list(sql_client.firewall_rules.list_by_server(rg, srv.name))

#         def _is_internet_rule(r):
#             s = str(getattr(r, "start_ip_address", "")).strip()
#             e = str(getattr(r, "end_ip_address", "")).strip()
#             # Copre sia la regola "AllowAllWindowsAzureIps" (0.0.0.0)
#             # sia range larghi fino a 255.255.255.255
#             return (
#                 s in ("0.0.0.0", "0.0.0.0/0")
#                 or e in ("255.255.255.255", "0.0.0.0/0")
#             )

#         return {
#             "sql_firewall_allows_internet": any(_is_internet_rule(r) for r in rules),
#             "sql_fw_rules_count": len(rules),
#             "sql_fw_sample": [getattr(r, "name", None) for r in rules[:3]],  # utile per debug
#         }
#     except Exception as ex:
#         return {"sql_firewall_allows_internet": None, "sql_fw_error": f"{type(ex).__name__}: {ex}"}
    

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

# def check_public_ip(resource):
#     # arricchisci con l’indirizzo
#     rg = resource.id.split("/")[4]
#     name = resource.name
#     pip = net_client.public_ip_addresses.get(rg, name)
#     return {"public_ip": True, "ip_address": getattr(pip, "ip_address", None)}

# def main():
#     items = []
#     now = datetime.now(timezone.utc).isoformat()

#     for r in res_client.resources.list_by_resource_group(RESOURCE_GROUP):
#         entry = {
#             "resource_id": r.id,
#             "name": r.name,
#             "type": r.type,
#             "region": r.location,
#             "collected_at": now
#         }

#         t = r.type.lower()
#         try:
#             if t == "microsoft.storage/storageaccounts":
#                 entry.update(check_storage(r))
#             elif t == "microsoft.keyvault/vaults":
#                 entry.update(check_keyvault(r))
#             elif t == "microsoft.network/networksecuritygroups":
#                 entry.update(check_nsg(r))
#             elif t == "microsoft.web/sites":
#                 entry.update(check_webapp(r))
#             elif t == "microsoft.network/publicipaddresses":
#                 entry.update(check_public_ip(r))   # se hai aggiunto questa funzione
#             elif t == "microsoft.sql/servers":
#                 entry.update(check_sql_server(r))  # ← QUI
#             # opzionale: ignora esplicitamente i database SQL
#             # elif t == "microsoft.sql/servers/databases":
#             #     pass

#         except Exception as e:
#             entry["note"] = f"Errore nel parsing: {e}"

#         items.append(entry)

#     with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
#         json.dump(items, f, ensure_ascii=False, indent=2)

#     print(f"[OK] Salvato inventario compatto in {OUTPUT_PATH} ({len(items)} risorse)")

# if __name__ == "__main__":
#     main()


from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import HttpResponseError

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOG = logging.getLogger("inventory")
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

# Evita rumorosità SDK se vuoi
for noisy in ["azure", "msrest", "uamqp"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Disattiva la telemetria Azure CLI se presente
os.environ.setdefault("AZURE_CORE_TELEMETRY_ENABLED", "false")

# -----------------------------------------------------------------------------
# Utility: retry semplice su errori transitori
# -----------------------------------------------------------------------------
from time import sleep


def retry(fn, *, tries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def wrapper(*args, **kwargs):
        t = tries
        d = delay
        last = None
        while t > 0:
            try:
                return fn(*args, **kwargs)
            except HttpResponseError as e:
                last = e
                if t == 1:
                    raise
                LOG.debug("Transient error: %s — retrying in %.1fs", e, d)
                sleep(d)
                d *= backoff
                t -= 1
    return wrapper


# -----------------------------------------------------------------------------
# API version resolver (cache + prefer stable)
# -----------------------------------------------------------------------------
@dataclass
class ApiVersionCache:
    cache: Dict[Tuple[str, str], str]

    def get(self, key: Tuple[str, str]) -> Optional[str]:
        return self.cache.get(key)

    def set(self, key: Tuple[str, str], value: str) -> None:
        self.cache[key] = value


API_CACHE = ApiVersionCache(cache={})


def _split_provider_type(resource_type: str) -> Tuple[str, str]:
    """Split 'Microsoft.X/type/subtype' -> (provider, 'type/subtype')."""
    if "/" not in resource_type:
        raise ValueError(f"Invalid resource type: {resource_type}")
    parts = resource_type.split("/")
    provider = parts[0]
    path = "/".join(parts[1:])
    return provider, path


@retry
def resolve_api_version(res_client: ResourceManagementClient, full_type: str) -> str:
    """Resolve the latest (prefer stable) apiVersion for a given resource type.

    full_type es: 'Microsoft.Storage/storageAccounts' o 'Microsoft.Web/sites/config'.
    """
    key = (res_client._config.subscription_id, full_type.lower())  # type: ignore[attr-defined]
    cached = API_CACHE.get(key)
    if cached:
        return cached

    provider, path = _split_provider_type(full_type)
    prov = res_client.providers.get(provider)  # type: ignore[arg-type]

    # La lista provider.resource_types contiene voci per top-level e anche per nested types.
    best: Optional[str] = None
    best_preview: Optional[str] = None

    def pick(candidates: List[str]) -> Tuple[Optional[str], Optional[str]]:
        stable = [v for v in candidates if "preview" not in v.lower()]
        previews = [v for v in candidates if "preview" in v.lower()]
        # prendi la più recente assumendo che la lista sia non ordinata; ordina semanticamente per anno/mese se presente
        def _sort_key(v: str) -> Tuple[int, str]:
            # tenta di estrarre yyyy-mm-dd
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", v)
            return (int(m.group(1).replace("-", "")) if m else 0, v)
        stable.sort(key=_sort_key, reverse=True)
        previews.sort(key=_sort_key, reverse=True)
        return (stable[0] if stable else None, previews[0] if previews else None)

    # match esatto sul path, poi fallback progressivo rimuovendo gli ultimi segmenti
    segments = path.split("/")
    for i in range(len(segments), 0, -1):
        needle = "/".join(segments[:i]).lower()
        for rt in prov.resource_types:  # type: ignore[attr-defined]
            if rt.resource_type.lower() == needle:
                s, p = pick(list(rt.api_versions or []))  # type: ignore[arg-type]
                best = best or s
                best_preview = best_preview or p
                if best:
                    API_CACHE.set(key, best)
                    return best
                # tieni a mente il migliore preview ma continua a cercare stable
        # continua a risalire
    # se non abbiamo trovato stable, usa preview migliore
    if best_preview:
        API_CACHE.set(key, best_preview)
        return best_preview

    # fallback durissimo: tenta l'ultima apiVersion del provider in generale
    all_versions: List[str] = []
    for rt in prov.resource_types:  # type: ignore[attr-defined]
        all_versions.extend(list(rt.api_versions or []))
    if all_versions:
        all_versions.sort(reverse=True)
        API_CACHE.set(key, all_versions[0])
        return all_versions[0]

    raise RuntimeError(f"Unable to resolve apiVersion for {full_type}")


# -----------------------------------------------------------------------------
# Baseline collector
# -----------------------------------------------------------------------------

def baseline_entry(res: Any) -> Dict[str, Any]:
    """Campi comuni sempre presenti."""
    return {
        "id": res.id,
        "name": getattr(res, "name", None),
        "type": getattr(res, "type", None),
        "location": getattr(res, "location", None),
        "tags": getattr(res, "tags", None) or {},
    }


@retry
def fetch_raw_by_id(res_client: ResourceManagementClient, resource_id: str, resource_type: str) -> Dict[str, Any]:
    api_version = resolve_api_version(res_client, resource_type)
    generic = res_client.resources.get_by_id(resource_id, api_version)
    as_dict = generic.as_dict()
    # alcune risorse non espongono 'properties'; salviamo tutto l'oggetto
    return {
        "api_version": api_version,
        "object": as_dict,
        "properties": as_dict.get("properties", {}),
    }


# -----------------------------------------------------------------------------
# Enricher plugins (aggiungi/estendi a piacere)
# -----------------------------------------------------------------------------
Enricher = Any  # Callable[[ResourceManagementClient, Dict[str,Any]], Dict[str,Any]]


def enricher_storage(res_client: ResourceManagementClient, base: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    props = raw.get("properties", {}) or {}
    net = props.get("networkAcls", {}) or props.get("networkRuleSet", {}) or {}
    https_only = props.get("supportsHttpsTrafficOnly")
    min_tls = props.get("minimumTlsVersion")
    public_network = (net.get("defaultAction") == "Allow") if net else None
    return {
        "enrich": {
            "storage": {
                "https_only": https_only,
                "minimum_tls": min_tls,
                "public_network_access": public_network,
            }
        }
    }


def enricher_webapp(res_client: ResourceManagementClient, base: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    props = raw.get("properties", {}) or {}
    https_only = props.get("httpsOnly")
    ftps_state = props.get("ftpsState")
    return {
        "enrich": {
            "webapp": {
                "https_only": https_only,
                "ftps_state": ftps_state,
            }
        }
    }


def enricher_nsg(res_client: ResourceManagementClient, base: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    props = raw.get("properties", {}) or {}
    rules = props.get("securityRules", []) or []
    risky_ports = {"22", "3389", "1433", "3306", "5432", "9200"}
    open_inbound = []
    for r in rules:
        rp = r.get("properties", {})
        if (rp.get("direction") == "Inbound" and rp.get("access") == "Allow" and
                (rp.get("sourceAddressPrefix") in ("*", "0.0.0.0/0", "Internet"))):
            # range porte
            sp = str(rp.get("destinationPortRange") or "")
            if sp and any(p in sp for p in risky_ports):
                open_inbound.append({"rule": r.get("name"), "port": sp, "protocol": rp.get("protocol")})
    return {"enrich": {"nsg": {"open_internet_rules": open_inbound}}}


# Registry mapping (lowercase)
ENRICHERS: Dict[str, Enricher] = {
    "microsoft.storage/storageaccounts": enricher_storage,
    "microsoft.web/sites": enricher_webapp,
    "microsoft.network/networksecuritygroups": enricher_nsg,
}


def apply_enricher(res_client: ResourceManagementClient, base: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    rtype = (base.get("type") or "").lower()
    # match esatto
    if rtype in ENRICHERS:
        return ENRICHERS[rtype](res_client, base, raw)
    # match prefisso (per sottotipi)
    for key, func in ENRICHERS.items():
        if rtype.startswith(key + "/"):
            return func(res_client, base, raw)
    return {}


# -----------------------------------------------------------------------------
# Worker per singola risorsa
# -----------------------------------------------------------------------------

def process_resource(res_client: ResourceManagementClient, res: Any) -> Dict[str, Any]:
    entry = baseline_entry(res)
    try:
        raw = fetch_raw_by_id(res_client, res.id, res.type)
        entry["raw"] = raw
    except Exception as e:
        LOG.debug("raw fetch failed for %s: %s", res.id, e)
        entry["raw_error"] = str(e)
        raw = {"properties": {}}
    # Enrichment opzionale
    try:
        enrich = apply_enricher(res_client, entry, raw)
        if enrich:
            entry.update(enrich)
    except Exception as e:
        entry["enrich_error"] = str(e)
    return entry


# -----------------------------------------------------------------------------
# Main orchestration
# -----------------------------------------------------------------------------

def collect_inventory(subscription_id: str, resource_group: str, *, max_workers: int = 10) -> Dict[str, Any]:
    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    res_client = ResourceManagementClient(cred, subscription_id)

    LOG.info("Enumerazione risorse nel RG '%s'...", resource_group)
    resources = list(res_client.resources.list_by_resource_group(resource_group))
    LOG.info("Trovate %d risorse", len(resources))

    items: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(process_resource, res_client, r) for r in resources]
        for fut in cf.as_completed(futures):
            items.append(fut.result())

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "schema_version": "1.0",
        "collected_at": now,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "count": len(items),
        "items": sorted(items, key=lambda x: (x.get("type") or "", x.get("name") or "")),
    }
    return doc


def main():
    ap = argparse.ArgumentParser(description="Azure Inventory Collector (ibrido)")
    ap.add_argument("--subscription-id", required=True)
    ap.add_argument("--resource-group", required=True)
    ap.add_argument("--output", required=True, help="Percorso file JSON di output")
    ap.add_argument("--workers", type=int, default=10, help="Thread workers (default 10)")
    args = ap.parse_args()

    try:
        doc = collect_inventory(args.subscription_id, args.resource_group, max_workers=args.workers)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        LOG.info("Inventory salvato in %s", args.output)
    except Exception as e:
        LOG.error("Errore durante la raccolta: %s", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
