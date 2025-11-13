#!/usr/bin/env python3
# Uso:
#   python reporting_engine.py inventory.json risk.json compliance.json report.pdf remediations.yaml

import sys
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime
from matplotlib.patches import Wedge

import yaml
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_remediations(path: str | None) -> dict:
    """remediations.yaml (facoltativo):

    rules:
      - id: "storage-public-container"
        remediation: "Disable public access..."
      - id: "nsg-no-internet-admin-ports"
        remediation: "Restrict SSH/RDP..."
    """
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    mapping = {}
    for r in data.get("rules", []):
        rid = r.get("id")
        txt = r.get("remediation")
        if rid and txt:
            mapping[rid] = txt
    return mapping


def human_datetime(iso_str: str | None) -> str:
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

def make_risk_gauge(score_percent: float, title: str = "", grade: str | None = None) -> BytesIO | None:
    """Semicerchio stile tachimetro (0–100%) orientato correttamente."""
    if score_percent is None:
        return None

    v = max(0.0, min(float(score_percent), 100.0))  # clamp 0-100
    angle = 180.0 * v / 100.0                       # quanto riempire

    # colori
    if v < 20:
        color = "#22c55e"
    elif v < 40:
        color = "#eab308"
    elif v < 70:
        color = "#f97316"
    else:
        color = "#ef4444"

    fig, ax = plt.subplots(figsize=(4, 2.2), subplot_kw={"aspect": "equal"})
    ax.axis("off")

    #
    # Semicerchio di sfondo GRIGIO (da 180° a 0°)
    #
    bg = Wedge(
    (0, 0),
    1.0,
    180,          # inizio sinistra
    0,            # fine destra
    facecolor="#e5e7eb",   # 👈 deve essere chiaro, NON arancione
    edgecolor="#9ca3af",
    linewidth=1,
    )
    ax.add_patch(bg)

    #
    # Fetta colorata: parte da 180° (sinistra) fino a 180° - angle
    #
    fg = Wedge(
    (0, 0),
    1.0,
    180,          # inizio sempre da sinistra
    180 - angle,  # fine proporzionale
    facecolor=color,       # 👈 arancione/verde/rosso
    edgecolor=color,
    linewidth=1,
    )
    ax.add_patch(fg)

    #
    # Testo centrale (valore)
    #
    ax.text(
        0,
        -0.15,
        f"{v:.1f}%",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="black",
    )

    #
    # Etichetta grado
    #
    if grade:
        grade_label = f"{grade} risk"
    else:
        grade_label = "Risk score"

    ax.text(
        0,
        -0.42,
        grade_label,
        ha="center",
        va="center",
        fontsize=9,
        color="#4b5563",
    )

    #
    # Titolo sopra
    #
    if title:
        ax.set_title(title, fontsize=10)

    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-0.55, 1.05)

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _short_framework_name(name: str) -> str:
    """Abbreviazione carina per i nomi framework da usare nel grafico."""
    if not name:
        return "Unknown"
    # es: "CIS Microsoft Azure Foundations v5.0.0" -> "Foundations v5.0.0"
    if "Azure" in name:
        try:
            part = name.split("Azure", 1)[1].strip()
            return part
        except Exception:
            return name
    return name


