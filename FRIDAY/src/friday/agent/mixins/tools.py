import json
import logging
import os
import random
import re
import subprocess
import time
import warnings
from collections.abc import Callable
from typing import Any
from urllib.parse import quote_plus
import uuid
from datetime import datetime
from friday.agent.checkpoint import TaskCheckpoint, TaskCheckpointStore
from friday.agent.cognitive import CognitiveIntelligenceEngine, CognitivePhase


from friday.agent.prompts import build_system_message
from friday.agent.state import ReasoningStateMachine, TaskState
from friday.agents.base_agent import AgentTask, BaseAgent

from friday.agents.registry import AgentRegistry

from friday.core.auth import BaseAuthorizer, DefaultSecureAuthorizer
from friday.core.config import Settings, get_settings
from friday.core.logging import get_logger
from friday.core.types import (
    AgentResponse,
    AuthorizationDecision,
    AuthorizationRequest,
    MemorySearchResult,
    Message,
    Role,
    SafetyLevel,
    ToolCall,
    ToolResult,
    TrustLevel,
)
from friday.llm.base import BaseLLMProvider
from friday.llm.factory import create_llm_provider
from friday.memory.base import BaseMemory
from friday.memory.factory import create_memory
from friday.memory.policies import should_retrieve_memory
from friday.memory.task_context import ActiveTaskContext
from friday.observability.notifications import NotificationManager
from friday.routing.capability_router import CapabilityRouter
from friday.tools.builtin import (
    AIUniverseTool,
    BrowserAutomationTool,
    CalculatorTool,
    CloseApplicationTool,
    ControlLightTool,
    ControlPlugTool,
    CreateGitBranchTool,
    CreateGitHubIssueTool,
    GoalLoopStatusTool,
    DictionaryTool,
    DraftEmailTool,
    DraftGmailTool,
    EnrollFaceIdentityTool,
    ExecuteCommandTool,
    FetchWebpageContentTool,
    FetchWebpageTool,
    FileListingTool,
    FileOperationsTool,
    FileReaderTool,
    FollowUpAddTool,
    FollowUpCompleteTool,
    FollowUpListTool,
    FindOnScreenTool,
    GetActiveAppContextTool,
    GetAIUniverseStatusTool,
    GetSystemResourcesTool,
    GetTodaysEventsTool,
    GitCommitTool,
    GitPushTool,
    GitStatusTool,
    ErrandApproveTool,
    ErrandCreateTool,
    ErrandRunTool,
    ErrandStatusTool,
    EscrcpyAutomationTool,
    EscrcpyLaunchPlanTool,
    HealthCheckTool,
    WorkflowTemplateListTool,
    WorkflowTemplateRunTool,
    LifeCalendarTool,
    LeadGenerateTool,
    KillProcessTool,
    LaptopBrowserTaskTool,
    LaptopClickTool,
    LaptopDictateTool,
    LaptopHotkeyTool,
    LaptopListDevicesTool,
    LaptopLockTool,
    LaptopMediaKeyTool,
    LaptopMediaStatusTool,
    LaptopPcCleanupTool,
    LaptopPcHealthTool,
    LaptopStorageCheckTool,
    LaptopStorageRepairTool,
    LaptopOpenAppTool,
    LaptopOpenUrlTool,
    LaptopRunCommandTool,
    LaptopScreenshotTool,
    LaptopTypeTextTool,
    LaptopDescribeScreenTool,
    SpotifyControlTool,
    LaunchApplicationTool,
    ListSkillsTool,
    ListGitHubIssuesTool,
    LocationMapsTool,
    StartGoalLoopTool,
    ManageTasksTool,
    ManageVolumeTool,
    ManageWindowsTool,
    MediaControlTool,
    MeetingFollowUpCreateTool,
    MeetingFollowUpDecideTool,
    MeetingFollowUpListTool,
    MemorySearchTool,
    NewsTool,
    OpenApplicationTool,
    OpenWebsiteTool,
    OpenWhatsAppTool,
    ProposeComputerActionTool,
    ReadActiveWindowTextTool,
    ReadGmailInboxTool,
    InboxDraftsTool,
    TriageInboxTool,
    ReadOwnCodebaseTool,
    ReadScreenTextTool,
    RememberFactTool,
    ReplaceFileContentTool,
    RunSkillTool,
    RunTestsTool,
    ScreenPredictionTool,
    ScreenSnapshotTool,
    SelfDevelopTool,
    SelfRepairTool,
    SendEmailTool,
    SendGmailTool,
    SendWhatsAppMessageTool,
    SynthesizeInformationTool,
    SystemControlTool,
    SystemInfoTool,
    FleetDispatchTool,
    FleetStatusTool,
    TaskStatusQueryTool,
    ForgeCodeTool,
    IntelXResearchTool,
    JobHuntPrepTool,
    JobHuntScanTool,
    JobHuntShortlistTool,
    LocalBusinessTool,
    StratexPortfolioTool,
    SentinelSecurityTool,
    FuturisForecastTool,
    WebFetchSummarizeTool,
    VyralXProjectTool,
    VyralXRenderTool,
    VyralXPublishTool,
    SystemPowerControlTool,
    TimeDateTool,
    ToggleBluetoothTool,
    ToggleDarkModeTool,
    ToggleWifiTool,
    TypeTextTool,
    VerifyFaceIdentityTool,
    WeatherTool,
    WebSearchTool,
    WikipediaTool,
    WriteCodeFileTool,
    YouTubeTool,
)
from friday.tools.base import BaseTool
from friday.tools.registry import ToolRegistry
from friday.vision.actions import ActionType
from friday.vision.computer_control import ComputerActionExecutor
from friday.vision.detector import DeterministicActionDetector
from friday.vision.intent_detector import ActionIntent, IntentDetector
from friday.vision.windows_input_driver import (
    WindowsNativeInputDriver,
    check_desktop_interactivity,
)


