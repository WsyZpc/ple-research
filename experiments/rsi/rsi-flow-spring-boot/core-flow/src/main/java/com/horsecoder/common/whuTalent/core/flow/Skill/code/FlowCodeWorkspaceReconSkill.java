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


/**
 * 运行
 * @com.horsecoder.common.whuTalent.flowTesting.core/FLOW_RUN
 * <p>
 * Author: horsecoder
 * Email: eamon@horsecoder.com
 */
@FlowComponent
public class FlowCodeWorkspaceReconSkill {
    private static final String INPUT_ERROR_PREFIX = "WORKSPACE_RECON_INPUT_ERROR: ";

    /**
     * 运行
     * FLOW_CODE_RUN
     *
     * @param structure 结构
     * @result result 运行结果
     */
    @Flow("FLOW_CODE_WORKSPACE_RECON")
    public void workspaceRecon(String blackboard) throws IOException, InterruptedException {
        FlowEngine.instance().register("result", PleSkillTrace.run("workspace_recon", blackboard, this::execute));
    }

    private String execute(String blackboard) throws IOException, InterruptedException {
        Path work = Files.createTempDirectory("workspace-recon-");
        Path script = work.resolve("workspace_recon.py");
        Path input = work.resolve("input.json");
        Path output = work.resolve("output.json");
        Path errors = work.resolve("stderr.log");
        Process process = null;

        try {
            try (InputStream source =
                         getClass().getResourceAsStream("/skills/workspace_recon.py")) {
                if (source == null) {
                    throw new IOException("找不到 Python 资源 /skills/workspace_recon.py");
                }
                Files.copy(source, script);
            }

            Files.write(input, blackboard.getBytes(StandardCharsets.UTF_8));
            String python = System.getProperty("ple.python", "python");
            process = new ProcessBuilder(python, "-I", "-S", script.toString())
                    .redirectInput(input.toFile())
                    .redirectOutput(output.toFile())
                    .redirectError(errors.toFile())
                    .start();

            if (!process.waitFor(30, TimeUnit.SECONDS)) {
                throw new IOException("WorkspaceReconSkill 扫描超时");
            }
            if (process.exitValue() != 0) {
                String diagnostic = new String(Files.readAllBytes(errors), StandardCharsets.UTF_8).trim();
                if (diagnostic.startsWith(INPUT_ERROR_PREFIX) && diagnostic.indexOf('\n') < 0
                        && diagnostic.indexOf('\r') < 0) {
                    throw new IOException(diagnostic.substring(INPUT_ERROR_PREFIX.length()));
                }
                if (!diagnostic.isEmpty()) {
                    System.err.println(diagnostic);
                }
                throw new IOException("WorkspaceReconSkill 执行失败，退出码 " + process.exitValue()
                        + "。请查看 IDEA 后端控制台。");
            }

            return new String(Files.readAllBytes(output), StandardCharsets.UTF_8);
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(2, TimeUnit.SECONDS);
            }
            Files.deleteIfExists(input);
            Files.deleteIfExists(output);
            Files.deleteIfExists(errors);
            Files.deleteIfExists(script);
            Files.deleteIfExists(work);
        }
    }


}
