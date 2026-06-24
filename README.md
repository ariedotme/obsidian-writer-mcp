# obsidian-writer-mcp

MCP server for writing to Obsidian through the `obsidian-writer` HTTP service.

This project was originally created for personal use in my homelab. I later decided to publish it in case it is useful to other people building similar local-first Obsidian automation.

Related project: [`obsidian-writer`](https://github.com/ariedotme/obsidian-writer), the HTTP service this MCP server calls to write into Obsidian vaults.

## Configuration

The server reads environment variables from the process and from `.env` files. Existing process variables take precedence over `.env` values.

Load order:

1. `.env` next to `obsidian_writer_mcp.py`
2. `.env` in the current working directory

Create a local `.env` from the example:

```bash
cp .env.example .env
```

Variables:

- `OBSIDIAN_WRITER_BASE_URL`: base URL for the HTTP writer. Default: `http://obsidian-writer:3000`.
- `OBSIDIAN_DEFAULT_VAULT`: default vault used when a tool does not receive `vault`. Default: `default`.

Example:

```env
OBSIDIAN_WRITER_BASE_URL=http://obsidian-writer:3000
OBSIDIAN_DEFAULT_VAULT=my-vault
```

The `.env` file is ignored by Git; publish `.env.example` and keep local values private.

## Hermes registration

If this repository is mounted inside the Hermes container at `/srv/apps/obsidian-writer-mcp`, register it without hardcoded vault values; the MCP will read `.env` itself:

```bash
docker exec -it hermes hermes -p <profile> mcp remove obsidian-writer || true

docker exec -it hermes hermes -p <profile> mcp add obsidian-writer \
  --command sh \
  --args -lc 'exec uv run --with fastmcp --with httpx python /srv/apps/obsidian-writer-mcp/obsidian_writer_mcp.py'

docker exec -it hermes hermes -p <profile> mcp test obsidian-writer
```

If your `obsidian-writer` service is not reachable as `http://obsidian-writer:3000` from inside Hermes, change `OBSIDIAN_WRITER_BASE_URL` in `.env`.

## Tools

### Inbox

- `obsidian_append_inbox`: append one line to today's inbox file in the configured default vault.

### Lists

- `obsidian_list_lists`: list existing Obsidian checklist files.
- `obsidian_list_add`: add unchecked items to a named list.
- `obsidian_list_remove`: remove items from a named list.
- `obsidian_list_update`: update/rename items in a named list.

### Notes

- `obsidian_list_notes`: list existing notes.
- `obsidian_read_note`: read a note by slug.
- `obsidian_create_note`: create a new standalone Markdown note.
- `obsidian_append_note`: append Markdown content to an existing note.
- `obsidian_create_or_append_note`: create a note or append to an existing compatible note.

### Tasks

Task creation keeps its existing tool name: `obsidian_create_task`.

Task listing is available as `obsidian_list_tasks` and reads structured tasks through `GET /tasks`.

Creation sends structured JSON to `POST /tasks`; it does **not** format Obsidian Tasks Markdown itself. The canonical formatter is the `obsidian-writer` service.

Supported creation fields include:

- `vault`
- `title`
- `content` (legacy fallback for `title`)
- `status`: `todo`, `done`, `cancelled`
- `due`, `scheduled`, `start`, `done`, `cancelled`: dates as `YYYY-MM-DD`
- `priority`: `highest`, `high`, `medium`, `low`, `lowest`, `none`
- `recurrence`
- `tags`
- `source`
- `due_text` (legacy; ignored when `due` is provided)
- `depends_on` (accepted by the MCP for compatibility, but not sent yet)

Dependencies are reserved for phase 2 if/when `obsidian-writer` supports them.

Listing supports:

- `status`: `todo` (default), `done`, `cancelled`, or `all`
- `limit`: optional positive integer
- `vault`: optional vault override

## Examples

Create a task using the configured default vault:

```python
obsidian_create_task(
    title="Pay electricity bill",
    due="2026-06-25",
    priority="high",
    tags=["home", "bills"],
    source="assistant",
)
```

List pending tasks:

```python
obsidian_list_tasks(status="todo", limit=20)
```

Create or append a note:

```python
obsidian_create_or_append_note(
    title="Project ideas",
    content="- Try a simpler publishing flow",
)
```

## Local development

Run the server over stdio:

```bash
uv run --with fastmcp --with httpx python obsidian_writer_mcp.py
```

The process will wait for MCP stdio messages; that is expected.
