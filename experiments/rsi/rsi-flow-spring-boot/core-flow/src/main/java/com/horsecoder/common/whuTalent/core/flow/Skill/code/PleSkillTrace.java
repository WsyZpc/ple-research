package com.horsecoder.common.whuTalent.core.flow.skill.code;

import com.alibaba.fastjson.JSONObject;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/** Records skill boundaries, including time spent starting Python and reading files. */
final class PleSkillTrace {
    interface Step {
        String run(String board) throws IOException, InterruptedException;
    }

    private static Path directory(JSONObject board) {
        String id = board.getString("trace_id");
        if (!UUID.fromString(id).toString().equals(id)) throw new IllegalArgumentException("Invalid trace_id");
        String root = System.getenv("PLE_TRACE_ROOT");
        return (root == null ? Paths.get(System.getProperty("user.home"), "ple-traces") : Paths.get(root))
                .toAbsolutePath().normalize().resolve(id);
    }

    private static void save(Path path, String json) throws IOException {
        Path tmp = Files.createTempFile(path.getParent(), ".writing-", ".tmp");
        try {
            Files.write(tmp, json.getBytes(StandardCharsets.UTF_8));
            Files.move(tmp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(tmp);
        }
    }

    static String run(String name, String input, Step step) throws IOException, InterruptedException {
        JSONObject before = JSONObject.parseObject(input);
        if (before.getString("trace_id") == null) return step.run(input);
        if ("TRANSPORT_PAUSED".equals(before.getString("route_status"))) return input;
        Path dir = directory(before);
        Files.createDirectories(dir);
        before.put("trace_dir", dir.toString());
        int seq = before.getIntValue("trace_seq") + 1;
        String prefix = String.format("%03d-%s-%s", seq, name, UUID.randomUUID().toString().substring(0, 8));
        Path snapshot = dir.resolve(prefix + ".input.json");
        String original = before.toJSONString();
        save(snapshot, original);
        for (int attempt = 1; attempt <= 2; attempt++) {
            String stem = prefix + "." + attempt;
            long started = System.nanoTime();
            JSONObject event = new JSONObject(true);
            event.put("node", name);
            event.put("input", snapshot.getFileName().toString());
            event.put("attempt", attempt);
            try {
                JSONObject output = JSONObject.parseObject(step.run(original));
                JSONObject failure = output.getJSONObject("transport_failure");
                if (failure != null) {
                    event.put("status", "transport_error");
                    event.put("error", failure);
                    if (attempt == 1) continue;
                    output = JSONObject.parseObject(original);
                    output.put("route_status", "TRANSPORT_PAUSED");
                    output.put("transport_failure", failure);
                    output.put("failed_node", name);
                    output.put("resume_input", snapshot.toString());
                } else {
                    event.put("status", "returned");
                }
                output.put("trace_seq", seq);
                String result = output.toJSONString();
                String file = stem + ".output.json";
                save(dir.resolve(file), result);
                event.put("output", file);
                event.put("route_status", output.getString("route_status"));
                event.put("retry_count", output.getIntValue("retry_count"));
                if ("engineering_solver".equals(name) && failure == null && before.getIntValue("retry_count") == 0
                        && !"EVIDENCE_HOLD".equals(before.getString("route_status"))) {
                    Path first = dir.resolve("first-solver.json");
                    if (!Files.exists(first)) save(first, result);
                }
                return result;
            } catch (IOException | RuntimeException | InterruptedException e) {
                event.put("status", "execution_error");
                event.put("error", e.getClass().getSimpleName());
                throw e;
            } finally {
                event.put("elapsed_ms", TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
                save(dir.resolve(stem + ".event.json"), event.toJSONString());
            }
        }
        throw new IllegalStateException("No attempt completed");
    }

    static void finish(String result) throws IOException {
        JSONObject board = JSONObject.parseObject(result);
        if (board.getString("trace_id") != null) {
            Path dir = directory(board);
            Files.createDirectories(dir);
            save(dir.resolve("final.json"), result);
        }
    }
}
