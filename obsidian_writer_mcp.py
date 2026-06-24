import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from fastmcp import FastMCP


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        os.environ[key] = value


load_env_file(Path(__file__).with_name(".env"))
load_env_file(Path.cwd() / ".env")

OBSIDIAN_WRITER_BASE_URL = os.getenv(
    "OBSIDIAN_WRITER_BASE_URL",
    "http://obsidian-writer:3000",
)
OBSIDIAN_DEFAULT_VAULT = os.getenv("OBSIDIAN_DEFAULT_VAULT", "default")

mcp = FastMCP("obsidian-writer")


async def get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{OBSIDIAN_WRITER_BASE_URL}{path}")
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            return {
                "ok": False,
                "status": response.status_code,
                "error": data,
            }

        return {
            "ok": True,
            "status": response.status_code,
            "response": data,
        }


async def post(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{OBSIDIAN_WRITER_BASE_URL}{path}",
            json=payload,
        )
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            return {
                "ok": False,
                "status": response.status_code,
                "error": data,
            }

        return {
            "ok": True,
            "status": response.status_code,
            "response": data,
        }


@mcp.tool()
async def obsidian_append_inbox(
    line: str,
    tags: list[str] | None = None,
    timestamp: int | None = None,
) -> dict:
    """
    Append one line to today's inbox file in the user's Obsidian vault.
    Use when the user asks to add/save/capture something to inbox.
    """
    payload = {
        "vault": OBSIDIAN_DEFAULT_VAULT,
        "line": line,
        "tags": tags or ["hermes"],
    }
    if timestamp is not None:
        payload["timestamp"] = timestamp
    return await post("/inbox", payload)


@mcp.tool()
async def obsidian_list_lists() -> dict:
    """
    List existing Obsidian lists in the configured default vault.
    Use before adding/removing/updating list items when the user gives an
    approximate list name. Prefer an existing compatible list to avoid creating
    duplicates such as mercado, compras, or lista-de-compras.
    """
    vault = quote(OBSIDIAN_DEFAULT_VAULT, safe="")
    return await get(f"/lists?vault={vault}")


@mcp.tool()
async def obsidian_list_add(
    list_name: str,
    items: list[str],
) -> dict:
    """
    Add one or more unchecked items to an Obsidian list in the configured default vault.
    Use when the user asks to add items to a named list. Before using this tool,
    call obsidian_list_lists when there is doubt about the exact list name.
    """
    return await post(
        "/lists",
        {
            "vault": OBSIDIAN_DEFAULT_VAULT,
            "list": list_name,
            "operation": "add",
            "items": items,
        },
    )


@mcp.tool()
async def obsidian_list_remove(
    list_name: str,
    items: list[str],
) -> dict:
    """
    Remove one or more items from an Obsidian list in the configured default vault.
    Use when the user asks to remove items from a named list. Before using this
    tool, call obsidian_list_lists when there is doubt about the exact list name.
    """
    return await post(
        "/lists",
        {
            "vault": OBSIDIAN_DEFAULT_VAULT,
            "list": list_name,
            "operation": "remove",
            "items": items,
        },
    )


@mcp.tool()
async def obsidian_list_update(
    list_name: str,
    old_items: list[str],
    new_items: list[str],
) -> dict:
    """
    Update list items in an Obsidian list in the configured default vault.
    Use when the user asks to rename/change existing list items. Before using
    this tool, call obsidian_list_lists when there is doubt about the exact list
    name.
    """
    return await post(
        "/lists",
        {
            "vault": OBSIDIAN_DEFAULT_VAULT,
            "list": list_name,
            "operation": "update",
            "old_items": old_items,
            "new_items": new_items,
        },
    )


@mcp.tool()
async def obsidian_list_notes() -> dict:
    """
    List existing notes in the configured default vault.
    Use before creating or updating a note when the user mentions a note by an
    approximate name. Prefer an existing compatible note instead of creating a
    duplicate.
    """
    vault = quote(OBSIDIAN_DEFAULT_VAULT, safe="")
    return await get(f"/notes?vault={vault}")


@mcp.tool()
async def obsidian_read_note(slug: str) -> dict:
    """
    Read an existing note from the configured default vault.
    Use before appending to a note or answering about its content. Use the slug
    returned by obsidian_list_notes.
    """
    vault = quote(OBSIDIAN_DEFAULT_VAULT, safe="")
    escaped_slug = quote(slug, safe="")
    return await get(f"/notes/{escaped_slug}?vault={vault}")


@mcp.tool()
async def obsidian_create_note(
    title: str,
    content: str,
) -> dict:
    """
    Create a new standalone Markdown note in the configured default vault.
    Use when the user asks to create a new note. mode=create always creates a
    new note; if the same slug already exists, obsidian-writer creates _2, _3,
    etc. Content should be well-formatted Markdown. Do not repeat the title as
    a heading inside content when title is already provided separately.
    """
    return await post(
        "/notes",
        {
            "vault": OBSIDIAN_DEFAULT_VAULT,
            "title": title,
            "content": content,
            "mode": "create",
            "source": "hermes",
        },
    )


@mcp.tool()
async def obsidian_append_note(
    slug: str,
    content: str,
) -> dict:
    """
    Append Markdown content to an existing note in the configured default vault.
    Use when the user asks to add content to an existing note. Before using,
    prefer calling obsidian_list_notes to discover the correct slug. If needed,
    use obsidian_read_note to understand the note before adding content.
    """
    return await post(
        "/notes",
        {
            "vault": OBSIDIAN_DEFAULT_VAULT,
            "slug": slug,
            "content": content,
            "mode": "append",
            "source": "hermes",
        },
    )


