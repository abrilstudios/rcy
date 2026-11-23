"""S2800/S3000/S3200 SysEx Expert Agent.

Structured specification data and tool functions for querying the Akai
S2800/S3000/S3200 MIDI System Exclusive protocol.

Usage:
    tools/bin/s2800-agent param FILFRQ
    tools/bin/s2800-agent offset keygroup 34
    tools/bin/s2800-agent list program
    tools/bin/s2800-agent models

The ADK ``agent`` object is resolved on first access so that the spec and
device tools work without google-adk installed.
"""

__all__ = ["agent"]


def __getattr__(name: str):
    if name == "agent":
        from s2800.agent.agent import agent
        return agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
