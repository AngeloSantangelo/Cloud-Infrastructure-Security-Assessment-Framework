import json
import sys
import yaml
from collections import defaultdict

def main(findings_path, mapping_path, out_path):
    findings_doc = json.load(open(findings_path, encoding="utf-8"))
    findings = findings_doc.get("findings", [])

    mapping = yaml.safe_load(open(mapping_path, encoding="utf-8"))
    global_framework = mapping.get("framework", "CIS-Microsoft-Azure-Composite")
    controls_cfg = mapping.get("controls", [])

    violated_by_rule = defaultdict(list)
    for f in findings:
        rule_id = f.get("Rule Violated") or f.get("rule_id")
        rid = f.get("resource_id")
        if rule_id and rid:
            violated_by_rule[rule_id].append(rid)

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


    DEDUP_EXCEPT_RULES = {"nsg-no-internet-admin-ports"}

    def dedup_key(entry: dict):
        vr = tuple(sorted(entry.get("violated_rules") or []))
        if any(r in DEDUP_EXCEPT_RULES for r in vr):
            return None
        return vr


    groups = {}
    passthrough = []

    for c in controls_out:
        key = dedup_key(c)
        if key is None:
            passthrough.append(c)
        else:
            groups.setdefault(key, []).append(c)

    dedup_controls = []
    for vr_key, items in groups.items():
        if len(items) == 1:
            dedup_controls.append(items[0])
            continue

        rep = items[0]
        rep_description = rep.get("description", "")
        rep_title = items[0].get("title", "")
        rep_rule_ids = list(vr_key)

        status = "PASS"
        affected = set()

        control_ids = []
        frameworks = []
        sources = []

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

        merged_control_id = " + ".join([c for c in control_ids if c])

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

    final_controls = passthrough + dedup_controls

    out_doc = {
        "framework": global_framework,
        "controls": final_controls,
    }

    json.dump(out_doc, open(out_path, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
