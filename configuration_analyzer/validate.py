# Requisiti:
#   pip install jsonpath-ng pyyaml

import json, sys, re, yaml
from jsonpath_ng.ext import parse as jp  # parser esteso (serve per JSONPath base)

# Operatori base
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
    """Valuta una JSONPath sull'oggetto (ritorna singolo valore o lista, o None se vuoto)."""
    if not expr:
        return None
    matches = [m.value for m in jp(expr).find(obj)]
    if not matches:
        return None
    return matches[0] if len(matches) == 1 else matches

def eval_clause_on(obj, clause):
    """Valuta una clausola (any/all/not/operator) su obj, dove i riferimenti '$.' sono relativi a obj."""
    if "any" in clause:
        return any(eval_clause_on(obj, c) for c in clause["any"])
    if "all" in clause:
        return all(eval_clause_on(obj, c) for c in clause["all"])
    if "not" in clause:
        return not eval_clause_on(obj, clause["not"])

    # Operatore binario
    (op_name, args), = clause.items()
    left = args.get("left"); right = args.get("right")
    lv = jget(obj, left) if isinstance(left, str) and left.startswith("$.") else left
    rv = jget(obj, right) if isinstance(right, str) and right.startswith("$.") else right
    return OP[op_name](lv, rv)

def eval_where(locals_dict, where):
    """
    Valuta la clausola where su locals_dict (che contiene i valori di 'select').
    Estensioni supportate:
      - any_item: { in: "$.<lista>", satisfy: <clausola> }  -> True se almeno un elemento soddisfa la clausola
    """
    if "any_item" in where:
        spec = where["any_item"]
        seq = jget(locals_dict, spec.get("in"))
        if not isinstance(seq, list):
            return False
        pred = spec.get("satisfy", {})
        for el in seq:
            if eval_clause_on(el, pred):
                return True
        return False

    # Altrimenti, valuta come insieme di clausole standard sul locals_dict
    return eval_clause_on(locals_dict, where)

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
                # costruisce il contesto locale dai select
                local = {k: jget(it, expr) for k, expr in sel.items()}
                local["item"] = it 
                if eval_where(local, where):
                    # Chiavi in ordine: resource_id, Rule Violated, severity
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