logger = logging.getLogger(__name__)

class ToolExecutionMixin:
    def _create_default_registry(self) -> ToolRegistry:
            """Instantiate default tool registry with built-in safe tools."""
            registry = ToolRegistry()
            registry.register(SystemInfoTool())
            registry.register(FleetStatusTool())
            registry.register(FleetDispatchTool())
            registry.register(TaskStatusQueryTool())
            registry.register(ForgeCodeTool())
            registry.register(IntelXResearchTool())
            # TASK-IG-FRD-003: job-hunt workflow (scan/score/prep; drafts only).
            registry.register(JobHuntScanTool())
            registry.register(JobHuntShortlistTool())
            registry.register(JobHuntPrepTool())
            # IG F-30/F-35: local-business patterns — prospect qualification
            # plus website-generation and appointment-agent prompt building
            # (generation only, no outreach). Registered at creation, per
            # the AUDIT-2 wiring lesson: export-only is not implemented.
            registry.register(LocalBusinessTool())
            registry.register(StratexPortfolioTool())
            registry.register(SentinelSecurityTool())
            registry.register(FuturisForecastTool())
            registry.register(WebFetchSummarizeTool())
            registry.register(VyralXProjectTool())
            registry.register(VyralXRenderTool())
            registry.register(VyralXPublishTool())
            registry.register(TimeDateTool())
            registry.register(CalculatorTool())
            registry.register(FileReaderTool())
            # TASK-IG-FRD-002: persistent owner follow-ups (never dropped).
            registry.register(FollowUpAddTool())
            registry.register(FollowUpListTool())
            registry.register(FollowUpCompleteTool())
            registry.register(FileListingTool())
            registry.register(MemorySearchTool(self.memory))
            registry.register(ScreenSnapshotTool())
            registry.register(ProposeComputerActionTool(autonomous=False))
            registry.register(OpenApplicationTool())
            registry.register(TypeTextTool())
            registry.register(CloseApplicationTool())
            registry.register(ManageVolumeTool())
            registry.register(SystemPowerControlTool())
            registry.register(ManageWindowsTool())
            registry.register(WebSearchTool())
            registry.register(FetchWebpageTool())
            registry.register(BrowserAutomationTool())
            registry.register(FileOperationsTool())
            registry.register(ExecuteCommandTool())
            registry.register(ReadScreenTextTool())
            registry.register(FindOnScreenTool())
            registry.register(GetActiveAppContextTool())
            registry.register(ReadActiveWindowTextTool())
            registry.register(GitStatusTool())
            registry.register(GitCommitTool())
            registry.register(GitPushTool())
            registry.register(ListGitHubIssuesTool())
            registry.register(CreateGitHubIssueTool())
            registry.register(GetSystemResourcesTool())
            registry.register(KillProcessTool())
            registry.register(LaunchApplicationTool())
            # TASK-LAP-001: the owner's own laptop, via the reverse tunnel.
            registry.register(LaptopListDevicesTool())
            registry.register(LaptopOpenAppTool())
            registry.register(LaptopOpenUrlTool())
            registry.register(LaptopScreenshotTool())
            # TASK-IG-FRD-008: vision-model description of the laptop screen.
            registry.register(LaptopDescribeScreenTool())
            registry.register(LaptopTypeTextTool())
            registry.register(LaptopDictateTool())
            registry.register(LaptopPcHealthTool())
            registry.register(LaptopPcCleanupTool())
            registry.register(LaptopHotkeyTool())
            registry.register(LaptopStorageCheckTool())
            registry.register(LaptopStorageRepairTool())
            registry.register(LaptopBrowserTaskTool())
            registry.register(LaptopClickTool())
            registry.register(LaptopRunCommandTool())
            # TASK-IG-FRD-010: lock the laptop screen (no unlock, by design).
            registry.register(LaptopLockTool())
            # TASK-FRD-044: Spotify playback control by voice — media keys
            # plus the session read-back that proves playback changed.
            registry.register(LaptopMediaKeyTool())
            registry.register(LaptopMediaStatusTool())
            registry.register(SpotifyControlTool())
            # TASK-IG2-LAP-01: Escrcpy integration — launch plans and phone
            # automation over the scrcpy/ADB transport. Registered
            # 2026-11-16 (IG implementation wave): the tools were exported
            # from tools/builtin but never reached the live registry.
            registry.register(EscrcpyLaunchPlanTool())
            registry.register(EscrcpyAutomationTool())
            registry.register(SystemControlTool())
            registry.register(HealthCheckTool())
            # TASK-IG-FRD-001: goal-loop autonomy (goal + criteria, worked in cycles).
            registry.register(StartGoalLoopTool())
            registry.register(GoalLoopStatusTool())
            # TASK-IG-FRD-004: delegated errands — framework only, approval-gated, dry-run.
            registry.register(ErrandCreateTool())
            registry.register(ErrandStatusTool())
            registry.register(ErrandApproveTool())
            registry.register(ErrandRunTool())
            # TASK-IG2-FRD-03: delegated lead generation — scrape a business
            # directory page into a deduplicated contact table; the table is
            # the deliverable (no outreach, no dialling). Registered
            # 2026-11-16 (IG implementation wave) — previously export-only.
            registry.register(LeadGenerateTool())
            # TASK-IG-FRD-005: ready-made workflow templates.
            registry.register(WorkflowTemplateListTool())
            registry.register(WorkflowTemplateRunTool())
            # TASK-IG-FRD-009: life-in-weeks dot-grid calendar computation.
            registry.register(LifeCalendarTool())
            # TASK-IG2-FRD-04: post-meeting follow-up automation — turn
            # meeting notes into tracked follow-ups and decide them.
            # Registered 2026-11-16 (IG implementation wave) — previously
            # export-only.
            registry.register(MeetingFollowUpCreateTool())
            registry.register(MeetingFollowUpListTool())
            registry.register(MeetingFollowUpDecideTool())
            registry.register(WriteCodeFileTool())
            registry.register(ReplaceFileContentTool())
            registry.register(RunTestsTool())
            registry.register(CreateGitBranchTool())
            registry.register(ControlLightTool())
            registry.register(ControlPlugTool())
            registry.register(FetchWebpageContentTool())
            registry.register(SynthesizeInformationTool())
            registry.register(ToggleDarkModeTool())
            registry.register(ToggleBluetoothTool())
            registry.register(ToggleWifiTool())
            registry.register(GetTodaysEventsTool())
            registry.register(SendEmailTool())
            registry.register(DraftEmailTool())
            registry.register(ReadGmailInboxTool())
            registry.register(DraftGmailTool())
            registry.register(SendGmailTool())
            registry.register(TriageInboxTool())
            registry.register(InboxDraftsTool())
            registry.register(SendWhatsAppMessageTool())
            registry.register(OpenWhatsAppTool())
            registry.register(ReadOwnCodebaseTool())
            registry.register(AIUniverseTool(memory=self.memory))
            registry.register(WeatherTool())
            registry.register(NewsTool())
            registry.register(ManageTasksTool())
            registry.register(OpenWebsiteTool())
            registry.register(YouTubeTool())
            registry.register(LocationMapsTool())
            registry.register(WikipediaTool())
            registry.register(DictionaryTool())
            registry.register(MediaControlTool())
            registry.register(RememberFactTool(memory=self.memory))
            registry.register(VerifyFaceIdentityTool())
            registry.register(EnrollFaceIdentityTool())
            
            # FRIDAY Android Control Tools
            try:
                from friday.tools.builtin.android_control import (
                    AndroidDeviceInfoTool,
                    AndroidKeyEventTool,
                    OpenAndroidAppTool,
                    SwipeScreenTool,
                    TapScreenTool,
                    TypeTextTool as AndroidTypeTextTool,
                )
                registry.register(TapScreenTool())
                registry.register(SwipeScreenTool())
                registry.register(OpenAndroidAppTool())
                registry.register(AndroidTypeTextTool())
                registry.register(AndroidKeyEventTool())
                registry.register(AndroidDeviceInfoTool())
            except ImportError:
                pass
            # FRIDAY Phone Control Tools (TASK-PHONE-001): the owner's phone
            # over the reverse tunnel in friday.remote.phone_bridge. Separate
            # from the ADB tools above — those need a phone plugged into this
            # machine; these reach the phone in the owner's hand.
            try:
                from friday.tools.builtin.phone_control import (
                    PhoneCloseAppTool,
                    PhoneFindMyPhoneTool,
                    PhoneMakeCallTool,
                    PhoneMediaControlTool,
                    PhoneOpenAppTool,
                    PhoneOpenUrlTool,
                    PhonePressKeyTool,
                    PhoneReadNotificationsTool,
                    PhoneScreenshotTool,
                    PhoneSendSmsTool,
                    PhoneSendWhatsAppTool,
                    PhoneSetAlarmTool,
                    PhoneSetVolumeTool,
                    PhoneStatusTool,
                    PhoneSwipeTool,
                    PhoneTapTool,
                    PhoneTypeTextTool,
                )
                from friday.tools.builtin.phone_ui_control import (
                    PhoneUiDumpTool,
                    PhoneUiTaskTool,
                )
                registry.register(PhoneStatusTool())
                registry.register(PhoneOpenAppTool())
                registry.register(PhoneCloseAppTool())
                registry.register(PhoneOpenUrlTool())
                registry.register(PhoneMakeCallTool())
                registry.register(PhoneSendSmsTool())
                registry.register(PhoneSendWhatsAppTool())
                registry.register(PhoneReadNotificationsTool())
                registry.register(PhoneSetAlarmTool())
                registry.register(PhoneMediaControlTool())
                registry.register(PhoneSetVolumeTool())
                registry.register(PhoneFindMyPhoneTool())
                registry.register(PhoneTapTool())
                registry.register(PhoneSwipeTool())
                registry.register(PhoneTypeTextTool())
                registry.register(PhonePressKeyTool())
                registry.register(PhoneScreenshotTool())
                # TASK-IG-LAP-01: natural-language UI automation surfaces.
                registry.register(PhoneUiDumpTool())
                registry.register(PhoneUiTaskTool())
            except ImportError:
                pass
            # The skill layer (24 registered skills) had no caller in the running
            # agent: `FridayAgent.skill_registry` was a lazy property nothing read,
            # so every skill was unreachable in production while its unit tests
            # passed by calling `execute` directly. These two tools are the bridge.
            _skill_registry = getattr(self, "skill_registry", None)
            registry.register(ListSkillsTool(skill_registry=_skill_registry))
            registry.register(
                RunSkillTool(
                    skill_registry=_skill_registry,
                    authorizer=getattr(self, "authorizer", None),
                    tool_registry=registry,
                    llm_provider=getattr(self, "llm_provider", None) or getattr(self, "provider", None),
                )
            )
            registry.register(GetAIUniverseStatusTool())
            registry.register(ScreenPredictionTool())
            # BUG-003: the system prompt tells the model to use these two by name.
            # They must be in the registry the model's schemas come from, or the
            # instruction produces a phantom tool call and FRIDAY appears to refuse.
            registry.register(SelfDevelopTool())
            registry.register(SelfRepairTool())
            return registry

    def _init_default_agent_registry(self) -> AgentRegistry:
            """Instantiate default specialist agent pool for Multi-Agent Specialist Architecture."""
            from friday.agents.specialists.developer_agent import DeveloperAgent
            from friday.agents.specialists.research_agent import ResearchAgent
            from friday.agents.specialists.self_dev_agent import SelfDevAgent
            reg = AgentRegistry()
            reg.register_agent(
                DeveloperAgent(
                    agent_id="developer_01",
                    role="developer",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                )
            )
            reg.register_agent(
                SelfDevAgent(
                    agent_id="self_developer_01",
                    role="self_developer",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                )
            )
            reg.register_agent(
                ResearchAgent(
                    agent_id="researcher_01",
                    role="researcher",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                )
            )
            reg.register_agent(
                BaseAgent(
                    agent_id="system_controller_01",
                    role="system_controller",
                    instructions="Manage desktop windows, open and close apps, adjust volume, launch commands, and control system state.",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                    allowed_tools=[
                        "open_application",
                        "launch_application",
                        "close_application",
                        "manage_windows",
                        "manage_volume",
                        "system_control",
                        "health_check",
                        "type_text",
                    ],
                )
            )
            reg.register_agent(
                BaseAgent(
                    agent_id="coder_01",
                    role="coder",
                    instructions="Inspect codebase, manipulate files, parse code structures, and run test/build commands.",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                    allowed_tools=["read_file", "list_files", "file_operations", "execute_command", "calculator"],
                )
            )
            reg.register_agent(
                BaseAgent(
                    agent_id="general_01",
                    role="general",
                    instructions="General purpose reasoning, conversation, and fallback execution.",
                    llm_provider=self.llm,
                    tool_registry=self.tools,
                )
            )
            return reg

    async def _execute_via_specialist_agents(self, goal: str, decomposition) -> str:
            """Orchestrate execution across multiple specialist agents and return synthesized outcome."""
            subtask_summaries: list[str] = []
            for idx, subtask in enumerate(decomposition.subtasks):
                decision = self.agent_router.route_subtask(subtask)
                agent = decision.selected_agent
                logger.info(
                    f"[MULTI-AGENT] Routing subtask '{subtask.title}' to specialist '{agent.role}' "
                    f"(Score: {decision.score}, Reason: {decision.rationale})"
                )
                task_obj = AgentTask(
                    goal=f"{subtask.title}: {subtask.description}",
                    subtask_index=idx,
                    total_subtasks=len(decomposition.subtasks),
                )
                result = await agent.execute_task(task_obj)
                subtask_summaries.append(f"- **{subtask.title}** ({agent.role}): {result.output.strip()}")

            synthesized = (
                f"Completed complex workflow via {len(decomposition.subtasks)} specialist agents:\n\n"
                + "\n".join(subtask_summaries)
            )
            return synthesized

    def _effective_tool_timeout(self, tool: Any | None, timeout: float | None = None) -> float:
        """Timeout for one tool call: explicit > tool-declared > agent default.

        TASK-IG-FRD-006-FIX-01: the agent used to pass its own default (30s)
        explicitly for every call, which shadowed the per-tool timeout in the
        registry — intelx_research declares 125s but was killed at 30.0s on
        FRIDAY-Server while its IntelX dispatch was still in flight. A tool
        timeout equal to BaseTool's class default (30) carries no override,
        so only a value different from the default counts as declared.
        """
        if timeout is not None:
            return float(timeout)
        declared = getattr(tool, "timeout", None)
        if declared:
            try:
                if float(declared) != float(BaseTool.timeout):
                    return float(declared)
            except (TypeError, ValueError):
                pass
        return float(self.tool_timeout)

    def _execute_single_tool_call_internal(self, tc: ToolCall, timeout: float | None = None) -> ToolResult:
            """Internal helper handling validation, authorization, and execution of a single tool call."""
            # Replay prevention within turn
            operation_signature = json.dumps(
                [tc.name, tc.arguments], sort_keys=True, separators=(",", ":"), default=str
            )
            with self._tool_replay_lock:
                if tc.id in self._processed_tool_ids:
                    return ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Error: Duplicate tool call ID '{tc.id}' ignored.",
                        is_error=True,
                        safety_level=SafetyLevel.SAFE,
                    )
                self._processed_tool_ids.add(tc.id)
                if operation_signature in self._processed_tool_signatures:
                    return ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=(
                            f"Error: Repeated tool operation '{tc.name}' with the same arguments "
                            "was not executed again in this request. Use the previous result."
                        ),
                        is_error=True,
                        safety_level=SafetyLevel.SAFE,
                    )
                self._processed_tool_signatures.add(operation_signature)

            tool = self.tools.get(tc.name)
            if not tool:
                err_msg = f"Error: Tool '{tc.name}' is not registered or available in FRIDAY's tool registry."
                logger.warning(err_msg)
                return ToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=err_msg,
                    is_error=True,
                    safety_level=SafetyLevel.SAFE,
                )

            # 1. Validation happens BEFORE authorization request
            is_valid, validation_err = tool.validate_arguments(tc.arguments)
            if not is_valid:
                err_msg = f"Invalid arguments for tool '{tc.name}': {validation_err}"
                logger.warning(err_msg)
                return ToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=err_msg,
                    is_error=True,
                    safety_level=tool.safety_level,
                )

            # 2. Extract affected resource (e.g. file paths) if present
            affected_res = tc.arguments.get("path") or tc.arguments.get("file_path") or tc.arguments.get("directory")
            if affected_res:
                affected_res = str(affected_res)

            auth_req = AuthorizationRequest(
                tool_name=tc.name,
                safety_level=tool.safety_level,
                arguments=tc.arguments,
                tool_call_id=tc.id,
                purpose=tool.description,
                affected_resource=affected_res,
            )

            # 3. Handle authorization check
            logger.info(f"Requesting authorization for tool '{tc.name}' [Safety: {tool.safety_level.value}]")
            auth_resp = self.authorizer.authorize(auth_req)

            logger.info(
                f"Authorization outcome for tool '{tc.name}': {auth_resp.decision.value} "
                f"(Reason: {auth_resp.reason})"
            )

            # 4. Execution happens ONLY after explicit authorization capability
            # TASK-IG-FRD-006-FIX-01: honor the tool's declared timeout
            # (e.g. intelx_research: 125s) instead of always passing the
            # agent default, which shadowed it in the registry.
            effective_timeout = self._effective_tool_timeout(tool, timeout)
            if auth_resp.decision == AuthorizationDecision.APPROVED:
                return self.tools.execute(
                    name=tc.name,
                    arguments=tc.arguments,
                    tool_call_id=tc.id,
                    authorization=auth_resp.capability,
                    timeout=effective_timeout,
                )
            
            err_msg = (
                f"Authorization Block: Execution of tool '{tc.name}' was {auth_resp.decision.value}. "
                f"Reason: {auth_resp.reason}"
            )
            return ToolResult(
                tool_call_id=tc.id,
                name=tc.name,
                content=err_msg,
                is_error=True,
                safety_level=tool.safety_level,
                metadata={"authorization": auth_resp.decision.value},
                refused=True,
            )

    def _execute_single_tool_call(self, tc: ToolCall, timeout: float | None = None) -> ToolResult:
            """Validate, authorize, and execute a single tool call request with duration logging."""
            tool_start = time.perf_counter()
            result = self._execute_single_tool_call_internal(tc, timeout=timeout)
            tool_duration = time.perf_counter() - tool_start
            logger.info(
                f"Tool '{tc.name}' execution completed in {tool_duration:.4f}s "
                f"(Success: {not result.is_error})"
            )
            # Automatic Experience Learning & Self-Upgrading into Memora
            # TASK-MEM-029: report_task_outcome_async fans the same event
            # out to the skill-learning loop as well (pattern = tool name).
            try:
                from friday.memory.memora_client import memora_client
                if result.is_error:
                    memora_client.report_task_outcome_async(
                        agent_name="friday",
                        task_name=tc.name,
                        status="failure",
                        error_log=str(result.content),
                        actions_taken=f"tool_arguments:{str(tc.arguments)[:200]}",
                        domain="tool_execution"
                    )
            except Exception as e:
                logger.debug(f"Memora tool outcome learning skipped: {e}")

            return result

    def _execute_single_tool_call_with_timeout(
            self, tc: ToolCall, timeout: float | None = None
        ) -> ToolResult:
            """Execute a single tool call through ToolRegistry's shared worker pool and timeout mechanism.

            A None timeout honors the tool's declared timeout (or the agent
            default); an explicit value still overrides it.
            """
            return self._execute_single_tool_call(tc, timeout=timeout)

