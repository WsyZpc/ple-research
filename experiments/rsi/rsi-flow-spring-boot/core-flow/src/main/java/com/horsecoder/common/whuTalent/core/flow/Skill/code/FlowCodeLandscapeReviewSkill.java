package com.horsecoder.common.whuTalent.core.flow.skill.code;

import cc.eamon.open.flow.core.FlowEngine;
import cc.eamon.open.flow.core.stereotype.Flow;
import cc.eamon.open.flow.spring.FlowComponent;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

@FlowComponent
public class FlowCodeLandscapeReviewSkill {

    @Flow("FLOW_CODE_PLE_LANDSCAPE_REVIEW")
    public void reviewLandscape(String blackboard) throws IOException, InterruptedException {
        runScript("review", blackboard, "blackboard");
    }

    @Flow("FLOW_CODE_PLE_LANDSCAPE_EXPORT")
    public void exportLandscape(String blackboard) throws IOException, InterruptedException {
        runScript("export", blackboard, "blackboard");
    }

    @Flow("FLOW_CODE_PLE_LANDSCAPE_VERIFY")
    public void verifyLandscape(String blackboard) throws IOException, InterruptedException {
        runScript("verify", blackboard, "result");
    }

    private void runScript(String action, String blackboard, String outputKey) throws IOException, InterruptedException {
        String name = "landscape_" + action;
        String result = PleSkillTrace.run(name, blackboard, input -> execute(action, input));
        FlowEngine.instance().register(outputKey, result);
    }

    private String execute(String action, String blackboard) throws IOException, InterruptedException {
        Path work = Files.createTempDirectory("ple-skill-");
        Path script = work.resolve("landscape_review.py");
        Path guard = work.resolve("roundtrip_schema_guard.py");
        Path common = work.resolve("skill_common.py");
        Path input = work.resolve("input.json");
        Path output = work.resolve("output.json");
        Process process = null;
        try {
            copyResource("landscape_review.py", script);
            copyResource("roundtrip_schema_guard.py", guard);
            copyResource("skill_common.py", common);
            Files.write(input, blackboard.getBytes(StandardCharsets.UTF_8));
            String python = System.getProperty("ple.python", "python");
            long timeout = Long.getLong("ple.skill.timeout.seconds", 180L);
            process = new ProcessBuilder(python, "-B", "-E", "-s", script.toString(), action)
                    .redirectInput(input.toFile())
                    .redirectOutput(output.toFile())
                    .redirectError(ProcessBuilder.Redirect.INHERIT)
                    .start();

            if (!process.waitFor(timeout, TimeUnit.SECONDS)) {
                throw new IOException("landscape_" + action + " 执行超时");
            }
            if (process.exitValue() != 0) {
                throw new IOException("landscape_" + action + " 执行失败，退出码 " + process.exitValue());
            }

            return new String(Files.readAllBytes(output), StandardCharsets.UTF_8);
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
            }
            Files.deleteIfExists(input);
            Files.deleteIfExists(output);
            Files.deleteIfExists(guard);
            Files.deleteIfExists(script);
            Files.deleteIfExists(common);
            Files.deleteIfExists(work);
        }
    }

    private void copyResource(String name, Path target) throws IOException {
        try (InputStream source = getClass().getResourceAsStream("/skills/" + name)) {
            if (source == null) {
                throw new IOException("找不到 Python 资源 /skills/" + name);
            }
            Files.copy(source, target);
        }
    }
}