def make_framework_compliance_chart(fw_list: list[dict]) -> BytesIO | None:
    """Bar chart: numero di controlli FAIL per framework."""
    labels = []
    values = []

    for fw in fw_list:
        ctrls = fw.get("controls") or []
        if not ctrls:
            continue
        fail = sum(1 for c in ctrls if c.get("status") == "FAIL")
        if fail == 0:
            continue
        labels.append(_short_framework_name(fw.get("name") or "Unknown"))
        values.append(fail)

    if not labels:
        return None

    fig, ax = plt.subplots(figsize=(4.5, 2.5))
    x = range(len(labels))
    ax.bar(x, values)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Failed controls")
    ax.set_title("Failed controls per framework")
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def make_bar_chart(labels, values, title: str) -> BytesIO | None:
    if not labels or not any(values):
        return None
    fig, ax = plt.subplots(figsize=(4, 2.2))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel("Count")
    ax.set_xlabel("")
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def build_styles():
    styles = getSampleStyleSheet()
    # aumenta leggermente il font base
    styles["Normal"].fontSize = 12       
    styles["Normal"].leading = 14
    styles.add(ParagraphStyle(
        name="Heading1Custom",
        parent=styles["Heading1"],
        fontSize=18,
        leading=20,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Heading2Custom",
        parent=styles["Heading2"],
        fontSize=14,
        leading=16,
        spaceBefore=8,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Heading3Custom",
        parent=styles["Heading3"],
        fontSize=12,
        leading=14,
        spaceBefore=6,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor="#555555",
    ))
    styles.add(ParagraphStyle(
        name="NormalBold",
        parent=styles["Normal"],
        fontSize=11,
        leading=13,
        spaceAfter=2,
        fontName="Helvetica-Bold"
    ))
    return styles


