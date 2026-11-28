package com.horsecoder.common.whuTalent.core.flow.skill.code;

import cc.eamon.open.flow.core.stereotype.Flow;
import cc.eamon.open.flow.spring.FlowComponent;

import java.io.IOException;

@FlowComponent
public class FlowCodeRequirementExtractionSkill {
    @Flow("FLOW_CODE_REQUIREMENT_EXTRACTION")
    public void requirementExtraction(String blackboard) throws IOException, InterruptedException {
        FlowCodeRoundTripSchemaGuardSkill.runScript("requirement_extraction.py", blackboard, "result");
    }
}
