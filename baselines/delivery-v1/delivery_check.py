"""Check the workspace-relative output contract declared in the task instruction."""
import posixpath
import re
import shlex

import taskbridge


class DeliveryCheck:
    def __init__(self, session):
        self.session = session
        self.directory = posixpath.join(session.workdir, "output")
        instruction = " ".join(session.instruction.lower().split())
        self.enabled = "save the files that make up your answer under `output/` in this workspace" in instruction
        self.word_memo = self.enabled and re.search(r"\bword memo\b", instruction) is not None
        self.retried = False

    def hint(self):
        if not self.enabled:
            return ""
        return (f"\nThe task's workspace-relative output/ is {self.directory}/. "
                "Save the deliverables there and check them there before finishing.")

    async def inspect(self):
        if not self.enabled:
            return ""
        left = self.session.time_left()
        if left is not None and left < 3:
            return f"Delivery could not be verified before the deadline in {self.directory}/."
        # Use the sandbox bridge: the agent server has a different filesystem.
        folder = shlex.quote(self.directory)
        pattern = " -iname '*.docx'" if self.word_memo else ""
        command = (f"if test -d {folder} && ! test -L {folder}; then "
                   f"find {folder} -type f -size +0c{pattern} -printf 'present' -quit; fi")
        try:
            result = await self.session.exec(command, timeout_sec=2)
        except (taskbridge.TaskError, TimeoutError) as exc:
            message = f"Could not verify {self.directory}/ ({type(exc).__name__})."
        else:
            if result.get("exit_code") == 0 and not result.get("timed_out"):
                if result.get("output", "").strip() == "present":
                    await self.session.log(f"delivery_check: pass {self.directory}/")
                    return ""
                kind = "nonempty Word memo (.docx)" if self.word_memo else "nonempty deliverable"
                message = f"No {kind} was found in {self.directory}/."
            else:
                message = f"Could not inspect the deliverables in {self.directory}/."
        await self.session.log(f"delivery_check: {message}")
        return message

    def correction(self, issue):
        self.retried = True
        return {"role": "user", "content": (
            f"{issue} Locate the files you created and place the requested deliverables "
            f"in {self.directory}/. Open them from that directory before finishing."
        )}

    @staticmethod
    def final(text, issue):
        return f"{text}\n\nDelivery check: {issue}".strip() if issue else text
