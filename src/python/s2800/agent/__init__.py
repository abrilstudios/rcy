"""S2800/S3000/S3200 SysEx Expert Agent.

Structured specification data and tool functions for querying the Akai
S2800/S3000/S3200 MIDI System Exclusive protocol.

Usage:
    tools/bin/s2800-agent param FILFRQ
    tools/bin/s2800-agent offset keygroup 34
    tools/bin/s2800-agent list program
    tools/bin/s2800-agent models
"""

from s2800.agent.agent import agent

__all__ = ["agent"]
