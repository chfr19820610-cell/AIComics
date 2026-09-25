"""Director Agent — central orchestrator for multi-agent animation pipeline.

Replaces the fixed pipeline with a Director Agent that delegates to
specialized sub-agents:

  Script Agent → Storyboard Agent → Character Agent → Video Agent
       → Quality Agent → Editor Agent → Publish Agent

Each agent is a callable that receives context and returns results.
The Director coordinates them, handles failures, and retries.

Usage:
    director = DirectorAgent()
    result = director.produce_episode(
        story="少年踏上修仙之路...",
        episode_code="E01",
        genre="cultivation",
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentResult:
    """Result from a single agent execution."""

    agent_name: str
    status: str  # success / failed / skipped
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class EpisodeProductionResult:
    """Final result of a full episode production."""

    episode_code: str
    success: bool
    agent_results: list[AgentResult] = field(default_factory=list)
    final_video_path: str = ""
    total_duration_seconds: float = 0.0
    quality_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_code": self.episode_code,
            "success": self.success,
            "agent_results": [r.to_dict() for r in self.agent_results],
            "final_video_path": self.final_video_path,
            "total_duration_seconds": self.total_duration_seconds,
            "quality_score": self.quality_score,
        }


class DirectorAgent:
    """Central orchestrator for the multi-agent animation pipeline.

    The Director doesn't do creative work itself — it delegates to
    specialized agents and coordinates the workflow.

    Args:
        agents: Optional dict of agent_name → callable. Defaults to
            built-in agents.
        max_retries: Max retries per agent on failure.
    """

    AGENT_PIPELINE = [
        "script",
        "storyboard",
        "character",
        "video",
        "quality",
        "editor",
        "publish",
    ]

    def __init__(
        self,
        agents: dict[str, Callable[..., AgentResult]] | None = None,
        max_retries: int = 2,
    ) -> None:
        self.max_retries = max_retries
        self._agents: dict[str, Callable[..., AgentResult]] = agents or {}
        self._execution_log: list[AgentResult] = []

    def register_agent(self, name: str, agent_fn: Callable[..., AgentResult]) -> None:
        """Register a specialized agent."""
        self._agents[name] = agent_fn

    def execute_agent(
        self,
        agent_name: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Execute a single agent with retry logic.

        Args:
            agent_name: Name of the agent to execute.
            context: Context dict passed to the agent.

        Returns:
            AgentResult from the agent execution.
        """
        agent_fn = self._agents.get(agent_name)
        if agent_fn is None:
            return AgentResult(
                agent_name=agent_name,
                status="skipped",
                error=f"Agent '{agent_name}' not registered",
            )

        for attempt in range(self.max_retries + 1):
            try:
                result = agent_fn(context=context, **context)
                if result.status == "success":
                    return result
                if attempt < self.max_retries:
                    continue  # retry
                return result
            except Exception as exc:
                if attempt < self.max_retries:
                    continue
                return AgentResult(
                    agent_name=agent_name,
                    status="failed",
                    error=str(exc),
                )

        return AgentResult(agent_name=agent_name, status="failed", error="Max retries exceeded")

    def produce_episode(
        self,
        story: str,
        episode_code: str = "E01",
        genre: str = "cultivation",
        **kwargs: Any,
    ) -> EpisodeProductionResult:
        """Run the full agent pipeline to produce an episode.

        Args:
            story: Story text/outline.
            episode_code: Episode identifier.
            genre: Genre for style guidance.
            **kwargs: Additional context passed to all agents.

        Returns:
            EpisodeProductionResult with full agent history.
        """
        import time

        results: list[AgentResult] = []
        context: dict[str, Any] = {
            "story": story,
            "episode_code": episode_code,
            "genre": genre,
            **kwargs,
        }

        success = True

        for agent_name in self.AGENT_PIPELINE:
            start = time.time()
            result = self.execute_agent(agent_name, context)
            result.duration_seconds = time.time() - start
            results.append(result)

            # Update context with agent output
            if result.status == "success":
                context.update(result.output)
            else:
                success = False
                # Non-critical agents (quality, publish) don't halt pipeline
                if agent_name in ("script", "storyboard", "character", "video", "editor"):
                    break

        return EpisodeProductionResult(
            episode_code=episode_code,
            success=success,
            agent_results=results,
            final_video_path=context.get("final_video_path", ""),
            total_duration_seconds=sum(r.duration_seconds for r in results),
            quality_score=context.get("quality_score", 0),
        )

    def get_pipeline_status(self) -> dict[str, Any]:
        """Get the current pipeline configuration status."""
        return {
            "registered_agents": list(self._agents.keys()),
            "pipeline": self.AGENT_PIPELINE,
            "missing_agents": [
                a for a in self.AGENT_PIPELINE if a not in self._agents
            ],
            "max_retries": self.max_retries,
        }

    def get_execution_log(self) -> list[AgentResult]:
        """Get the log of all agent executions."""
        return list(self._execution_log)