def main(inventory_path: str, risk_path: str, compliance_path: str,
         pdf_path: str, remediations_path: str | None = None) -> None:

    # --- Input JSON/YAML -------------------------------------------------
    inventory = load_json(inventory_path)
    risk_doc = load_json(risk_path)
    compliance_doc = load_json(compliance_path)
    remap = load_remediations(remediations_path)

    overall = risk_doc.get("overall") or {}
    by_severity_raw = risk_doc.get("by_severity") or {}
    resources_raw = risk_doc.get("resources") or []

    # --- Severità (ordine decente) --------------------------------------
    sev_order = ["critical", "high", "medium", "low"]
    severity_table = []
    for s in sev_order:
        severity_table.append({
            "label": s.capitalize(),
            "key": s,
            "count": int(by_severity_raw.get(s, 0)),
        })
    for s, cnt in by_severity_raw.items():
        if s not in sev_order:
            severity_table.append({
                "label": s,
                "key": s,
                "count": int(cnt),
            })

    # --- Risorse ordinate per risk_score --------------------------------
    resources_sorted = sorted(
        resources_raw,
        key=lambda r: r.get("resource_score", 0.0),
        reverse=True,
    )
    top_resources = [r for r in resources_sorted if r.get("resource_score", 0.0) > 0][:10]

    detailed_resources = []
    for r in resources_sorted:
        findings = []
        for f in r.get("findings", []):
            rid = f.get("rule_id")
            sev = (f.get("severity") or "").lower()
            remediation = remap.get(rid)
            if not remediation:
                remediation = f"Remediation TBD for rule '{rid}'"
            findings.append({
                "rule_id": rid,
                "severity": sev or None,
                "remediation": remediation,
            })
        r_out = dict(r)
        r_out["findings"] = findings

        max_w = r.get("max_severity_weight", 0.0)
        max_sev = None
        for name, w in [("critical", 10), ("high", 5), ("medium", 3), ("low", 1)]:
            if max_w == w:
                max_sev = name.capitalize()
                break
        r_out["max_severity"] = max_sev
        detailed_resources.append(r_out)

    # --- Compliance summary ---------------------------------------------
    controls = compliance_doc.get("controls") or []

    # Per il conteggio totale/pass/fail usiamo ancora il livello "aggregato"
    total_controls = len(controls)
    fail_count = sum(1 for c in controls if c.get("status") == "FAIL")
    pass_count = sum(1 for c in controls if c.get("status") == "PASS")

    by_framework = {}

    for c in controls:
        # Se esiste "sources", contiene il dettaglio per ogni control_id singolo
        sources = c.get("sources")

        if sources:
            for src in sources:
                fw_name = src.get("framework") or "Unknown"
                ctrl_id = src.get("control_id") or c.get("control_id")
                desc = src.get("description") or c.get("description")
                title = src.get("title") or c.get("title") 

                entry = by_framework.setdefault(fw_name, [])
                entry.append({
                    "control_id": ctrl_id,
                    "title": title,
                    "description": desc,
                    "status": c.get("status", "UNKNOWN"),
                    "affected_count": len(c.get("affected_resources") or []),
                    "violated_rules": c.get("violated_rules") or [],
                })
        else:
            # fallback: vecchio comportamento (nessun "sources")
            fw_val = c.get("framework")
            if isinstance(fw_val, list):
                frameworks = fw_val
            else:
                frameworks = [fw_val or compliance_doc.get("framework") or "Unknown"]

            for fw in frameworks:
                fw_name = fw or "Unknown"
                entry = by_framework.setdefault(fw_name, [])
                entry.append({
                    "control_id": c.get("control_id"),
                    "title": c.get("title"),
                    "description": c.get("description"),
                    "status": c.get("status", "UNKNOWN"),
                    "affected_count": len(c.get("affected_resources") or []),
                    "violated_rules": c.get("violated_rules") or [],
                })

    fw_list = []
    for name, ctrls in sorted(by_framework.items(), key=lambda x: x[0]):
        # merge per control_id dentro lo stesso framework
        merged: dict[str, dict] = {}

        for c in ctrls:
            cid = c.get("control_id") or "Unknown"
            if cid not in merged:
                # prima volta che vediamo questo control_id
                merged[cid] = dict(c)
            else:
                # uniamo le informazioni
                m = merged[cid]

                # se una delle occorrenze è FAIL, il control resta FAIL
                if c.get("status") == "FAIL":
                    m["status"] = "FAIL"

                # affected_count: prendiamo il massimo (o potresti fare la somma, se preferisci)
                m["affected_count"] = max(
                    m.get("affected_count", 0),
                    c.get("affected_count", 0),
                )

                # violated_rules: unione dei set
                vr1 = set(m.get("violated_rules") or [])
                vr2 = set(c.get("violated_rules") or [])
                m["violated_rules"] = sorted(vr1.union(vr2))
                if not m.get("title") and c.get("title"):
                    m["title"] = c["title"]

                # description: tieni la prima non vuota (di solito identica)
                if not m.get("description") and c.get("description"):
                    m["description"] = c["description"]

        fw_list.append({
            "name": name,
            "controls": sorted(
                merged.values(),
                key=lambda c: (c["status"] != "FAIL", c["control_id"] or ""),
            ),
        })


    # --- Grafici -------------------------------------------
    severity_labels = [s["label"] for s in severity_table]
    severity_values = [s["count"] for s in severity_table]
    sev_buf = make_bar_chart(severity_labels, severity_values, "Findings by severity")

    comp_buf = make_bar_chart(
        ["PASS", "FAIL"],
        [pass_count, fail_count],
        "Compliance status (controls)",
    )

    gauge_buf = make_risk_gauge(
        overall.get("score_percent", 0.0),
        title="Environment risk score",
        grade=overall.get("risk_grade") or "Unknown",
    )

    fw_comp_buf = make_framework_compliance_chart(fw_list)

    # --- Context per testi ----------------------------------------------
    inv_ctx = {
        "subscription_id": inventory.get("subscription_id"),
        "resource_group": inventory.get("resource_group"),
        "collected_at": inventory.get("collected_at"),
        "collected_at_human": human_datetime(inventory.get("collected_at")),
    }

    risk_ctx = {
        "score_percent": overall.get("score_percent", 0.0),
        "base_score_percent": overall.get("base_score_percent", 0.0),
        "grade": (overall.get("risk_grade") or "Unknown"),
        "total_resources": overall.get("total_resources", 0),
        "total_findings": overall.get("total_findings", 0),
    }

    compliance_ctx = {
        "total_controls": total_controls,
        "fail_count": fail_count,
        "pass_count": pass_count,
    }

    # --- ReportLab: costruzione del PDF ---------------------------------
    styles = build_styles()
    story = []

    # Header
    story.append(Paragraph("Cloud Infrastructure Security Assessment", styles["Heading1Custom"]))
    header_text = (
        f"Subscription: {inv_ctx['subscription_id'] or 'N/A'}<br/>"
        f"Resource Group: {inv_ctx['resource_group'] or 'N/A'}<br/>"
        f"Inventory collected at: {inv_ctx['collected_at_human']}"
    )
    story.append(Paragraph(header_text, styles["Small"]))
    story.append(Spacer(1, 12))

    grade = risk_ctx["grade"]
    summary_text = (
        f"<b>Overall Risk Grade:</b> {grade} "
        f"({risk_ctx['score_percent']}%)"
    )
    story.append(Paragraph(summary_text, styles["Normal"]))
    story.append(Spacer(1, 10))

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary", styles["Heading2Custom"]))

    kpi_data = [
        ["KPI", "Value"],
        ["Environment risk score", f"{risk_ctx['score_percent']}%"],
        ["Resources & findings", f"{risk_ctx['total_resources']} resources, {risk_ctx['total_findings']} findings"],
        ["Compliance", f"{compliance_ctx['fail_count']} / {compliance_ctx['total_controls']} controls in FAIL"],
    ]
    kpi_table = Table(kpi_data, hAlign="LEFT")
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # gauge del risk score
    if gauge_buf:
        story.append(Image(gauge_buf, width=300, height=150))
        story.append(Spacer(1, 8))

    story.append(Paragraph("1.1 Findings by Severity", styles["Heading3Custom"]))

    sev_table_data = [["Severity", "Count"]] + [
        [s["label"], str(s["count"])] for s in severity_table
    ]
    sev_table = Table(sev_table_data, hAlign="LEFT")
    sev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(sev_table)
    story.append(Spacer(1, 6))

    if sev_buf:
        story.append(Image(sev_buf, width=400, height=180))
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(Paragraph("1.2 Top Risky Resources", styles["Heading3Custom"]))
    if top_resources:
        tr_data = [["#", "Resource", "Type", "Location", "Score", "Sensitivity", "#Findings"]]
        for idx, r in enumerate(top_resources, start=1):
            tr_data.append([
                str(idx),
                r.get("name") or r.get("resource_id"),
                r.get("type") or "N/A",
                r.get("location") or "N/A",
                f"{r.get('resource_score', 0.0):.2f}",
                f"{r.get('sensitivity', 0.0):.2f}",
                str(len(r.get("findings") or [])),
            ])
        col_widths = [25, 110, 200, 70, 50, 60, 65]
        tr_table = Table(tr_data, repeatRows=1, colWidths=col_widths)
        tr_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story.append(tr_table)
    else:
        story.append(Paragraph("No risky resources detected.", styles["Small"]))

    story.append(PageBreak())

    # 2. Detailed Findings
    story.append(Paragraph("2. Detailed Findings", styles["Heading2Custom"]))
    story.append(Paragraph(
        "This section provides a per-resource view of misconfigurations detected, "
        "including violated rules and suggested remediation notes.", styles["Small"]))
    story.append(Spacer(1, 8))

    if not detailed_resources:
        story.append(Paragraph("No findings in the environment.", styles["Small"]))
        story.append(PageBreak())
    else:
        for r in detailed_resources:
            header = f"{r.get('name') or r.get('resource_id')} — {r.get('type') or 'N/A'}"
            story.append(Paragraph(header, styles["NormalBold"]))
            meta = (
                f"ID: {r.get('resource_id')}<br/>"
                f"Location: {r.get('location') or 'N/A'}<br/>"
                f"Risk score: {r.get('resource_score', 0.0):.2f} "
                f"(sensitivity {r.get('sensitivity', 0.0):.2f})"
            )
            story.append(Paragraph(meta, styles["Small"]))
            story.append(Spacer(1, 4))

            findings = r.get("findings") or []
            if not findings:
                story.append(Paragraph("No findings for this resource.", styles["Small"]))
                story.append(Spacer(1, 6))
                continue

            f_data = [["#", "Rule ID", "Severity"]]
            for idx, f in enumerate(findings, start=1):
                f_data.append([
                    str(idx),
                    f.get("rule_id"),
                    (f.get("severity") or "N/A").capitalize(),
                ])
            col_widths = [25, 200, 65]
            f_table = Table(f_data, repeatRows=1, colWidths=col_widths)
            f_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(f_table)
            story.append(Spacer(1, 10))

        story.append(PageBreak())

    # 3. Compliance Summary
    story.append(Paragraph("3. Compliance Summary", styles["Heading2Custom"]))
    story.append(Spacer(1, 4))

    # 3.1 Overall Compliance Status
    story.append(Paragraph("3.1 Overall Compliance Status", styles["Heading3Custom"]))
    comp_table_data = [
        ["Status", "Count"],
        ["PASS", str(pass_count)],
        ["FAIL", str(fail_count)],
    ]
    comp_table = Table(comp_table_data, hAlign="LEFT")
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 6))

    if comp_buf:
        story.append(Image(comp_buf, width=400, height=180))
        story.append(Spacer(1, 10))

    # 3.2 Compliance by Framework
    story.append(Paragraph("3.2 Compliance by Framework", styles["Heading3Custom"]))
    story.append(Spacer(1, 6))

    if fw_comp_buf:
        story.append(Image(fw_comp_buf, width=400, height=200))
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    for fw in fw_list:
        # Titolo del framework (es. CIS Microsoft Azure Foundations v5.0.0)
        story.append(Paragraph(fw["name"], styles["NormalBold"]))
        story.append(Spacer(1, 4))

        ctrls = fw["controls"]
        if not ctrls:
            story.append(Paragraph("No controls for this framework.", styles["Small"]))
            story.append(Spacer(1, 8))
            continue

        # ---------- TABELLINA COMPATTA ----------
        table_data = [["Control ID", "Status", "#Affected", "Violated Rules"]]

        for c in ctrls:
            table_data.append([
                c["control_id"],
                c["status"],
                str(c["affected_count"]),
                ", ".join(c["violated_rules"]),
            ])

        fw_table = Table(
            table_data,
            repeatRows=1,
            colWidths=[80, 50, 60, 180],
            hAlign="LEFT",
        )
        fw_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

        story.append(fw_table)
        story.append(Spacer(1, 8))

        # ---------- BLOCCHI DESCRIPTION + REMEDIATION (deduplicati per control_id) ----------
        seen_ids = set()

        for c in ctrls:
            control_id = c.get("control_id") or "Unknown"

            # se questo control ID è già stato stampato per questo framework, salta
            if control_id in seen_ids:
                continue
            seen_ids.add(control_id)

            title = c.get("title") or ""
            description = c.get("description") or "No description available."
            remediation = "Remediation TBD."  # in futuro: legata a un yaml di remediation

            if title:
                header = f"{control_id} — {title}"
            else:
                header = control_id

            story.append(Paragraph(f"<b>{header}</b>", styles["NormalBold"]))
            story.append(Paragraph(f"<b>Description:</b> {description}", styles["Small"]))
            story.append(Paragraph(f"<b>Remediation:</b> {remediation}", styles["Small"]))
            story.append(Spacer(1, 6))

        # spazio extra tra un framework e il successivo
        story.append(Spacer(1, 12))


    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    doc.build(story)
    print(f"Report PDF generato in: {pdf_path}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python reporting_engine.py <inventory.json> <risk.json> <compliance.json> <out.pdf> [remediations.yaml]")
        sys.exit(1)

    inventory_path = sys.argv[1]
    risk_path = sys.argv[2]
    compliance_path = sys.argv[3]
    out_pdf = sys.argv[4]
    remediations_path = sys.argv[5] if len(sys.argv) >= 6 else None

    main(inventory_path, risk_path, compliance_path, out_pdf, remediations_path)
