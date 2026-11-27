
# Controlled response replay for original task inputs. Loaded only into the test classpath.
def replay_ref(docs, prefix, pattern):
    path = next(name for name in docs if Path(name).name.casefold().startswith(prefix))
    row = next(line for line in docs[path].splitlines() if re.search(pattern, line, re.I))
    return path + ":" + row.split(":", 1)[0], row


def chat_json(system, data, **kwargs):
    if "engineering solver" in system:
        docs = data["documents"]
        lab, lab_row = replay_ref(docs, "proctor_d1557_", r"Borrow Source.*Larchwood Pit")
        placement, placement_row = replay_ref(docs, "fill_placement_records_blocka_", r"Borrow source.*Stockpile north of Block C")
        rfi, rfi_row = replay_ref(docs, "rfi_log_", r"\bRFI 079\b.*subject to gradation retest")
        spec, _ = replay_ref(docs, "spec_312000_", r"material actually placed")
        scope = "Stockpile north of Block C"
        old_source = "Larchwood Pit"
        draft = (
            "1. PURPOSE\nReview the Block A slab-on-grade compaction record for Item 054.\n"
            "2. DOCUMENTS REVIEWED\nBlock A Placement Records, VMT-25-0918-P04, RFI Log and Earth Moving Rev 3.\n"
            "3. BASIS OF REVIEW\nSection 31 20 00 requires ASTM D1557 Method C on material actually placed. "
            f"[{spec}]\n4. FINDINGS\n")
        fixed_basis = (f"The placement log identifies the {scope} [{placement}]. "
                       f"VMT-25-0918-P04 tested {old_source} [{lab}]. "
                       "A matching D1557 Method C determination has not been established in the reviewed files. "
                       "Density and moisture acceptance limits remain undetermined for the material placed.")
        fixed_rfi = (f"RFI 079 approved reuse of the {scope} subject to a gradation retest, "
                     f"referencing TPM-25-079 [{rfi}]. The closed entry establishes the RFI disposition. "
                     "It does not document completion of the gradation retest. Obtain and verify that retest before acceptance.")
        targets = data.get("repair_claim_ids", [])
        if targets:
            assert set(targets) == {"FILL_TEST_BASIS", "FILL_RFI_079"}
            assert data["retrieved_line_anchors"], "repair did not receive newly retrieved evidence"
        claims = [dict(claim_id="FILL_TEST_BASIS", param="compaction test basis", unit="1", source_entity=scope if targets else old_source,
                       target_entity=scope, value=fixed_basis if targets else "Applied VMT-25-0918-P04",
                       provenance=placement if targets else lab, regime_or_version="Block A slab-on-grade")]
        if targets:
            claims.append(dict(claim_id="FILL_RFI_079", param="RFI 079 gradation retest", unit="1", source_entity="RFI 079",
                               target_entity="RFI 079", value=fixed_rfi, provenance=rfi, regime_or_version="Block A slab-on-grade"))
        findings = fixed_basis + "\n" + fixed_rfi if targets else "The review applies the off-site laboratory value."
        proposal = draft + findings + "\n5. CONCLUSION AND RECOMMENDATION\nItem 054 remains open."
        return dict(claims=claims, draft_output=proposal,
                    missing_evidence=[dict(message="A stockpile-specific laboratory determination remains unverified.")]), {}
    if "independent engineering" in system:
        return dict(conflicts=[], missing_evidence=[]), {}
    docs = data["authority_documents"]
    rfi, _ = replay_ref(docs, "rfi_log_", r"\bRFI 079\b.*subject to gradation retest")
    quote = next((s for s in data["draft_output"].splitlines() if s.startswith("RFI 079 approved reuse")), "")
    return dict(requirements=[dict(id="RFI_079", description="Check stockpile approval scope and gradation retest", provenance=rfi)],
                draft_responses=[dict(id="RFI_079", quote=quote)] if quote else [], attribution_warnings=[]), {}
