"""Forge-side self-repair proposer.

Phase E1. This is the half of the loop that was missing: something has to notice a
real failure, produce a real candidate fix on a real branch, and attach evidence
that the fix actually works before anyone downstream is asked to trust it.

The rule this module exists to enforce: **a proposal may only claim a test passes
if Forge ran that test and watched it pass.** A candidate fix is applied to a real
branch in a real repository, the real test command is executed against that
working tree, and the verbatim output is carried with the proposal. If the command
does not pass, the proposer reports ``fixed=False`` and the candidate is not
promoted into a proposal.

That matters because "I believe this fixes it" is exactly the kind of claim that
turns a bad patch into a production incident. The cost of running the test is a
few seconds; the cost of shipping an unverified patch is larger.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestRun:
    """Verbatim result of one real test invocation."""

    #: pytest collects anything named Test*; this is a value object, not a suite.
    __test__ = False

    command: str
    passed: bool
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

    def as_evidence(self) -> dict[str, Any]:
        """The exact shape FRIDAY's gate accepts as test evidence.

        Note the gate requires ``passed is True``; a failing run can be carried for
        diagnosis but can never be mistaken for a passing one.
        """
        return {
            "command": self.command,
            "passed": self.passed,
            "summary": self.stdout.strip().splitlines()[-1] if self.stdout.strip() else "",
            "returncode": self.returncode,
        }

    def transcript(self) -> str:
        return (
            f"$ {self.command}\n"
            f"exit={self.returncode} passed={self.passed} ({self.duration_ms}ms)\n"
            f"--- stdout ---\n{self.stdout.rstrip()}\n"
            f"--- stderr ---\n{self.stderr.rstrip()}"
        )


@dataclass
class CandidateFix:
    """A proposed change, before any test has been run against it."""

    target_file: str
    original_snippet: str
    replacement_snippet: str
    rationale: str


@dataclass
class RepairProposalRequest:
    """What Forge hands to the gate. Mirrors FRIDAY's RepairProposalRequest."""

    repo_path: str
    branch: str
    base_commit: str
    target_file: str
    original_snippet: str
    replacement_snippet: str
    rationale: str
    proposed_by: str = "forge"
    test_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProposalOutcome:
    """The result of attempting to turn a candidate into a proposal."""

    fixed: bool
    before: TestRun | None
    after: TestRun | None
    branch: str
    base_commit: str
    candidate: CandidateFix
    reason: str = ""

    def to_request(self, repo_path: str) -> RepairProposalRequest:
        """Build the wire payload. Refuses to invent evidence that was not gathered."""
        if not self.fixed or self.after is None:
            raise RuntimeError(
                "refusing to emit a proposal: the candidate did not produce a passing test run"
            )
        return RepairProposalRequest(
            repo_path=str(Path(repo_path).resolve()),
            branch=self.branch,
            base_commit=self.base_commit,
            target_file=self.candidate.target_file,
            original_snippet=self.candidate.original_snippet,
            replacement_snippet=self.candidate.replacement_snippet,
            rationale=self.candidate.rationale,
            proposed_by="forge",
            test_evidence=self.after.as_evidence(),
        )


