"""Google Docs delivery via an MCP-host-provided command bridge."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.config import PROJECT_ROOT, Settings
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeliveryResult:
    mode: str
    status: str
    document_id: str | None
    document_url: str | None
    message: str


def _save_local_preview(title: str, markdown: str) -> DeliveryResult:
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = title.lower().replace(" ", "_").replace("/", "-")
    preview_path = out_dir / f"{safe_name}.md"
    preview_path.write_text(markdown, encoding="utf-8")
    return DeliveryResult(
        mode="dry_run",
        status="saved_locally",
        document_id="local-preview",
        document_url=str(preview_path),
        message="Saved local preview because Docs MCP command is not configured.",
    )


def deliver_weekly_pulse(
    *,
    title: str,
    markdown: str,
    settings: Settings,
    dry_run: bool,
) -> DeliveryResult:
    command = settings.pulse_docs_mcp_command.strip()
    if dry_run or not command:
        return _save_local_preview(title, markdown)

    payload = {"title": title, "markdown": markdown}
    logger.info("Delivering weekly pulse through Docs MCP command bridge.")

    try:
        proc = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=settings.pulse_docs_timeout_seconds,
            shell=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return DeliveryResult(
            mode="mcp_command",
            status="timeout",
            document_id=None,
            document_url=None,
            message=f"Docs MCP command timed out: {exc}",
        )

    if proc.returncode != 0:
        return DeliveryResult(
            mode="mcp_command",
            status="failed",
            document_id=None,
            document_url=None,
            message=(proc.stderr or proc.stdout or "Docs MCP command failed").strip(),
        )

    try:
        data = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return DeliveryResult(
            mode="mcp_command",
            status="failed",
            document_id=None,
            document_url=None,
            message="Docs MCP command did not return valid JSON.",
        )

    return DeliveryResult(
        mode="mcp_command",
        status="delivered",
        document_id=data.get("document_id"),
        document_url=data.get("url"),
        message=data.get("message", "Weekly pulse delivered to Docs MCP."),
    )
