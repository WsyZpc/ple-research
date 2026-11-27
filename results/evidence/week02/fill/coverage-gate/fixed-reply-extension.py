
# Same initial fixture as the previous replay. These additions are used only when the
# new checklist returns a sourced gap, to exercise bounded repair and document readback.
_original_fill_reply = chat_json


def chat_json(system, data, **kwargs):
    reply, usage = _original_fill_reply(system, data, **kwargs)
    if "engineering solver" not in system:
        return reply, usage
    feedback = json.loads(data.get("retry_feedback") or "{}")
    new_gaps = [item for item in feedback.get("findings", []) if item.get("code") == "FILL_COVERAGE_MISSING"]
    if not new_gaps:
        return reply, usage
    docs = data["documents"]
    report_path = next(name for name in docs if Path(name).name.startswith("Field_Density_Report_SF-26-0708"))
    report = docs[report_path]
    spec, _ = replay_ref(docs, "spec_312000_", r"material actually placed")
    register, _ = replay_ref(docs, "thelbridge_verification_register", r"\b012\b.*Modified Proctor")
    placement, _ = replay_ref(docs, "fill_placement_records_blocka_", r"Borrow source.*Stockpile north of Block C")
    findings = [
        ("SF-26-0708, dated 07/09/2026 for testing on 07/08/2026, uses historical Wexford Ridge Phase 1 "
         "ASTM D698 Method A, 118.6 pcf and 12.1% optimum moisture. Its reported PASS flags are based on "
         "that reference and do not establish compliance for the Block A material. Under Article 1.2.A.1, "
         "D698 is for historical characterization only. See SF-26-0708 pp. 1–2."),
        ("Under Article 3.4.B each location independently requires dry density at least 95% of the maximum "
         "and moisture within −1 to +2 percentage points of optimum, using ASTM D1557 Method C on the material "
         "actually placed. Neither Larchwood Pit nor Phase 1 provides an applicable denominator. Both absolute "
         f"acceptance limits are undetermined until the stockpile is tested. See {spec}."),
    ]
    for test_id in ("FD-14", "FD-15", "FD-16", "FD-17"):
        line = next((line for line in report.splitlines() if re.search(rf"^L\d+:\s*{test_id}\b", line)), "")
        if not line:
            raise ValueError(f"Field report excerpt lacks {test_id}")
        values = re.search(r"Lift\s+6\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+PASS", line)
        density, moisture, old_percent = values.groups()
        ref = report_path + ":" + line.split(":", 1)[0]
        findings.append(
            f"{test_id}: measured {density} pcf dry density and {moisture}% moisture. The report shows "
            f"{old_percent}% against the inapplicable D698 reference. Reject the reported acceptance for {test_id}; "
            f"evaluate both readings again against the actual stockpile's D1557 Method C values. [{ref}]"
        )
    findings.extend([
        ("Item 012 closed on 09/22/2025 based on the Larchwood Pit D1557 report. That closure covered the "
         f"lab report on file and does not establish the acceptance basis for Item 054. See {register}."),
        ("Testing frequency: Article 3.7.A.1 requires one ASTM D6938 test per 5,000 sf per lift and no fewer "
         f"than three per lift. Four tests exceed the minimum of three for the logged 11,400 sf lift. See {placement}. "
         "Verify documented subgrade acceptance and the applicable inspection attendance before release. "
         "Spot nuclear-gauge readings by themselves do not establish continuous special inspection."),
        ("Construction hold: do not proceed with construction on the fill until the independent laboratory "
         "obtains new ASTM D1557 Method C maximum dry density and optimum moisture for the actual stockpile, "
         "the gradation retest is verified, and FD-14 through FD-17 are re-evaluated under Article 3.4.B. "
         "If either criterion fails, rework and retest the affected locations under Article 3.4.C. "
         "Resolve Item 054 before the 07/20/2026 closure deadline."),
    ])
    marker = "\n5. CONCLUSION AND RECOMMENDATION\n"
    reply["draft_output"] = reply["draft_output"].replace(marker, "\n" + "\n".join(findings) + marker)
    return reply, usage