class GitSelfRepairProposer:
    """Branches a real repository, applies a candidate, and proves it with a real test.

    Every git and test invocation is a real subprocess. Nothing here is simulated,
    and a caller cannot obtain a passing proposal without a passing run.
    """

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    async def _run(self, *args: str, cwd: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        return (
            proc.returncode or 0,
            out.decode("utf-8", errors="replace"),
            err.decode("utf-8", errors="replace"),
        )

    async def _git(self, repo: str, *args: str) -> tuple[int, str, str]:
        return await self._run("git", *args, cwd=repo)

    async def _test(
        self,
        repo: str,
        command: str,
        env: dict[str, str] | None = None,
    ) -> TestRun:
        """Run a real command in the working tree and keep its verbatim output.

        ``env`` overlays the ambient environment. This exists so a caller can
        supply whatever the command needs to run for real (a test suite that must
        disable plugin autoload, a PYTHONPATH, CI flags) without the proposer
        pretending the command passed when it could not even start.
        """
        loop = asyncio.get_running_loop()
        started = loop.time()
        child_env = {**os.environ, **(env or {})}
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=repo,
            env=child_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        duration = int((loop.time() - started) * 1000)
        code = proc.returncode or 0
        return TestRun(
            command=command,
            passed=code == 0,
            returncode=code,
            stdout=out.decode("utf-8", errors="replace"),
            stderr=err.decode("utf-8", errors="replace"),
            duration_ms=duration,
        )

    async def _original_head(self, repo: str) -> tuple[str | None, str]:
        """Where the caller was: ``(branch or None, exact commit)``.

        Recorded before anything is touched. Checking out a commit SHA detaches
        HEAD, so a proposer that only restores *what* it changed and not *where*
        it was leaves the caller's repository on a detached HEAD — every later
        commit would land nowhere, and the operator would have no idea why.

        The commit is kept alongside the refname because a detached caller has no
        refname to return to. Restoring them onto the default branch instead would
        silently move their work.
        """
        ref_code, ref_out, _ = await self._git(repo, "symbolic-ref", "--short", "HEAD")
        ref = ref_out.strip() if ref_code == 0 else ""
        sha_code, sha_out, sha_err = await self._git(repo, "rev-parse", "HEAD")
        sha = sha_out.strip() if sha_code == 0 else ""
        if not sha:
            raise RuntimeError(f"cannot read HEAD before touching the repository: {sha_err}")
        return (ref or None), sha

    async def _restore(self, repo: str, original: tuple[str | None, str]) -> None:
        """Put the caller's working tree and branch back exactly as found."""
        ref, sha = original
        await self._git(repo, "reset", "--hard")
        await self._git(repo, "clean", "-fd")
        args = ("checkout", ref) if ref else ("checkout", "--detach", sha)
        code, _, err = await self._git(repo, *args)
        if code != 0:
            raise RuntimeError(f"cannot return to {ref or sha}: {err}")

    async def _commit_retained(self, repo: str, branch: str) -> str:
        """Commit the verified fix on the scratch branch; return the new commit.

        Only used by ``keep_branch=True``. A branch left with the fix sitting
        uncommitted in the working tree is not retained at all: the moment the
        caller checks anything else out, the patch is gone and the branch is an
        empty copy of the base. Committing is what makes "retained for
        inspection" true, and it puts the patch on a named ref where a human can
        read it with ``git show`` before approving anything.
        """
        message = (
            f"candidate repair on {branch}: verified by a real passing test run, not applied"
        )
        for args in (("add", "-A"), ("commit", "-m", message)):
            code, out, err = await self._git(repo, *args)
            if code != 0:
                raise RuntimeError(f"cannot {' '.join(args)}: {err or out}")
        code, sha, err = await self._git(repo, "rev-parse", "HEAD")
        if code != 0:
            raise RuntimeError(f"cannot read the retained commit: {err or sha}")
        return sha.strip()

    async def _cleanup(
        self,
        repo: str,
        base_commit: str,
        branch: str,
        original_ref: tuple[str | None, str] | None = None,
    ) -> None:
        """Hand the working tree and the scratch branch back, leaving no trace.

        Used by every path that has modified the tree, on success and on failure
        alike. Three details are load-bearing and were all learned the hard way:

        * ``reset --hard`` rather than ``checkout <sha>`` — git refuses to discard
          local modifications when there is no commit to switch to, so checkout
          silently leaves the change in place.
        * ``checkout --detach`` before ``branch -D`` — git refuses to delete the
          branch that is currently checked out.
        * returning to the caller's original ref afterwards — detaching is a side effect of
          being able to drop the branch at all, so the caller must be put back on
          the branch they started from rather than left on a detached HEAD.

        Duplicating this at each call site is how the failure paths were able to
        leak a half-applied patch; there is deliberately only one copy.
        """
        await self._git(repo, "reset", "--hard", base_commit)
        await self._git(repo, "clean", "-fd")
        detach_code, _, detach_err = await self._git(repo, "checkout", "--detach", base_commit)
        if detach_code != 0:
            raise RuntimeError(f"cannot detach HEAD to clean up {branch}: {detach_err}")
        drop_code, _, drop_err = await self._git(repo, "branch", "-D", branch)
        if drop_code != 0:
            raise RuntimeError(f"cannot drop scratch branch {branch}: {drop_err}")
        if original_ref:
            await self._restore(repo, original_ref)

    async def propose(
        self,
        *,
        repo_path: str,
        base_commit: str,
        branch: str,
        candidate: CandidateFix,
        test_command: str,
        env: dict[str, str] | None = None,
        keep_branch: bool = False,
    ) -> ProposalOutcome:
        """Try a candidate fix and, only if the real test passes, produce a proposal.

        The sequence is: prove the test currently fails, branch, apply, prove the
        test now passes, and then give the working tree back.

        ``keep_branch=False`` is the default and the correct one for the
        propose-then-approve flow: Forge is proposing, not applying. Leaving a
        committed fix sitting on a branch would mean the patch had already been
        written before anyone approved it, and would collide with the gate when
        the gate creates its own repair branch. ``keep_branch=True`` is the
        deliberate opt-in for a human who wants to read the patch first: the fix
        is committed on the scratch branch, and the caller is still returned to the
        ref they started on with a clean working tree.
        """
        repo = str(Path(repo_path).resolve())
        if not (Path(repo) / ".git").exists():
            raise ValueError(f"not a git repository: {repo}")

        target = str(Path(repo) / candidate.target_file)
        if not Path(target).is_file():
            raise FileNotFoundError(candidate.target_file)

        # Recorded before the first checkout, because checking out a commit SHA
        # detaches HEAD and nothing later would put the caller back.
        original_ref = await self._original_head(repo)

        committed = await self._git(repo, "checkout", base_commit)
        if committed[0] != 0:
            raise RuntimeError(f"cannot check out {base_commit}: {committed[2] or committed[1]}")

        # 1. The test must fail before the fix, or there is nothing to repair.
        before = await self._test(repo, test_command, env=env)
        if before.passed:
            await self._restore(repo, original_ref)
            return ProposalOutcome(
                fixed=False,
                before=before,
                after=None,
                branch=branch,
                base_commit=base_commit,
                candidate=candidate,
                reason="the test already passed before the change; nothing was broken",
            )

        # 2. Branch from the pinned commit and apply the candidate.
        branched = await self._git(repo, "checkout", "-b", branch, base_commit)
        if branched[0] != 0:
            await self._restore(repo, original_ref)
            raise RuntimeError(f"cannot create branch {branch}: {branched[2] or branched[1]}")

        current = Path(target).read_text(encoding="utf-8")
        if candidate.original_snippet not in current:
            await self._cleanup(repo, base_commit, branch, original_ref)
            return ProposalOutcome(
                fixed=False,
                before=before,
                after=None,
                branch=branch,
                base_commit=base_commit,
                candidate=candidate,
                reason="the snippet to replace is not present in the file at the base commit",
            )
        if current.count(candidate.original_snippet) != 1:
            await self._cleanup(repo, base_commit, branch, original_ref)
            return ProposalOutcome(
                fixed=False,
                before=before,
                after=None,
                branch=branch,
                base_commit=base_commit,
                candidate=candidate,
                reason=(
                    f"the snippet appears {current.count(candidate.original_snippet)} times; "
                    "refusing to guess which occurrence was meant"
                ),
            )

        Path(target).write_text(
            current.replace(candidate.original_snippet, candidate.replacement_snippet, 1),
            encoding="utf-8",
        )
        # Purge the module's cached bytecode before running the test.
        #
        # Python validates a .pyc on (source mtime, source size). A repair that
        # does not change the file's length — swapping "-" for "+", say — can land
        # inside the same filesystem timestamp tick, the cache is judged valid, and
        # the test silently executes the *old* code. The result would be a repair
        # reported as verified that the test never actually exercised. Evidenced
        # here: an edit of identical length left `assert -1 == 3` failing after the
        # file on disk was already correct.
        self._purge_bytecode(repo, target)

        # 3. The same command must now pass. This is the only accepted evidence.
        after = await self._test(repo, test_command, env=env)
        if not after.passed:
            await self._cleanup(repo, base_commit, branch, original_ref)
            return ProposalOutcome(
                fixed=False,
                before=before,
                after=after,
                branch=branch,
                base_commit=base_commit,
                candidate=candidate,
                reason=(
                    f"the test still fails after the change (exit={after.returncode}); "
                    "no proposal was emitted"
                ),
            )

        # 4. The proposal is not an application. Forge has proved the fix works;
        #    the gate owns every write to a working tree from here, under an owner
        #    approval. So the working tree is restored and the scratch branch is
        #    dropped, leaving only the evidence behind.
        #
        #    `reset --hard` is required rather than `checkout <sha>`: the working
        #    tree is dirty at this point, and git refuses to discard local
        #    modifications when there is no commit to switch to. Using checkout
        #    here silently leaves the fix in place, which would mean the patch had
        #    been written before anyone approved it.
        #
        #    HEAD is detached before the branch is dropped, because git refuses to
        #    delete the branch that is currently checked out. Detaching is also
        #    safer than guessing the default branch name, which may be main or
        #    master depending on how the repository was initialised.
        if keep_branch:
            # The fix is committed on the scratch branch *and* the caller is handed
            # back their own ref with a clean tree. Leaving the caller parked on
            # the scratch branch means their next commit lands there instead of on
            # their branch, which is a worse surprise than an unfixed test.
            try:
                retained = await self._commit_retained(repo, branch)
            except RuntimeError:
                await self._cleanup(repo, base_commit, branch, original_ref)
                raise
            await self._restore(repo, original_ref)
            disposition = f"branch retained for inspection at {retained[:12]}"
        else:
            await self._cleanup(repo, base_commit, branch, original_ref)
            disposition = "branch rolled back - the gate applies"

        return ProposalOutcome(
            fixed=True,
            before=before,
            after=after,
            branch=branch,
            base_commit=base_commit,
            candidate=candidate,
            reason=f"test went from failing to passing on {branch}; {disposition}",
        )

    @staticmethod
    def _purge_bytecode(repo: str, target_file: str) -> list[str]:
        """Delete cached bytecode for the patched module. Returns what was removed."""
        removed: list[str] = []
        module = Path(target_file).stem
        for cache_dir in Path(repo).rglob("__pycache__"):
            for cached in cache_dir.glob(f"{module}.*.pyc"):
                try:
                    cached.unlink()
                    removed.append(str(cached.relative_to(repo)))
                except OSError:
                    # A cache we cannot delete is not fatal: the timestamp-based
                    # invalidation still applies to the common case, and failing
                    # the whole repair over a stale .pyc would be worse.
                    continue
        return removed

    async def current_commit(self, repo_path: str) -> str:
        code, out, err = await self._git(str(Path(repo_path).resolve()), "rev-parse", "HEAD")
        if code != 0:
            raise RuntimeError(f"cannot read HEAD: {err or out}")
        return out


def build_request(
    outcome: ProposalOutcome,
    repo_path: str,
) -> RepairProposalRequest:
    """Wire payload for the gate, carrying the real repository path."""
    return outcome.to_request(repo_path)
