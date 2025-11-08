# compliance.py
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
        rule_ids = ctrl.get("rules", []) or ctrl.get("rule_ids", [])

        # framework specifico del controllo, se presente; altrimenti quello globale del file
        ctrl_framework = ctrl.get("framework", global_framework)

        affected_resources = set()
        for r in rule_ids:
            affected_resources.update(violated_by_rule.get(r, []))

        status = "FAIL" if affected_resources else "PASS"

        controls_out.append({
            "control_id": ctrl_id,
            "framework": ctrl_framework,
            "description": desc,
            "status": status,
            "violated_rules": rule_ids,
            "affected_resources": sorted(affected_resources),
        })

    out_doc = {
        "framework": global_framework,
        "controls": controls_out,
    }

    json.dump(out_doc, open(out_path, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python compliance.py <findings.json> <mapping.yaml> <out.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
