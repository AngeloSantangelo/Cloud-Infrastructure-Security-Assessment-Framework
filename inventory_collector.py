#!/usr/bin/env python3
"""
Azure Inventory Collector — RAW ONLY (universale) + sub-resources essenziali

Cosa fa:
- Enumera tutte le risorse top-level nel Resource Group
- Aggiunge sub-resources chiave NON sempre elencate di default:
    • Microsoft.Sql/servers/firewallRules
    • Microsoft.Web/sites/config  (id: .../sites/<name>/config/web)
- Per OGNI risorsa (top-level e sub), esegue una GET ARM generica e salva le RAW:
    {
      "raw": {
        "api_version": "...",
        "object": { ... risposta ARM completa ... },
        "properties": { ... scorciatoia a object.properties ... }
      }
    }

Uso:
  python inventory_collector.py \
    --subscription-id <SUB_ID> \
    --resource-group <RG_NAME> \
    --output ./inventory.json \
"""
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
from time import sleep
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.core.exceptions import HttpResponseError

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOG = logging.getLogger("inventory")
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

for noisy in ["azure", "msrest", "uamqp"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

os.environ.setdefault("AZURE_CORE_TELEMETRY_ENABLED", "false")

# -----------------------------------------------------------------------------
# Retry helper
# -----------------------------------------------------------------------------
def retry(fn, *, tries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def wrapper(*args, **kwargs):
        t = tries
        d = delay
        while t > 0:
            try:
                return fn(*args, **kwargs)
            except HttpResponseError as e:
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
    if "/" not in resource_type:
        raise ValueError(f"Invalid resource type: {resource_type}")
    parts = resource_type.split("/")
    provider = parts[0]
    path = "/".join(parts[1:])
    return provider, path

@retry
def resolve_api_version(res_client: ResourceManagementClient, full_type: str) -> str:
    """Resolve a good apiVersion for the given resource type (prefer stable)."""
    key = (res_client._config.subscription_id, full_type.lower())  # type: ignore[attr-defined]
    cached = API_CACHE.get(key)
    if cached:
        return cached
    provider, path = _split_provider_type(full_type)
    prov = res_client.providers.get(provider)  # type: ignore[arg-type]

    best: Optional[str] = None
    best_preview: Optional[str] = None

    def pick(candidates: List[str]) -> Tuple[Optional[str], Optional[str]]:
        stable = [v for v in candidates if "preview" not in v.lower()]
        previews = [v for v in candidates if "preview" in v.lower()]
        def _sort_key(v: str) -> Tuple[int, str]:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", v)
            return (int(m.group(1).replace("-", "")) if m else 0, v)
        stable.sort(key=_sort_key, reverse=True)
        previews.sort(key=_sort_key, reverse=True)
        return (stable[0] if stable else None, previews[0] if previews else None)

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
    if best_preview:
        API_CACHE.set(key, best_preview)
        return best_preview

    all_versions: List[str] = []
    for rt in prov.resource_types:  # type: ignore[attr-defined]
        all_versions.extend(list(rt.api_versions or []))
    if all_versions:
        all_versions.sort(reverse=True)
        API_CACHE.set(key, all_versions[0])
        return all_versions[0]
    raise RuntimeError(f"Unable to resolve apiVersion for {full_type}")

# -----------------------------------------------------------------------------
# Baseline + raw fetch
# -----------------------------------------------------------------------------
def baseline_entry(res: Any) -> Dict[str, Any]:
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
    return {
        "api_version": api_version,
        "object": as_dict,
        "properties": as_dict.get("properties", {}),
    }

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _parse_rg_and_name_from_id(resource_id: str) -> Tuple[str, str]:
    parts = resource_id.split("/")
    # /subscriptions/<sub>/resourceGroups/<rg>/providers/<Provider>/<Type>/<name>
    rg = parts[4]
    name = parts[-1]
    return rg, name

# -----------------------------------------------------------------------------
# Sub-resources: SQL firewallRules
# -----------------------------------------------------------------------------
def _process_sql_fw_rule(res_client: ResourceManagementClient, rule, server_location: Optional[str]) -> Dict[str, Any]:
    entry = {
        "id": rule.id,
        "name": getattr(rule, "name", None),
        "type": "Microsoft.Sql/servers/firewallRules",
        "location": server_location,
        "tags": {},
    }
    try:
        entry["raw"] = fetch_raw_by_id(res_client, rule.id, "Microsoft.Sql/servers/firewallRules")
    except Exception as e:
        entry["raw_error"] = str(e)
    return entry

def collect_sql_firewall_rules(cred, subscription_id: str, res_client: ResourceManagementClient, sql_servers: List[Any]) -> List[Dict[str, Any]]:
    if not sql_servers:
        return []
    sql_client = SqlManagementClient(cred, subscription_id)
    entries: List[Dict[str, Any]] = []

    def worker(server):
        rg, sname = _parse_rg_and_name_from_id(server.id)
        server_loc = getattr(server, "location", None)
        try:
            rules = list(sql_client.firewall_rules.list_by_server(rg, sname))
        except Exception as e:
            LOG.warning("Impossibile elencare firewall rules per %s: %s", server.id, e)
            return []
        return [_process_sql_fw_rule(res_client, r, server_loc) for r in rules]

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(worker, s) for s in sql_servers]
        for fut in cf.as_completed(futures):
            entries.extend(fut.result() or [])
    return entries

# -----------------------------------------------------------------------------
# Sub-resources: Web App configuration (Microsoft.Web/sites/config, name='web')
# -----------------------------------------------------------------------------
def _process_web_config(res_client: ResourceManagementClient, config_id: str, site_location: Optional[str]) -> Dict[str, Any]:
    entry = {
        "id": config_id,
        "name": "web",
        "type": "Microsoft.Web/sites/config",
        "location": site_location,
        "tags": {},
    }
    try:
        entry["raw"] = fetch_raw_by_id(res_client, config_id, "Microsoft.Web/sites/config")
    except Exception as e:
        entry["raw_error"] = str(e)
    return entry

def collect_web_sites_config(cred, subscription_id: str, res_client: ResourceManagementClient, web_sites: List[Any]) -> List[Dict[str, Any]]:
    if not web_sites:
        return []
    web_client = WebSiteManagementClient(cred, subscription_id)
    entries: List[Dict[str, Any]] = []

    def worker(site):
        rg, sname = _parse_rg_and_name_from_id(site.id)
        site_loc = getattr(site, "location", None)
        config_id = f"{site.id}/config/web"
        try:
            _ = web_client.web_apps.get_configuration(rg, sname)
        except Exception as e:
            LOG.debug("Config SDK non letta per %s: %s (ok, continuo con ARM raw)", site.id, e)
        return _process_web_config(res_client, config_id, site_loc)

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(worker, s) for s in web_sites]
        for fut in cf.as_completed(futures):
            res = fut.result()
            if res:
                entries.append(res)
    return entries

