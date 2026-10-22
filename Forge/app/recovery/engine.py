"""
Recovery & Self-Healing Engine for Project FORGE.
Coordinates diagnosis, anti-loop governance, surgical patch application, and re-verification.
"""

from app.core.logging import get_logger
from app.execution.engine import ExecutionEngine, execution_engine
from app.memory.db import db_manager
from app.memory.state_store import StateStore
from app.recovery.classifier import (
    FailureClassifier,
    FailureDiagnosis,
    failure_classifier,
)
from app.recovery.loop_guard import AntiLoopController, anti_loop_controller
from app.recovery.repair import PatchApplicator, RepairPatch
from app.recovery.syntax_repair import _repair_python_source
from app.verification.engine import VerificationEngine, verification_engine
from app.verification.evidence import VerificationEvidence

logger = get_logger("recovery.engine")


class RecoveryEngine:
    """Automates diagnosis, minimal patching, and verification loops for failing tasks."""

    def __init__(
        self,
        classifier: FailureClassifier | None = None,
        loop_guard: AntiLoopController | None = None,
        applicator: PatchApplicator | None = None,
        verifier: VerificationEngine | None = None,
        store: StateStore | None = None,
        exec_engine: ExecutionEngine | None = None,
    ):
        self.exec_engine = exec_engine or execution_engine
        self.classifier = classifier or failure_classifier
        self.loop_guard = loop_guard or anti_loop_controller
        self.applicator = applicator or PatchApplicator(engine=self.exec_engine)
        self.verifier = verifier or verification_engine
        self.store = store or StateStore(db_manager)
        self.provider = None

    def set_provider(self, provider) -> None:
        """Assign an active model provider for LLM-driven patch synthesis."""
        self.provider = provider

    async def attempt_recovery(
        self,
        task_id: str,
        failed_evidence: VerificationEvidence,
    ) -> tuple[bool, str, RepairPatch | None]:
        """
        Diagnose a failed check and repair it, escalating until something works.

        The repair ladder is, in order:

          1. ``synthesis``    -- LLM patch synthesis, then the hand-written
                                syntactic heuristics that were already here.
          2. ``deterministic``-- compile-validated repair of well-understood
                                syntax defects. Needs no provider, so it still
                                works with every AI endpoint unreachable.
          3. ``agent``        -- the Debugger agent reads the real failure
                                evidence and writes the fix itself.

        A route is only abandoned once it has actually been tried. Before this
        ladder existed, the first route to return *any* patch won and the engine
        never fell through -- so a heuristic that produced a patch which did not
        even compile ended the attempt, and the routes that could have fixed it
        never ran. Verified live: a missing ``:`` after ``def`` was "repaired" by
        the quote/bracket balancer into a still-broken file, and the run reported
        ``route=synthesis`` while the deterministic and agent routes sat unused.

        Returns (recovered: bool, message: str, patch: Optional[RepairPatch]).
        """
        # 1. Classify failure
        diagnosis = self.classifier.classify(failed_evidence)
        logger.info(
            f"[Task {task_id}] Failure classified: {diagnosis.failure_class.value} "
            f"({diagnosis.error_message[:80]})"
        )

        target_file = self._resolve_target_file(task_id, diagnosis)

        last_message = ""
        last_patch: RepairPatch | None = None
        routes_tried: list[str] = []

        for route in ("synthesis", "deterministic", "agent"):
            if route == "synthesis":
                patch = await self._synthesize_patch_for_diagnosis(task_id, diagnosis)
            elif route == "deterministic":
                patch = self._deterministic_syntax_repair(task_id, target_file, diagnosis)
            else:
                patch = await self._escalate_repair_to_agent(
                    task_id, diagnosis, failed_evidence
                )

            if not patch:
                logger.info(f"[Task {task_id}] Repair route '{route}' produced no patch")
                continue

            # A route that hands back code which does not even parse is not a
            # candidate. Rejecting it here is what lets the next route run.
            if not self._patch_is_sound(task_id, patch):
                logger.warning(
                    f"[Task {task_id}] Repair route '{route}' produced an unsound "
                    f"patch for '{patch.target_file}'; trying the next route"
                )
                await self._audit(
                    task_id,
                    "recovery.patch_rejected",
                    {
                        "route": route,
                        "target_file": patch.target_file,
                        "reason": "candidate did not compile",
                    },
                )
                last_patch = patch
                last_message = (
                    f"Route '{route}' produced a patch that does not compile."
                )
                continue

            routes_tried.append(route)

            # 2. Check Anti-Loop Controller
            allowed, reason = self.loop_guard.can_attempt_repair(
                task_id=task_id,
                failure_class=diagnosis.failure_class,
                patch_content=patch.replacement_snippet,
            )
            if not allowed:
                await self._audit(
                    task_id,
                    "recovery.escalated",
                    {"reason": reason, "diagnosis": diagnosis.model_dump(mode="json")},
                )
                return False, f"Recovery Escalation: {reason}", patch

            self.loop_guard.record_repair_attempt(
                task_id=task_id,
                failure_class=diagnosis.failure_class,
                patch_content=patch.replacement_snippet,
            )

            await self._audit(
                task_id,
                "recovery.attempted",
                {
                    "failure_class": diagnosis.failure_class.value,
                    "target_file": patch.target_file,
                    "explanation": patch.explanation,
                    "route": route,
                },
            )

            # Feed the self-brain: which repair route worked for which failure
            # class is exactly the lesson that should shape the next attempt.
            self._remember_repair(task_id, diagnosis, patch, route, "attempted")

            # 3. Apply surgical patch
            applied = self.applicator.apply_patch(task_id, patch, role="debugger")
            if not applied:
                last_message = "Failed to write patch to workspace."
                last_patch = patch
                continue

            # 4. Re-verify task
            new_report = await self.verifier.verify_task(task_id)
            if new_report.all_passed:
                logger.info(
                    f"[Task {task_id}] Recovery succeeded via route '{route}'! "
                    "All verification checks passed."
                )
                self._record_repair_lesson(task_id, diagnosis, patch, True, route)
                await self._audit(
                    task_id,
                    "recovery.succeeded",
                    {"target_file": patch.target_file, "route": route},
                )
                return True, f"Recovery succeeded via route '{route}'. All checks passing.", patch

            logger.warning(
                f"[Task {task_id}] Route '{route}' applied but verification still "
                f"fails: {new_report.failure_reasons}"
            )
            self._record_repair_lesson(task_id, diagnosis, patch, False, route)
            last_message = (
                f"Route '{route}' applied but re-verification failed: "
                f"{new_report.failure_reasons}"
            )
            last_patch = patch

        msg = last_message or (
            f"Unable to synthesize automated patch for {diagnosis.failure_class.value}"
        )
        logger.warning(f"[Task {task_id}] {msg}")
        self._record_repair_lesson(
            task_id, diagnosis, last_patch, False, routes_tried[-1] if routes_tried else "none"
        )
        return False, msg, last_patch

    def _resolve_target_file(self, task_id: str, diagnosis: FailureDiagnosis) -> str:
        """Work out which file a repair should target, tolerating odd paths."""
        target_file = diagnosis.failing_file
        if not target_file:
            try:
                py_files = self.exec_engine.fs.search_files(
                    task_id, pattern="*.py", role="debugger"
                )
                target_file = py_files[0] if py_files else "main.py"
            except Exception:
                target_file = "main.py"
        if "\\" in target_file:
            target_file = target_file.replace("\\", "/")
        if "project/" in target_file:
            target_file = target_file.split("project/")[-1]
        return target_file

    @staticmethod
    def _patch_is_sound(task_id: str, patch: RepairPatch) -> bool:
        """Reject a candidate repair that would not even parse.

        The old heuristics balanced quotes and brackets without checking the
        result, so they could turn one syntax error into a different one and the
        engine would still write it to the workspace.
        """
        if not patch.target_file.endswith(".py"):
            return True
        try:
            compile(patch.replacement_snippet, patch.target_file, "exec")
            return True
        except SyntaxError:
            return False
        except Exception:
            return True

    @staticmethod
    def _remember_repair(
        task_id: str,
        diagnosis: FailureDiagnosis,
        patch: RepairPatch,
        route: str,
        status: str,
    ) -> None:
        """Persist a repair attempt to the self-brain."""
        try:
            from forge_upgrade.memora_client import memora_client

            memora_client.learn_from_outcome(
                agent_name="forge",
                task_name=f"repair:{diagnosis.failure_class.value}",
                status=status,
                error_log=diagnosis.error_message,
                actions_taken=f"route:{route};target:{patch.target_file}",
                domain="self_healing",
            )
        except Exception:
            pass

    async def _audit(self, task_id: str, event_type: str, payload: dict) -> None:
        """Record an audit event without ever failing the repair.

        An audit write must not be able to abort a self-healing attempt. A
        missing task row (FOREIGN KEY), a locked database or a full disk should
        cost us the log line, not the repair -- otherwise the engine trades a
        working fix for a bookkeeping entry.
        """
        if not self.store:
            return
        try:
            await self.store.record_event(
                task_id=task_id, event_type=event_type, payload=payload
            )
        except Exception as exc:
            logger.warning(
                f"[Task {task_id}] Could not record audit event '{event_type}': "
                f"{type(exc).__name__}: {exc}"
            )

    def _deterministic_syntax_repair(
        self, task_id: str, target_file: str, diagnosis: FailureDiagnosis
    ) -> RepairPatch | None:
        """Repair well-understood syntax defects without needing a model.

        The synthesis and agent-escalation routes both depend on a provider that
        can author code. When that provider is the offline fallback -- which is
        what runs whenever the real endpoints are unreachable -- neither can fix
        anything, and the engine used to report "Unable to synthesize automated
        patch" for failures it could have repaired deterministically.

        This route only fires for defects with an unambiguous correction, and the
        candidate is compiled before it is accepted: a repair that does not parse
        is never written to the workspace.
        """
        if not target_file.endswith(".py"):
            return None
        try:
            original = self.exec_engine.fs.read_file(task_id, target_file, role="debugger")
        except Exception:
            return None
        if not isinstance(original, str) or not original.strip():
            return None

        # NUL bytes are never valid Python and make compile() raise ValueError
        # rather than SyntaxError. Strip them up front so the probe below is
        # meaningful; without this a workspace containing binary content crashed
        # the whole repair attempt.
        if "\x00" in original:
            original = original.replace("\x00", "")

        # If it already compiles there is nothing for this route to do.
        try:
            compile(original, target_file, "exec")
            return None
        except SyntaxError:
            pass
        except Exception:
            return None

        candidate = _repair_python_source(original)
        if candidate is None or candidate == original:
            return None

        try:
            compile(candidate, target_file, "exec")
        except Exception:
            return None

        return RepairPatch(
            target_file=target_file,
            original_snippet=original,
            replacement_snippet=candidate,
            explanation=(
                f"Deterministic syntax repair for {diagnosis.failure_class.value}: "
                f"{diagnosis.error_message[:60]}"
            ),
            patch_type="rewrite",
        )

    async def _escalate_repair_to_agent(
        self,
        task_id: str,
        diagnosis: FailureDiagnosis,
        failed_evidence: VerificationEvidence,
    ) -> RepairPatch | None:
        """Hand a repair the heuristics could not solve to a specialist agent.

        This is the engine asking a peer for help. The Debugger reads the real
        failure evidence, the terminal output and the workspace, then writes the
        fix itself through the normal file tools -- so the repair is produced by
        the same code path a DAG node would use, not by a bespoke heuristic.

        Returns a RepairPatch describing what the agent changed (so the anti-loop
        guard and the audit trail still see it), or None if the agent produced no
        usable change.
        """
        try:
            from app.agents.roles import DebuggerRole

            target_file = diagnosis.failing_file
            if not target_file:
                py_files = self.exec_engine.fs.search_files(
                    task_id, pattern="*.py", role="debugger"
                )
                target_file = py_files[0] if py_files else "main.py"
            if "\\" in target_file:
                target_file = target_file.replace("\\", "/")
            if "project/" in target_file:
                target_file = target_file.split("project/")[-1]

            try:
                before = self.exec_engine.fs.read_file(
                    task_id, target_file, role="debugger"
                )
            except Exception:
                before = ""

            try:
                project_files = [
                    f
                    for f in self.exec_engine.fs.search_files(
                        task_id, pattern="*", role="debugger"
                    )
                    if not f.startswith(".") and "/." not in f
                ][:40]
            except Exception:
                project_files = []

            terminal_logs = ""
            try:
                from app.core.context import context_manager

                terminal_logs = context_manager.get_terminal_context(task_id) or ""
            except Exception:
                terminal_logs = ""

            context = {
                "error": (
                    f"Verification check '{failed_evidence.check_name}' failed.\n"
                    f"Failure class: {diagnosis.failure_class.value}\n"
                    f"Error: {diagnosis.error_message}\n"
                    f"Suggested strategy: {diagnosis.suggested_strategy}\n"
                    f"Failing file: {target_file}"
                ),
                "terminal_logs": terminal_logs or "No terminal logs available.",
                "project_files": project_files,
                "target_file": target_file,
            }

            logger.info(
                f"[Task {task_id}] Escalating repair of '{target_file}' to the Debugger agent"
            )
            debugger = DebuggerRole(provider=self.provider)
            result = await debugger.execute_step(
                task_id=task_id,
                node_title=f"Self-heal {diagnosis.failure_class.value} in {target_file}",
                context=context,
                engine=self.exec_engine,
            )

            fixed_files = (result or {}).get("fixed_files") or []
            if not fixed_files:
                logger.warning(
                    f"[Task {task_id}] Debugger agent produced no file changes"
                )
                return None

            try:
                after = self.exec_engine.fs.read_file(
                    task_id, target_file, role="debugger"
                )
            except Exception:
                after = ""

            if not after or after == before:
                logger.warning(
                    f"[Task {task_id}] Debugger agent left '{target_file}' unchanged"
                )
                return None

            await self._audit(
                task_id,
                "recovery.agent_escalated",
                {
                    "agent": "debugger",
                    "target_file": target_file,
                    "files_changed": fixed_files,
                    "diagnosis": (result or {}).get("diagnosis", "")[:500],
                },
            )

            return RepairPatch(
                target_file=target_file,
                original_snippet=before or None,
                replacement_snippet=after,
                explanation=(
                    f"Debugger agent repaired {diagnosis.failure_class.value}: "
                    f"{diagnosis.error_message[:60]}"
                ),
                patch_type="rewrite",
            )
        except Exception as exc:
            logger.warning(f"[Task {task_id}] Agent escalation failed: {exc}")
            return None

    @staticmethod
    def _record_repair_lesson(
        task_id: str,
        diagnosis: FailureDiagnosis,
        patch: RepairPatch | None,
        succeeded: bool,
        route: str,
    ) -> None:
        """Persist the outcome of a repair so the next attempt starts smarter."""
        try:
            from forge_upgrade.memora_client import memora_client

            memora_client.learn_from_outcome(
                agent_name="forge",
                task_name=f"repair:{diagnosis.failure_class.value}",
                status="success" if succeeded else "failure",
                error_log=None if succeeded else diagnosis.error_message,
                actions_taken=f"route:{route};target:{patch.target_file if patch else 'none'}",
                domain="self_healing",
            )
        except Exception:
            pass

    async def _synthesize_patch_for_diagnosis(
        self, task_id: str, diagnosis: FailureDiagnosis
    ) -> RepairPatch | None:
        """Synthesize candidate repair patch based on diagnosis using LLM or heuristics."""
        from app.agents.parser import LLMResponseParser

        target_file = diagnosis.failing_file
        if not target_file:
            py_files = self.exec_engine.fs.search_files(task_id, pattern="*.py", role="debugger")
            target_file = py_files[0] if py_files else "main.py"

        # Sanitize target file relative path
        if "\\" in target_file:
            target_file = target_file.replace("\\", "/")
        if "project/" in target_file:
            target_file = target_file.split("project/")[-1]

        try:
            current_content = self.exec_engine.fs.read_file(task_id, target_file, role="debugger")
        except Exception:
            current_content = ""

        # 1. LLM-driven patch synthesis if provider is assigned
        if self.provider:
            consensus_info = ""
            try:
                from app.integrations.ai_universe_client import get_ai_universe_client

                ai_client = get_ai_universe_client()
                ai_res = await ai_client.consult_with_verification(
                    question=f"Diagnose root cause and suggest code repair for {diagnosis.failure_class.value}: {diagnosis.error_message} in file {target_file}",
                    min_confidence=0.70,
                    use_debate=True,
                )
                if ai_res:
                    consensus_info = f"\nExternal Multi-Agent Consensus (Run ID: {ai_res.run_id}):\n{ai_res.answer}\n"
                    await self._audit(
                        task_id,
                        "ai_universe.consulted",
                        {
                            "run_id": ai_res.run_id,
                            "confidence": ai_res.confidence,
                            "stage": "recovery_patch",
                        },
                    )
            except Exception as e:
                logger.info(f"AI Universe consultation skipped or failed during recovery: {e}")
                await self._audit(
                    task_id,
                    "ai_universe.consultation_failed",
                    {"error": str(e), "stage": "recovery_patch"},
                )

            prompt = (
                f"Fix failure in file '{target_file}':\n"
                f"Failure Class: {diagnosis.failure_class.value}\n"
                f"Error Message: {diagnosis.error_message}\n"
                f"Suggested Strategy: {diagnosis.suggested_strategy}\n"
                f"{consensus_info}"
                f"Current File Content:\n```python\n{current_content}\n```\n\n"
                f"Output the complete fixed file delimited as:\n"
                f"### File: {target_file}\n```python\n<fixed code>\n```"
            )
            try:
                response = await self.provider.generate(
                    prompt=prompt,
                    system_prompt="You are an expert software debugger. Author verified, syntax-clean, bug-free fixes.",
                )
                extracted = LLMResponseParser.extract_files(
                    response.content, default_filename=target_file
                )
                if extracted and extracted[0].content != current_content:
                    return RepairPatch(
                        target_file=extracted[0].relative_path,
                        replacement_snippet=extracted[0].content,
                        explanation=f"LLM repaired {diagnosis.failure_class.value}: {diagnosis.error_message[:60]}",
                        patch_type="rewrite",
                    )
            except Exception as e:
                logger.warning(
                    f"LLM patch synthesis failed: {e}. Falling back to rule-based repair."
                )

        # 2. Basic syntax or indentation repair heuristics fallback
        if diagnosis.failure_class.value == "syntax_error":
            lines = current_content.splitlines()
            if diagnosis.failing_line and 0 < diagnosis.failing_line <= len(lines):
                bad_line = lines[diagnosis.failing_line - 1]
                fixed_line = bad_line

                # Check if failure is due to empty block or comment after except/def/try/if
                prev_line = lines[diagnosis.failing_line - 2] if diagnosis.failing_line >= 2 else ""
                if prev_line.strip().startswith("except ") and (
                    not bad_line.strip() or bad_line.strip().startswith("#")
                ):
                    indent = " " * (len(prev_line) - len(prev_line.lstrip()) + 4)
                    lines.insert(
                        diagnosis.failing_line - 1,
                        f"{indent}print(f'Error: {{exc}}', file=sys.stderr)",
                    )
                    lines.insert(diagnosis.failing_line, f"{indent}return 1")
                    if "__main__" not in current_content:
                        lines.append('\nif __name__ == "__main__":\n    main()\n')
                    return RepairPatch(
                        target_file=target_file,
                        replacement_snippet="\n".join(lines) + "\n",
                        explanation=f"Repaired missing exception block on line {diagnosis.failing_line}",
                        patch_type="rewrite",
                    )

                if fixed_line.count('"') % 2 != 0:
                    fixed_line += '"'
                if fixed_line.count("'") % 2 != 0:
                    fixed_line += "'"
                if fixed_line.count("(") > fixed_line.count(")"):
                    fixed_line += ")" * (fixed_line.count("(") - fixed_line.count(")"))
                if fixed_line.count("[") > fixed_line.count("]"):
                    fixed_line += "]" * (fixed_line.count("[") - fixed_line.count("]"))
                if fixed_line.count("{") > fixed_line.count("}"):
                    fixed_line += "}" * (fixed_line.count("{") - fixed_line.count("}"))
                if fixed_line.strip().startswith(
                    (
                        "def ",
                        "class ",
                        "if ",
                        "for ",
                        "while ",
                        "elif ",
                        "else",
                        "try",
                        "except",
                        "finally",
                    )
                ) and not fixed_line.strip().endswith(":"):
                    fixed_line += ":"

                lines[diagnosis.failing_line - 1] = fixed_line
                repaired_content = "\n".join(lines) + "\n"
                if repaired_content != current_content:
                    return RepairPatch(
                        target_file=target_file,
                        replacement_snippet=repaired_content,
                        explanation=f"Fixed syntax on line {diagnosis.failing_line}",
                        patch_type="rewrite",
                    )

        # No fake repair: if content is unchanged, return None to trigger explicit recovery escalation
        return None


recovery_engine = RecoveryEngine()
