# Uso: python compliance.py report.json compliance_mapping_cis.yaml compliance.json
import json
import sys
import yaml
from collections import defaultdict

def main(findings_path, mapping_path, out_path):
    # 1) Leggo i findings dal Configuration Analyzer
    findings_doc = json.load(open(findings_path, encoding="utf-8"))
    findings = findings_doc.get("findings", [])

    # 2) Leggo il file YAML dei controlli CIS (quello "composito")
    mapping = yaml.safe_load(open(mapping_path, encoding="utf-8"))
    global_framework = mapping.get("framework", "CIS-Microsoft-Azure-Composite")
    controls_cfg = mapping.get("controls", [])

    # 3) Indicizzo le violazioni per rule_id
    violated_by_rule = defaultdict(list)  # rule_id -> [resource_ids]
    for f in findings:
        rule_id = f.get("Rule Violated") or f.get("rule_id")
        rid = f.get("resource_id")
        if rule_id and rid:
            violated_by_rule[rule_id].append(rid)

    # 4) Valuto ogni controllo CIS
    controls_out = []
    for ctrl in controls_cfg:
        ctrl_id = ctrl["id"]
        desc = ctrl.get("description", "")
        title = ctrl.get("title", "")
        remediation = ctrl.get("remediation", "")
        rule_ids = ctrl.get("rules", []) or ctrl.get("rule_ids", [])

        ctrl_framework = ctrl.get("framework", global_framework)

        affected_resources = set()
        for r in rule_ids:
            affected_resources.update(violated_by_rule.get(r, []))

        status = "FAIL" if affected_resources else "PASS"

        controls_out.append({
            "control_id": ctrl_id,
            "framework": ctrl_framework,          
            "title": title,
            "description": desc,                  
            "status": status,
            "violated_rules": rule_ids,
            "affected_resources": sorted(affected_resources),
            "remediation": remediation,
        })

    # === Deduplica dei "controlli logici"
    # Eccezioni: rule_id che NON vanno deduplicati anche se hanno lo stesso violated_rules
    # (es. NSG per porte diverse: rischi distinti)
    DEDUP_EXCEPT_RULES = {"nsg-no-internet-admin-ports"}

    def dedup_key(entry: dict):
        """
        Chiave canonica per deduplica: insieme ordinato delle violated_rules.
        Se tra le violated_rules c'è una regola in eccezione, non deduplicare (pass-through).
        """
        vr = tuple(sorted(entry.get("violated_rules") or []))
        if any(r in DEDUP_EXCEPT_RULES for r in vr):
            return None
        return vr

    # raggruppo per chiave canonica
    groups = {}       # key -> list[control entries] (candidati a fusione)
    passthrough = []  # controlli che saltano la deduplica (eccezioni o gruppi singoli)

    for c in controls_out:
        key = dedup_key(c)
        if key is None:
            # eccezione: non deduplicare
            passthrough.append(c)
        else:
            groups.setdefault(key, []).append(c)

    dedup_controls = []
    for vr_key, items in groups.items():
        if len(items) == 1:
            # non è un duplicato: mantieni il controllo originale
            dedup_controls.append(items[0])
            continue

        # C'è davvero un duplicato: fondi gli elementi del gruppo
        # Rappresentante: PRIMO controllo così come definito nel YAML
        rep = items[0]
        rep_description = rep.get("description", "")
        rep_title = items[0].get("title", "")
        rep_rule_ids = list(vr_key)

        # Stato aggregato: FAIL se almeno uno è FAIL; risorse affette unite
        status = "PASS"
        affected = set()

        # Per tracciare corrispondenza tra ID e framework
        control_ids = []
        frameworks = []
        sources = []  # [{control_id, framework}]

        for it in items:
            cid = it.get("control_id", "")
            fw = it.get("framework", global_framework)
            remediation = it.get("remediation", "")
            control_ids.append(cid)
            frameworks.append(fw)
            sources.append({"control_id": cid, "framework": fw})

            if it.get("status") == "FAIL":
                status = "FAIL"
                affected.update(it.get("affected_resources") or [])

        # Unisci ID con " + " (niente prefisso DEDUP)
        merged_control_id = " + ".join([c for c in control_ids if c])

        # Framework come lista (unica) di tutti i PDF di provenienza
        # Mantieni l'ordine di apparizione, rimuovendo i duplicati
        seen_fw = set()
        merged_frameworks = []
        for fw in frameworks:
            if fw and fw not in seen_fw:
                merged_frameworks.append(fw)
                seen_fw.add(fw)

        dedup_controls.append({
            "control_id": merged_control_id,          
            "framework": merged_frameworks,           
            "title": rep_title,
            "description": rep_description,          
            "status": status,
            "violated_rules": rep_rule_ids,           
            "affected_resources": sorted(affected),
            "sources": sources,                       
            "remediation": remediation,
        })

    # Controlli finali = eccezioni (non deduplicati) + controlli (deduplicati o singoli)
    final_controls = passthrough + dedup_controls

    out_doc = {
        "framework": global_framework,
        "controls": final_controls,
    }

    json.dump(out_doc, open(out_path, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python compliance.py <findings.json> <mapping.yaml> <out.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
