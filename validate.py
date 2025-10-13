
# validate.py — Valida regole YAML statiche su inventory.json
# Requisiti:
#   pip install jsonpath-ng pyyaml
#
# Uso:
#   python validate.py ./inventory.json ./rules.yaml ./report.json
import json, sys, re, yaml
from jsonpath_ng import parse as jp

OP = {
    "equals":       lambda v, w: v == w,
    "not_equals":   lambda v, w: v != w,
    "in":           lambda v, arr: v in (arr or []),
    "not_in":       lambda v, arr: v not in (arr or []),
    "regex":        lambda v, pat: bool(re.search(pat, str(v) or "")),
    "exists":       lambda v, _: v is not None,
    "contains":     lambda v, w: (isinstance(v, (list, tuple, set)) and w in v) or (isinstance(v, str) and str(w) in v),
    "gt":           lambda v, w: (v is not None and w is not None and v > w),
    "gte":          lambda v, w: (v is not None and w is not None and v >= w),
    "lt":           lambda v, w: (v is not None and w is not None and v < w),
    "lte":          lambda v, w: (v is not None and w is not None and v <= w),
}

def jget(obj, expr):
    if not expr:
        return None
    matches = [m.value for m in jp(expr).find(obj)]
    if not matches:
        return None
    return matches[0] if len(matches) == 1 else matches

def eval_clause(locals_dict, clause):
    if "any" in clause:
        return any(eval_clause(locals_dict, c) for c in clause["any"])
    if "all" in clause:
        return all(eval_clause(locals_dict, c) for c in clause["all"])
    if "not" in clause:
        return not eval_clause(locals_dict, clause["not"])
    (op_name, args), = clause.items()
    left = args.get("left"); right = args.get("right")
    lv = jget(locals_dict, left) if isinstance(left, str) and left.startswith("$.") else left
    rv = jget(locals_dict, right) if isinstance(right, str) and right.startswith("$.") else right
    return OP[op_name](lv, rv)

def type_matches(item_type: str, rule_type: str) -> bool:
    it = (item_type or "").lower()
    rt = (rule_type or "").lower()
    return it == rt or it.startswith(rt + "/")

def main(inventory_path, rules_path, out_path):
    inv = json.load(open(inventory_path, encoding="utf-8"))
    rules = yaml.safe_load(open(rules_path, encoding="utf-8"))
    items = inv.get("items", [])
    findings = []

    for rule in rules.get("rules", []):
        rtype = rule["resource_type"]
        sel = rule.get("select", {})
        where = rule.get("where", {})
        for it in items:
            if type_matches(it.get("type"), rtype):
                local = {k: jget(it, expr) for k, expr in sel.items()}
                local["item"] = it
                if eval_clause(local, where):
                    finding = {}
                    finding["resource_id"] = it.get("id")
                    finding["Rule Violated"] = rule["id"]
                    finding["severity"] = rule.get("severity", "info")
                    findings.append(finding)

    json.dump({"findings": findings}, open(out_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python validate.py <inventory.json> <rules.yaml> <report.json>")
        sys.exit(1)
    inv, rules, out = sys.argv[1], sys.argv[2], sys.argv[3]
    main(inv, rules, out)
