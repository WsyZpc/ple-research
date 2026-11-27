package com.horsecoder.common.whuTalent.core.flow.skill.code;

import cc.eamon.open.flow.core.FlowEngine;
import cc.eamon.open.flow.core.stereotype.Flow;
import cc.eamon.open.flow.spring.FlowComponent;
import com.alibaba.fastjson.JSONObject;

/** Adapters between JSON-string Skill outputs and scalar RSI route expressions. */
@FlowComponent
public class FlowCodePleRouting {
    @Flow("FLOW_CODE_PLE_START_REVIEW")
    public void startReview(String taskDir, String instruction, String expectedSchema) {
        initialize(taskDir, instruction, expectedSchema, false);
    }

    @Flow("FLOW_CODE_PLE_START_ENTITY_REVIEW")
    public void startEntityReview(String taskDir, String instruction, String expectedSchema) {
        initialize(taskDir, instruction, expectedSchema, true);
    }

    private void initialize(String taskDir, String instruction, String expectedSchema, boolean extended) {
        JSONObject board = new JSONObject();
        board.put("task_dir", taskDir);
        board.put("instruction", instruction);
        board.put("expected_schema", expectedSchema);
        board.put("max_retry", 2);
        if (extended) board.put("trace_id", java.util.UUID.randomUUID().toString());
        board.put("retry_count", 0);
        if (extended && "fill-compaction-acceptance".equals(taskDir)) {
            board.put("fill_compaction", true);
            board.put("max_retry", 1);
        }
        if (extended && (taskDir.equals("les-mesh-resolution")
                || taskDir.equals("les-mesh-resolution/environment/files"))) {
            board.put("entity_review_extensions", true);
            if (expectedSchema.trim().startsWith("{")) {
                JSONObject spec = JSONObject.parseObject(expectedSchema);
                if (spec.containsKey("retention_required_text")) {
                    board.put("retention_required_text", spec.get("retention_required_text"));
                }
            }
        }
        FlowEngine.instance().register("blackboard", board.toJSONString());
    }

    @Flow("FLOW_CODE_PLE_PREPARE_REPAIR")
    public void prepareRepair(String blackboard) {
        JSONObject board = JSONObject.parseObject(blackboard);
        JSONObject feedback = board.getJSONObject("retry_feedback");
        boolean supportsLocal = board.getBooleanValue("entity_review_extensions") || board.getBooleanValue("fill_compaction");
        boolean local = supportsLocal && feedback != null
                && feedback.getJSONArray("repair_claim_ids") != null && !feedback.getJSONArray("repair_claim_ids").isEmpty();
        board.put("solver_entry", local ? "REPAIR" : "SOLVE");
        if (local) board.put("retention_mode", "snapshot");
        FlowEngine.instance().register("repair_scope", local ? "local" : "full")
                .register("blackboard", board.toJSONString());
    }

    @Flow("FLOW_CODE_PLE_PREPARE_COMPARISON")
    public void prepareComparison(String blackboard) {
        JSONObject board = JSONObject.parseObject(blackboard);
        board.put("retention_mode", "compare");
        FlowEngine.instance().register("blackboard", board.toJSONString());
    }

    @Flow("FLOW_CODE_PLE_PREPARE_WORD_CHECK")
    public void prepareWordCheck(String blackboard) {
        JSONObject board = JSONObject.parseObject(blackboard);
        boolean requested = board.getJSONArray("retention_required_text") != null
                && !board.getJSONArray("retention_required_text").isEmpty();
        board.put("word_retention_requested", requested);
        if (requested) board.put("retention_mode", "artifact");
        FlowEngine.instance().register("word_check", requested ? "run" : "skip")
                .register("blackboard", board.toJSONString());
    }

    @Flow("FLOW_CODE_PLE_SELECT_DELIVERY")
    public void selectDelivery(String result) {
        JSONObject board = JSONObject.parseObject(result);
        String dir = board.getString("task_dir").replace('\\', '/');
        boolean les = dir.equals("les-mesh-resolution") || dir.equals("les-mesh-resolution/environment/files");
        String delivery = "none";
        if (les) {
            delivery = "les_docx";
        } else if ("fill-compaction-acceptance".equals(dir) && board.getBooleanValue("fill_compaction")) {
            delivery = "fill_docx";
        }
        FlowEngine.instance().register("delivery", delivery)
                .register("blackboard", result).register("result", result);
    }

    @Flow("FLOW_CODE_PLE_READ_ROUTE")
    public void readRoute(String blackboard) {
        String status = JSONObject.parseObject(blackboard).getString("route_status");
        if (!"PASS".equals(status) && !"RETRY_CONFLICT".equals(status)
                && !"TRANSPORT_PAUSED".equals(status) && !"EVIDENCE_HOLD".equals(status) && !"MAX_RETRY_REACHED".equals(status)) {
            throw new IllegalStateException("Unknown PLE route: " + status);
        }
        FlowEngine.instance().register("route_status", status).register("result", blackboard);
    }

    @Flow("FLOW_CODE_PLE_SELECT_ENTRY")
    public void selectEntry(String blackboard) {
        JSONObject board = JSONObject.parseObject(blackboard);
        String entry = board.getString("review_entry");
        board.remove("review_entry");
        if (entry == null) entry = "SOLVE";
        if (!java.util.Arrays.asList("SOLVE", "REPAIR", "AUDIT_1", "AUDIT_2").contains(entry))
            throw new IllegalArgumentException("Unsupported review entry: " + entry);
        FlowEngine.instance().register("entry", entry).register("blackboard", board.toJSONString());
    }

    @Flow("FLOW_CODE_PLE_FINISH_TRACE")
    public void finishTrace(String result) throws java.io.IOException {
        PleSkillTrace.finish(result);
        FlowEngine.instance().register("result", result);
    }
}
