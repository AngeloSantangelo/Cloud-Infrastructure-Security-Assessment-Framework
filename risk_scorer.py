# Uso:
#   python risk_scorer.py inventory.json report.json compliance.json risk.json
#
# Se non vuoi usare la compliance, puoi passare "-" al posto di compliance.json:
#   python risk_scorer.py inventory.json report.json - risk.json

import json
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------
# Pesi di severità (dal PDF della tesi)
# ---------------------------------------------------------------------
SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 3,
    "low": 1,
}

MAX_SEVERITY_WEIGHT = 10.0  # critical
MAX_SENSITIVITY = 2.0       # env=prod

# ---------------------------------------------------------------------
# Calcolo della sensibilità della risorsa a partire dai tag
# ---------------------------------------------------------------------
def infer_sensitivity(tags: dict) -> float:
    """Determina quanto 'vale' la risorsa (resource sensitivity) dai tag."""
    if not isinstance(tags, dict):
        return 1.0

    # prova a leggere env / environment / ENV ecc.
    env_val = None
    for key in ["env", "environment", "Environment", "ENV", "Env"]:
        if key in tags and tags[key]:
            env_val = str(tags[key]).lower()
            break

    # opzionale: tag esplicito di sensitivity
    sens_val = None
    for key in ["sensitivity", "Sensitivity", "data_classification"]:
        if key in tags and tags[key]:
            sens_val = str(tags[key]).lower()
            break

    # se ho un tag sensitivity esplicito lo considero prioritaro
    if sens_val:
        if sens_val in ["critical", "high"]:
            return 2.0
        if sens_val in ["medium"]:
            return 1.5
        if sens_val in ["low"]:
            return 1.0

    # altrimenti inferisco dall'env
    if env_val:
        if env_val in ["prod", "production", "live"]:
            return 2.0
        if env_val in ["stage", "staging", "preprod", "pre-production"]:
            return 1.5
        if env_val in ["dev", "development", "test", "testing", "lab"]:
            return 0.75

    # default
    return 1.0

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main(inventory_path: str, findings_path: str, compliance_path: str, out_path: str) -> None:
    # 1) Carico inventario (per ricavare tags, name, type, ecc.)
    inv_doc = json.load(open(inventory_path, encoding="utf-8"))
    items = inv_doc.get("items", [])
    item_by_id = {it.get("id"): it for it in items if it.get("id")}

    total_resources = len(items)

    # 2) Carico findings del Configuration Analyzer
    findings_doc = json.load(open(findings_path, encoding="utf-8"))
    findings = findings_doc.get("findings", [])

    # indicizzo i findings per resource_id
    findings_by_res = {}
    for f in findings:
        rid = f.get("resource_id")
        if not rid:
            continue
        findings_by_res.setdefault(rid, []).append(f)

    # 3) (Opzionale) carico risultato di compliance
    compliance_doc = None
    failed_controls = None
    total_controls = None

    if compliance_path and compliance_path != "-":
        try:
            compliance_doc = json.load(open(compliance_path, encoding="utf-8"))
            controls = compliance_doc.get("controls", [])
            total_controls = len(controls) if controls is not None else 0
            failed_controls = sum(1 for c in controls if c.get("status") == "FAIL")
        except FileNotFoundError:
            compliance_doc = None

    # 4) Calcolo per-resource score
    resources_out = []
    sum_resource_scores = 0.0

    for rid, item in item_by_id.items():
        res_findings = findings_by_res.get(rid, [])
        tags = item.get("tags") or {}
        sensitivity = infer_sensitivity(tags)

        # severità massima fra i findings della risorsa
        max_w = 0.0
        findings_out = []
        for f in res_findings:
            sev_raw = (f.get("severity") or "").lower()
            w = SEVERITY_WEIGHTS.get(sev_raw, 0.5 if sev_raw else 0.0)
            if w > max_w:
                max_w = w

            findings_out.append({
                "rule_id": f.get("Rule Violated") or f.get("rule_id"),
                "severity": sev_raw or None,
            })

        resource_score = max_w * sensitivity
        sum_resource_scores += resource_score

        resources_out.append({
            "resource_id": rid,
            "name": item.get("name"),
            "type": item.get("type"),
            "location": item.get("location"),
            "tags": tags,
            "sensitivity": sensitivity,
            "max_severity_weight": max_w,
            "resource_score": resource_score,
            "findings": findings_out,
        })

    # 5) Statistiche per severità (conta findings)
    by_severity = {}
    for f in findings:
        sev = (f.get("severity") or "unknown").lower()
        by_severity[sev] = by_severity.get(sev, 0) + 1

    # 6) Calcolo Environment Risk Score (0-100%)
    if total_resources == 0:
        base_percent = 0.0
        score_percent = 0.0
    else:
        avg_score_per_resource = sum_resource_scores / float(total_resources)
        theoretical_max = MAX_SEVERITY_WEIGHT * MAX_SENSITIVITY  # 10 * 2.0 = 20
        base_percent = (avg_score_per_resource / theoretical_max) * 100.0
        if base_percent < 0:
            base_percent = 0.0
        if base_percent > 100:
            base_percent = 100.0

        score_percent = base_percent

        # amplifico leggermente se falliscono molti controlli CIS
        if compliance_doc and total_controls:
            fail_ratio = (failed_controls or 0) / float(total_controls)
            # massimo +50% se tutti i controlli sono FAIL
            score_percent = base_percent * (1.0 + 0.5 * fail_ratio)
            if score_percent > 100.0:
                score_percent = 100.0

    # 7) Risk grade (stringa da usare nel report)
    if score_percent < 20:
        grade = "Very Low"
    elif score_percent < 40:
        grade = "Low"
    elif score_percent < 60:
        grade = "Medium"
    elif score_percent < 80:
        grade = "High"
    else:
        grade = "Critical"

    out_doc = {
        "schema_version": "1.0-risk",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "score_percent": round(score_percent, 2),
            "base_score_percent": round(base_percent, 2),
            "risk_grade": grade,
            "total_resources": total_resources,
            "total_findings": len(findings),
            "failed_controls": failed_controls,
            "total_controls": total_controls,
        },
        "by_severity": by_severity,
        "resources": sorted(
            resources_out,
            key=lambda r: r.get("resource_score", 0.0),
            reverse=True,
        ),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_doc, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Uso: python risk_scorer.py <inventory.json> <findings.json> <compliance.json|- > <out.json>")
        sys.exit(1)

    inventory_path = sys.argv[1]
    findings_path = sys.argv[2]
    compliance_path = sys.argv[3]
    out_path = sys.argv[4]
    main(inventory_path, findings_path, compliance_path, out_path)