@mcp.tool()
async def obsidian_create_or_append_note(
    title: str,
    content: str,
    slug: str | None = None,
) -> dict:
    """
    Create a note or append to an existing compatible note in the configured default vault.
    Use for ambiguous requests like "put this in note X" or "save this in a note
    about X". If a compatible note exists, use its slug and append. If not, let
    obsidian-writer create the note. Before using, prefer calling
    obsidian_list_notes.
    """
    payload = {
        "vault": OBSIDIAN_DEFAULT_VAULT,
        "title": title,
        "content": content,
        "mode": "create_or_append",
        "source": "hermes",
    }
    if slug is not None:
        payload["slug"] = slug
    return await post("/notes", payload)


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_TASK_STATUSES = {"todo", "done", "cancelled"}
VALID_TASK_LIST_STATUSES = {"todo", "done", "cancelled", "all"}
VALID_TASK_PRIORITIES = {"highest", "high", "medium", "low", "lowest", "none"}


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return len(value) > 0
    return True


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validation_error(message: str) -> dict:
    return {
        "ok": False,
        "error": message,
    }


def _clean_task_http_result(result: dict) -> dict:
    if result.get("ok") is True and isinstance(result.get("response"), dict):
        return result["response"]

    if result.get("ok") is False:
        error = result.get("error")
        if isinstance(error, dict):
            error = error.get("error") or error.get("message") or error
        cleaned = {
            "ok": False,
            "error": error or "obsidian-writer request failed",
        }
        if "status" in result:
            cleaned["status"] = result["status"]
        return cleaned

    return result


@mcp.tool()
async def obsidian_list_tasks(
    status: str | None = "todo",
    limit: int | None = None,
    vault: str | None = None,
) -> dict:
    """
    List structured Obsidian Tasks-compatible tasks from a vault.
    Use when the user asks what tasks/todos/reminders are pending, completed,
    cancelled, or all. By default lists pending todo tasks from the configured default vault.
    """
    normalized_status = _clean_string(status) or "todo"
    if normalized_status not in VALID_TASK_LIST_STATUSES:
        return _validation_error(
            "Invalid status: expected one of todo, done, cancelled, all"
        )

    if limit is not None and limit < 1:
        return _validation_error("Invalid limit: expected a positive integer")

    params = {
        "vault": _clean_string(vault) or OBSIDIAN_DEFAULT_VAULT,
        "status": normalized_status,
    }
    if limit is not None:
        params["limit"] = str(limit)

    query = "&".join(
        f"{quote(str(key), safe='')}={quote(str(value), safe='')}"
        for key, value in params.items()
    )
    return _clean_task_http_result(await get(f"/tasks?{query}"))


@mcp.tool()
async def obsidian_create_task(
    title: str | None = None,
    vault: str | None = None,
    content: str | None = None,
    status: str | None = None,
    due: str | None = None,
    scheduled: str | None = None,
    start: str | None = None,
    done: str | None = None,
    cancelled: str | None = None,
    priority: str | None = None,
    recurrence: str | None = None,
    tags: list[str] | None = None,
    source: str | None = "hermes",
    due_text: str | None = None,
    depends_on: str | list[str] | None = None,
) -> dict:
    """
    Create a structured Obsidian Tasks-compatible task in a vault.
    Use when the user asks for a task, todo, manual reminder, or pending action.
    Pass semantic fields only; obsidian-writer formats the final Markdown line.
    Dependencies are accepted for future compatibility but are not sent yet.
    """
    task_title = _clean_string(title) or _clean_string(content)
    if task_title is None:
        return _validation_error("title or content is required")

    if re.match(r"^\s*- \[[ xX-]\]", task_title):
        return _validation_error(
            "Provide structured task fields instead of raw Markdown task syntax"
        )

    normalized_status = _clean_string(status)
    if normalized_status is not None and normalized_status not in VALID_TASK_STATUSES:
        return _validation_error(
            "Invalid status: expected one of todo, done, cancelled"
        )

    normalized_priority = _clean_string(priority)
    if normalized_priority is not None and normalized_priority not in VALID_TASK_PRIORITIES:
        return _validation_error(
            "Invalid priority: expected one of highest, high, medium, low, lowest, none"
        )

    date_values = {
        "due": _clean_string(due),
        "scheduled": _clean_string(scheduled),
        "start": _clean_string(start),
        "done": _clean_string(done),
        "cancelled": _clean_string(cancelled),
    }
    for field, value in date_values.items():
        if value is not None and not DATE_RE.match(value):
            return _validation_error(f"Invalid {field}: expected YYYY-MM-DD")

    if tags is not None and not all(isinstance(tag, str) for tag in tags):
        return _validation_error("Invalid tags: expected a list of strings")

    payload = {
        "vault": _clean_string(vault) or OBSIDIAN_DEFAULT_VAULT,
        "title": task_title,
    }

    optional_fields = {
        "status": normalized_status,
        "due": date_values["due"],
        "scheduled": date_values["scheduled"],
        "start": date_values["start"],
        "done": date_values["done"],
        "cancelled": date_values["cancelled"],
        "priority": normalized_priority,
        "recurrence": _clean_string(recurrence),
        "tags": tags,
        "source": _clean_string(source),
    }

    # Legacy compatibility: keep due_text only when the structured due field is absent.
    cleaned_due_text = _clean_string(due_text)
    if date_values["due"] is None and cleaned_due_text is not None:
        optional_fields["due_text"] = cleaned_due_text

    # Phase 2: send depends_on once obsidian-writer supports task dependencies.
    _ = depends_on

    for key, value in optional_fields.items():
        if _is_present(value):
            payload[key] = value

    return _clean_task_http_result(await post("/tasks", payload))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
