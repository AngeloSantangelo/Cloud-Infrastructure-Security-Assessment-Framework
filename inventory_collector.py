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