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
public class FlowCodeRoundTripSchemaGuardSkill {

    @Flow("FLOW_CODE_ROUNDTRIP_SCHEMA_GUARD")
    public void roundTripSchemaGuard(String blackboard) throws IOException, InterruptedException {
        runScript("roundtrip_schema_guard.py", blackboard, "result");
    }

    @Flow("FLOW_CODE_PLE_EXPORT_LES_DOCX")
    public void exportLesDocx(String blackboard) throws IOException, InterruptedException {
        runScript("export_les_docx.py", blackboard, "blackboard");
    }

    @Flow("FLOW_CODE_PLE_EXPORT_REVIEW_DOCX")
    public void exportReviewDocx(String blackboard) throws IOException, InterruptedException {
        runScript("export_review_docx.py", blackboard, "blackboard");
    }

    static void runScript(String scriptName, String blackboard, String outputKey) throws IOException, InterruptedException {
        String name = scriptName.substring(0, scriptName.length() - 3);
        String result = PleSkillTrace.run(name, blackboard, input -> execute(scriptName, input));
        FlowEngine.instance().register(outputKey, result);
    }

    private static String execute(String scriptName, String blackboard) throws IOException, InterruptedException {
        Path work = Files.createTempDirectory("ple-skill-");
        Path script = work.resolve(scriptName);
        Path common = work.resolve("skill_common.py");
        Path input = work.resolve("input.json");
        Path output = work.resolve("output.json");
        Process process = null;
        try {
            copyResource(scriptName, script);
            copyResource("skill_common.py", common);
            Files.write(input, blackboard.getBytes(StandardCharsets.UTF_8));
            String python = System.getProperty("ple.python", "python");
            long timeout = Long.getLong("ple.skill.timeout.seconds", 180L);
            process = new ProcessBuilder(python, "-B", "-E", "-s", script.toString())
                    .redirectInput(input.toFile())
                    .redirectOutput(output.toFile())
                    .redirectError(ProcessBuilder.Redirect.INHERIT)
                    .start();

            if (!process.waitFor(timeout, TimeUnit.SECONDS)) {
                throw new IOException(scriptName + " 执行超时");
            }
            if (process.exitValue() != 0) {
                throw new IOException(scriptName + " 执行失败，退出码 " + process.exitValue());
            }

            return new String(Files.readAllBytes(output), StandardCharsets.UTF_8);
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
            }
            Files.deleteIfExists(input);
            Files.deleteIfExists(output);
            Files.deleteIfExists(script);
            Files.deleteIfExists(common);
            Files.deleteIfExists(work);
        }
    }

    private static void copyResource(String name, Path target) throws IOException {
        try (InputStream source = FlowCodeRoundTripSchemaGuardSkill.class.getResourceAsStream("/skills/" + name)) {
            if (source == null) {
                throw new IOException("找不到 Python 资源 /skills/" + name);
            }
            Files.copy(source, target);
        }
    }
}