# -----------------------------------------------------------------------------
# Worker per risorsa top-level
# -----------------------------------------------------------------------------
def process_resource(res_client: ResourceManagementClient, res: Any) -> Dict[str, Any]:
    entry = baseline_entry(res)
    try:
        entry["raw"] = fetch_raw_by_id(res_client, res.id, res.type)
    except Exception as e:
        LOG.debug("raw fetch failed for %s: %s", res.id, e)
        entry["raw_error"] = str(e)
    return entry

# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------
def collect_inventory(subscription_id: str, resource_group: str, *, max_workers: int = 10) -> Dict[str, Any]:
    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    res_client = ResourceManagementClient(cred, subscription_id)

    LOG.info("Enumerazione risorse nel RG '%s'...", resource_group)
    resources = list(res_client.resources.list_by_resource_group(resource_group))
    LOG.info("Trovate %d risorse top-level", len(resources))

    items: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(process_resource, res_client, r) for r in resources]
        for fut in cf.as_completed(futures):
            items.append(fut.result())

    # Sub-resources: SQL firewallRules
    sql_servers = [r for r in resources if (getattr(r, "type", "") or "").lower() == "microsoft.sql/servers"]
    fw_entries: List[Dict[str, Any]] = []
    if sql_servers:
        LOG.info("Raccolgo sub-resources SQL firewallRules per %d server...", len(sql_servers))
        fw_entries = collect_sql_firewall_rules(cred, subscription_id, res_client, sql_servers)
        LOG.info("Aggiunte %d firewallRules", len(fw_entries))

    # Sub-resources: Web sites/config
    web_sites = [r for r in resources if (getattr(r, "type", "") or "").lower() == "microsoft.web/sites"]
    cfg_entries: List[Dict[str, Any]] = []
    if web_sites:
        LOG.info("Raccolgo sub-resources WebApp config per %d siti...", len(web_sites))
        cfg_entries = collect_web_sites_config(cred, subscription_id, res_client, web_sites)
        LOG.info("Aggiunte %d sites/config", len(cfg_entries))

    all_items = items + fw_entries + cfg_entries

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "schema_version": "2.0-raw",
        "collected_at": now,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "count": len(all_items),
        "items": sorted(all_items, key=lambda x: (x.get("type") or "", x.get("name") or "")),
    }
    return doc

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Azure Inventory Collector — RAW ONLY (universale)")
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
