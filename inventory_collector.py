#!/usr/bin/env python3
"""
Azure Inventory Collector — baseline + plugin + sub-resources (SQL firewallRules)

Esegui:
  python inventory_collector.py     --subscription-id <SUB_ID>     --resource-group <RG_NAME>     --output ./inventory.json

Requisiti:
  pip install azure-identity azure-mgmt-resource azure-mgmt-sql
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
from azure.core.exceptions import HttpResponseError

LOG = logging.getLogger("inventory")
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

for noisy in ["azure", "msrest", "uamqp"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

os.environ.setdefault("AZURE_CORE_TELEMETRY_ENABLED", "false")

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
                sleep(d); d *= backoff; t -= 1
    return wrapper

@dataclass
class ApiVersionCache:
    cache: Dict[Tuple[str, str], str]
    def get(self, key: Tuple[str, str]) -> Optional[str]: return self.cache.get(key)
    def set(self, key: Tuple[str, str], value: str) -> None: self.cache[key] = value
API_CACHE = ApiVersionCache(cache={})

def _split_provider_type(resource_type: str) -> Tuple[str, str]:
    parts = resource_type.split("/"); return parts[0], "/".join(parts[1:])

@retry
def resolve_api_version(res_client: ResourceManagementClient, full_type: str) -> str:
    key = (res_client._config.subscription_id, full_type.lower())
    cached = API_CACHE.get(key)
    if cached: return cached
    provider, path = _split_provider_type(full_type)
    prov = res_client.providers.get(provider)
    best = None; best_preview = None
    def pick(cands: List[str]):
        stable = [v for v in cands if "preview" not in v.lower()]
        previews = [v for v in cands if "preview" in v.lower()]
        def _k(v: str):
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", v); return (int(m.group(1).replace("-","")) if m else 0, v)
        stable.sort(key=_k, reverse=True); previews.sort(key=_k, reverse=True)
        return (stable[0] if stable else None, previews[0] if previews else None)
    segs = path.split("/")
    for i in range(len(segs), 0, -1):
        needle = "/".join(segs[:i]).lower()
        for rt in prov.resource_types:
            if rt.resource_type.lower() == needle:
                s, p = pick(list(rt.api_versions or []))
                best = best or s; best_preview = best_preview or p
                if best: API_CACHE.set(key, best); return best
    if best_preview: API_CACHE.set(key, best_preview); return best_preview
    allv = []; [allv.extend(list(rt.api_versions or [])) for rt in prov.resource_types]
    if allv: allv.sort(reverse=True); API_CACHE.set(key, allv[0]); return allv[0]
    raise RuntimeError(f"Unable to resolve apiVersion for {full_type}")

def baseline_entry(res: Any) -> Dict[str, Any]:
    return {"id": res.id, "name": getattr(res, "name", None), "type": getattr(res, "type", None),
            "location": getattr(res, "location", None), "tags": getattr(res, "tags", None) or {}}

@retry
def fetch_raw_by_id(res_client: ResourceManagementClient, resource_id: str, resource_type: str) -> Dict[str, Any]:
    api_version = resolve_api_version(res_client, resource_type)
    generic = res_client.resources.get_by_id(resource_id, api_version)
    as_dict = generic.as_dict()
    return {"api_version": api_version, "object": as_dict, "properties": as_dict.get("properties", {})}

Enricher = Any

def enricher_storage(res_client, base, raw):
    props = raw.get("properties", {}) or {}
    net = props.get("networkAcls", {}) or props.get("networkRuleSet", {}) or {}
    https_only = props.get("supportsHttpsTrafficOnly")
    min_tls = props.get("minimumTlsVersion")
    public_network = (net.get("defaultAction") == "Allow") if net else None
    return {"enrich": {"storage": {"https_only": https_only, "minimum_tls": min_tls, "public_network_access": public_network}}}

def enricher_webapp(res_client, base, raw):
    props = raw.get("properties", {}) or {}
    return {"enrich": {"webapp": {"https_only": props.get("httpsOnly"), "ftps_state": props.get("ftpsState")}}}

def enricher_nsg(res_client, base, raw):
    props = raw.get("properties", {}) or {}
    rules = props.get("securityRules", []) or []
    risky_ports = {"22","3389","1433","3306","5432","9200"}
    open_inbound = []
    for r in rules:
        rp = r.get("properties", {})
        if (rp.get("direction") == "Inbound" and rp.get("access") == "Allow" and (rp.get("sourceAddressPrefix") in ("*","0.0.0.0/0","Internet"))):
            sp = str(rp.get("destinationPortRange") or "")
            if sp and any(p in sp for p in risky_ports):
                open_inbound.append({"rule": r.get("name"), "port": sp, "protocol": rp.get("protocol")})
    return {"enrich": {"nsg": {"open_internet_rules": open_inbound}}}

ENRICHERS: Dict[str, Enricher] = {
    "microsoft.storage/storageaccounts": enricher_storage,
    "microsoft.web/sites": enricher_webapp,
    "microsoft.network/networksecuritygroups": enricher_nsg,
}

def apply_enricher(res_client, base, raw):
    rtype = (base.get("type") or "").lower()
    if rtype in ENRICHERS: return ENRICHERS[rtype](res_client, base, raw)
    for key, func in ENRICHERS.items():
        if rtype.startswith(key + "/"): return func(res_client, base, raw)
    return {}

# ---- Sub-resources: SQL firewallRules ----
def _parse_rg_and_name_from_id(resource_id: str) -> Tuple[str, str]:
    parts = resource_id.split("/"); return parts[4], parts[-1]

def _process_sql_fw_rule(res_client, rule, server_location):
    entry = {"id": rule.id, "name": getattr(rule, "name", None), "type": "Microsoft.Sql/servers/firewallRules",
             "location": server_location, "tags": {}}
    try:
        entry["raw"] = fetch_raw_by_id(res_client, rule.id, "Microsoft.Sql/servers/firewallRules")
    except Exception as e:
        entry["raw_error"] = str(e)
    return entry

def collect_sql_firewall_rules(cred, subscription_id: str, res_client, sql_servers: List[Any]) -> List[Dict[str, Any]]:
    if not sql_servers: return []
    sql_client = SqlManagementClient(cred, subscription_id)
    entries: List[Dict[str, Any]] = []
    def worker(server):
        rg, sname = _parse_rg_and_name_from_id(server.id)
        server_loc = getattr(server, "location", None)
        try:
            rules = list(sql_client.firewall_rules.list_by_server(rg, sname))
        except Exception as e:
            LOG.warning("Impossibile elencare firewall rules per %s: %s", server.id, e); return []
        return [_process_sql_fw_rule(res_client, r, server_loc) for r in rules]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(worker, s) for s in sql_servers]
        for fut in cf.as_completed(futures):
            entries.extend(fut.result() or [])
    return entries

def process_resource(res_client, res):
    entry = baseline_entry(res)
    try:
        raw = fetch_raw_by_id(res_client, res.id, res.type)
        entry["raw"] = raw
    except Exception as e:
        LOG.debug("raw fetch failed for %s: %s", res.id, e); entry["raw_error"] = str(e); raw = {"properties": {}}
    try:
        enrich = apply_enricher(res_client, entry, raw)
        if enrich: entry.update(enrich)
    except Exception as e:
        entry["enrich_error"] = str(e)
    return entry

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

    sql_servers = [r for r in resources if (r.type or "").lower() == "microsoft.sql/servers"]
    if sql_servers:
        LOG.info("Raccolgo sub-resources SQL firewallRules per %d server...", len(sql_servers))
        fw_entries = collect_sql_firewall_rules(cred, subscription_id, res_client, sql_servers)
        items.extend(fw_entries)
        LOG.info("Aggiunte %d firewallRules", len(fw_entries))

    now = datetime.now(timezone.utc).isoformat()
    doc = {"schema_version": "1.1", "collected_at": now, "subscription_id": subscription_id,
           "resource_group": resource_group, "count": len(items),
           "items": sorted(items, key=lambda x: ((x.get("type") or ""), (x.get("name") or "")))}
    return doc

def main():
    ap = argparse.ArgumentParser(description="Azure Inventory Collector (ibrido + sub-resources)")
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
        LOG.error("Errore durante la raccolta: %s", e); sys.exit(2)

if __name__ == "__main__": main()
