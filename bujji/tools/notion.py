"""
bujji/tools/notion.py

Notion tools — everything you need to work with Notion from bujji.

Setup
─────
1. Go to https://www.notion.so/my-integrations
2. Create a new integration → copy the "Internal Integration Secret"
3. Add to ~/.bujji/config.json:
       "tools": {
         "notion": {
           "api_key": "secret_xxxxxxxxxxxx"
         }
       }
4. In Notion: open a page/database → "..." menu → "Add connections" → pick your integration

Tools available
───────────────
  notion_search          — search across all pages & databases
  notion_get_page        — read a page's full text content
  notion_create_page     — create a new standalone page
  notion_append_to_page  — add text/bullets/todos to an existing page
  notion_get_database    — list rows from a database with optional filter
  notion_add_database_row — add a new row to a database
  notion_update_property  — update a property on a database row
  notion_get_comments    — read comments on a page
  notion_add_comment     — add a comment to a page
"""
from __future__ import annotations

from bujji.tools.base import HttpClient, ToolContext, param, register_tool

# ── Shared client factory ─────────────────────────────────────────────────────

def _notion(_ctx: ToolContext) -> HttpClient:
    return HttpClient(
        base_url = "https://api.notion.com/v1",
        headers  = {
            "Authorization":  "Bearer " + _ctx.cred("notion.api_key"),
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json",
        },
    )

# ── Text extraction helpers ───────────────────────────────────────────────────

def _rich_text_to_str(rich_text: list) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text)

def _get_page_title(page: dict) -> str:
    """Extract title from a page or database row."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return _rich_text_to_str(prop.get("title", []))
    return "(Untitled)"

def _blocks_to_text(blocks: list, indent: int = 0) -> str:
    """Convert Notion blocks to readable plain text."""
    lines = []
    prefix = "  " * indent

    for block in blocks:
        btype = block.get("type", "")
        data  = block.get(btype, {})
        text  = _rich_text_to_str(data.get("rich_text", []))

        if btype == "paragraph":
            lines.append(f"{prefix}{text}" if text else "")
        elif btype in ("heading_1", "heading_2", "heading_3"):
            hashes = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[btype]
            lines.append(f"{prefix}{hashes} {text}")
        elif btype == "bulleted_list_item":
            lines.append(f"{prefix}• {text}")
        elif btype == "numbered_list_item":
            lines.append(f"{prefix}1. {text}")
        elif btype == "to_do":
            done = "✅" if data.get("checked") else "⬜"
            lines.append(f"{prefix}{done} {text}")
        elif btype == "toggle":
            lines.append(f"{prefix}▶ {text}")
        elif btype == "quote":
            lines.append(f'{prefix}> {text}')
        elif btype == "callout":
            emoji = data.get("icon", {}).get("emoji", "💡")
            lines.append(f"{prefix}{emoji} {text}")
        elif btype == "divider":
            lines.append(f"{prefix}---")
        elif btype == "code":
            lang = data.get("language", "")
            lines.append(f"{prefix}```{lang}\n{text}\n{prefix}```")
        elif btype == "child_page":
            title = data.get("title", "(child page)")
            lines.append(f"{prefix}📄 [{title}]")
        elif btype == "child_database":
            title = data.get("title", "(child database)")
            lines.append(f"{prefix}🗃️ [{title}]")
        elif btype == "image":
            url = (data.get("file") or data.get("external") or {}).get("url", "")
            caption = _rich_text_to_str(data.get("caption", []))
            lines.append(f"{prefix}🖼️  {caption or url}")
        elif btype == "bookmark":
            url = data.get("url", "")
            caption = _rich_text_to_str(data.get("caption", []))
            lines.append(f"{prefix}🔖 {caption or url}  ({url})")
        elif btype == "equation":
            lines.append(f"{prefix}∑ {data.get('expression', '')}")

        # Recurse into children if present
        if block.get("has_children") and block.get("_children"):
            lines.append(_blocks_to_text(block["_children"], indent + 1))

    return "\n".join(lines)

def _prop_to_str(prop: dict) -> str:
    """Convert any Notion property value to a readable string."""
    ptype = prop.get("type", "")
    val   = prop.get(ptype)

    if val is None:
        return ""
    if ptype == "title":
        return _rich_text_to_str(val)
    if ptype == "rich_text":
        return _rich_text_to_str(val)
    if ptype in ("number", "url", "email", "phone_number"):
        return str(val) if val is not None else ""
    if ptype == "checkbox":
        return "✅" if val else "⬜"
    if ptype == "select":
        return val.get("name", "") if val else ""
    if ptype == "multi_select":
        return ", ".join(o.get("name", "") for o in val)
    if ptype == "status":
        return val.get("name", "") if val else ""
    if ptype == "date":
        if not val:
            return ""
        s = val.get("start", "")
        e = val.get("end", "")
        return f"{s} → {e}" if e else s
    if ptype == "people":
        return ", ".join(
            p.get("name") or p.get("id", "?") for p in val
        )
    if ptype == "files":
        return ", ".join(
            (f.get("file") or f.get("external") or {}).get("url", f.get("name", "?"))
            for f in val
        )
    if ptype == "relation":
        return ", ".join(r.get("id", "") for r in val)
    if ptype == "formula":
        fval = val.get(val.get("type", ""), "")
        return str(fval)
    if ptype == "rollup":
        rtype = val.get("type", "")
        return str(val.get(rtype, ""))
    if ptype == "created_time":
        return str(val)
    if ptype == "last_edited_time":
        return str(val)
    if ptype == "created_by":
        return val.get("name") or val.get("id", "?") if val else ""
    return str(val)[:200]


# ─────────────────────────────────────────────────────────────────────────────
#  TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    description=(
        "Search across all Notion pages and databases your integration has access to. "
        "Returns titles and URLs. Use this first when you don't know the page ID."
    ),
    params=[
        param("query",  "Search query — finds pages, databases, and titles"),
        param("limit",  "Max results to return", type="integer", default=10),
        param("filter", "Filter by 'page' or 'database' (leave empty for both)", default=""),
    ]
)
def notion_search(query: str, limit: int = 10, filter: str = "", _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    payload: dict = {"query": query, "page_size": limit}
    if filter in ("page", "database"):
        payload["filter"] = {"value": filter, "property": "object"}

    data    = notion.post("/search", json=payload)
    results = data.get("results", [])

    if not results:
        return f"No Notion results for '{query}'."

    lines = []
    for r in results:
        kind  = r.get("object", "page")
        title = _get_page_title(r)
        url   = r.get("url", "")
        pid   = r.get("id", "")
        lines.append(f"[{kind}] {title}\n  id:  {pid}\n  url: {url}")

    return "\n\n".join(lines)


@register_tool(
    description=(
        "Read the full text content of a Notion page. "
        "Extracts all blocks — headings, bullets, todos, code, etc — as readable text."
    ),
    params=[
        param("page_id", "Notion page ID (UUID) or full page URL"),
    ]
)
def notion_get_page(page_id: str, _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    page_id = _parse_id(page_id)

    # Get page metadata (title)
    page  = notion.get(f"/pages/{page_id}")
    title = _get_page_title(page)

    # Get all blocks
    blocks = _get_all_blocks(notion, page_id)
    body   = _blocks_to_text(blocks)

    return f"# {title}\n\n{body}" if body.strip() else f"# {title}\n\n(page is empty)"


@register_tool(
    description=(
        "Create a new Notion page inside a parent page or database. "
        "Supports markdown-style content: # headings, - bullets, [ ] todos."
    ),
    params=[
        param("parent_id", "ID of the parent page or database to create the page inside"),
        param("title",     "Page title"),
        param("content",   "Page content — supports markdown: # heading, - bullet, [ ] todo, text paragraphs", default=""),
    ]
)
def notion_create_page(parent_id: str, title: str, content: str = "", _ctx: ToolContext = None) -> str:
    notion    = _notion(_ctx)
    parent_id = _parse_id(parent_id)

    # Figure out if parent is a database or page
    parent_type = _get_object_type(notion, parent_id)

    if parent_type == "database":
        parent_obj = {"database_id": parent_id}
        properties = {"Name": {"title": [{"text": {"content": title}}]}}
    else:
        parent_obj = {"page_id": parent_id}
        properties = {"title": {"title": [{"text": {"content": title}}]}}

    children = _markdown_to_blocks(content) if content.strip() else []

    result = notion.post("/pages", json={
        "parent":     parent_obj,
        "properties": properties,
        "children":   children,
    })

    return f"✓ Page created: {title}\n  id:  {result.get('id')}\n  url: {result.get('url')}"


@register_tool(
    description=(
        "Append new content to the end of an existing Notion page. "
        "Supports markdown-style text: # headings, - bullets, [ ] todos, plain paragraphs. "
        "Use this to add notes, logs, or updates without overwriting the page."
    ),
    params=[
        param("page_id", "Notion page ID or URL"),
        param("content", "Content to append — supports # heading, - bullet, [ ] todo, plain text"),
    ]
)
def notion_append_to_page(page_id: str, content: str, _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    page_id = _parse_id(page_id)
    blocks  = _markdown_to_blocks(content)

    if not blocks:
        return "Nothing to append — content was empty."

    notion.patch(f"/blocks/{page_id}/children", json={"children": blocks})
    return f"✓ Appended {len(blocks)} block(s) to page {page_id}"


@register_tool(
    description=(
        "List rows from a Notion database. "
        "Optionally filter by a property value. "
        "Returns all property values for each row."
    ),
    params=[
        param("database_id",    "Notion database ID or URL"),
        param("limit",          "Max rows to return", type="integer", default=20),
        param("filter_property","Property name to filter by (optional)", default=""),
        param("filter_value",   "Value to match for the filter (optional)", default=""),
        param("sort_property",  "Property to sort by (optional)", default=""),
        param("sort_direction", "ascending or descending", enum=["ascending","descending"], default="descending"),
    ]
)
def notion_get_database(
    database_id:     str,
    limit:           int = 20,
    filter_property: str = "",
    filter_value:    str = "",
    sort_property:   str = "",
    sort_direction:  str = "descending",
    _ctx: ToolContext = None,
) -> str:
    notion      = _notion(_ctx)
    database_id = _parse_id(database_id)
    payload: dict = {"page_size": limit}

    if filter_property and filter_value:
        payload["filter"] = {
            "property": filter_property,
            "rich_text": {"contains": filter_value},
        }

    if sort_property:
        payload["sorts"] = [{"property": sort_property, "direction": sort_direction}]

    data = notion.post(f"/databases/{database_id}/query", json=payload)
    rows = data.get("results", [])

    if not rows:
        return "No rows found in this database."

    # Get property names from first row
    if rows:
        prop_names = list(rows[0].get("properties", {}).keys())
    else:
        prop_names = []

    lines = []
    for row in rows:
        props = row.get("properties", {})
        pid   = row.get("id", "")
        url   = row.get("url", "")
        vals  = {name: _prop_to_str(props.get(name, {})) for name in prop_names}
        title = vals.get("Name") or vals.get("Title") or next(iter(vals.values()), "(no title)")
        other = {k: v for k, v in vals.items() if k not in ("Name", "Title") and v}
        prop_str = "  ".join(f"{k}: {v}" for k, v in other.items())
        lines.append(f"• {title}  (id: {pid})\n  {prop_str}\n  {url}".strip())

    return f"Found {len(rows)} row(s):\n\n" + "\n\n".join(lines)


@register_tool(
    description=(
        "Add a new row to a Notion database. "
        "Pass properties as a JSON object where keys are column names and values are the content."
    ),
    params=[
        param("database_id",  "Notion database ID or URL"),
        param("title",        "Value for the main title/name column"),
        param("properties",   "Other properties as JSON, e.g. {\"Status\": \"In Progress\", \"Priority\": \"High\"}", default="{}"),
    ]
)
def notion_add_database_row(
    database_id: str,
    title:       str,
    properties:  str = "{}",
    _ctx: ToolContext = None,
) -> str:
    import json
    notion      = _notion(_ctx)
    database_id = _parse_id(database_id)

    try:
        extra_props = json.loads(properties) if properties.strip() else {}
    except json.JSONDecodeError as e:
        return f"[Notion] Invalid JSON for properties: {e}"

    # First, get the database schema to know property types
    db_schema = notion.get(f"/databases/{database_id}")
    db_props  = db_schema.get("properties", {})

    # Find the title property name
    title_prop_name = next(
        (name for name, prop in db_props.items() if prop.get("type") == "title"),
        "Name"
    )

    props_payload: dict = {
        title_prop_name: {"title": [{"text": {"content": title}}]}
    }

    # Map extra properties to Notion format based on schema
    for key, value in extra_props.items():
        if key not in db_props:
            continue
        ptype = db_props[key].get("type", "")
        if ptype == "rich_text":
            props_payload[key] = {"rich_text": [{"text": {"content": str(value)}}]}
        elif ptype == "number":
            props_payload[key] = {"number": float(value)}
        elif ptype == "select":
            props_payload[key] = {"select": {"name": str(value)}}
        elif ptype == "multi_select":
            vals = value if isinstance(value, list) else [value]
            props_payload[key] = {"multi_select": [{"name": str(v)} for v in vals]}
        elif ptype == "checkbox":
            props_payload[key] = {"checkbox": bool(value)}
        elif ptype == "date":
            props_payload[key] = {"date": {"start": str(value)}}
        elif ptype == "url":
            props_payload[key] = {"url": str(value)}
        elif ptype == "email":
            props_payload[key] = {"email": str(value)}
        elif ptype == "phone_number":
            props_payload[key] = {"phone_number": str(value)}
        elif ptype == "status":
            props_payload[key] = {"status": {"name": str(value)}}

    result = notion.post("/pages", json={
        "parent":     {"database_id": database_id},
        "properties": props_payload,
    })

    return f"✓ Row added: {title}\n  id:  {result.get('id')}\n  url: {result.get('url')}"


@register_tool(
    description="Update a single property value on a Notion database row (page).",
    params=[
        param("page_id",       "ID of the database row (page) to update"),
        param("property_name", "Name of the property to update, e.g. 'Status'"),
        param("value",         "New value — for select/status use the option name, for checkbox use true/false"),
    ]
)
def notion_update_property(page_id: str, property_name: str, value: str, _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    page_id = _parse_id(page_id)

    # Get current page to find property type
    page  = notion.get(f"/pages/{page_id}")
    props = page.get("properties", {})

    if property_name not in props:
        available = ", ".join(props.keys())
        return f"[Notion] Property '{property_name}' not found.\nAvailable: {available}"

    ptype = props[property_name].get("type", "")

    if ptype == "rich_text":
        prop_val = {"rich_text": [{"text": {"content": value}}]}
    elif ptype == "title":
        prop_val = {"title": [{"text": {"content": value}}]}
    elif ptype == "number":
        prop_val = {"number": float(value)}
    elif ptype == "select":
        prop_val = {"select": {"name": value}}
    elif ptype == "multi_select":
        prop_val = {"multi_select": [{"name": v.strip()} for v in value.split(",")]}
    elif ptype == "checkbox":
        prop_val = {"checkbox": value.lower() in ("true", "yes", "1", "✅")}
    elif ptype == "date":
        prop_val = {"date": {"start": value}}
    elif ptype == "url":
        prop_val = {"url": value}
    elif ptype == "email":
        prop_val = {"email": value}
    elif ptype == "phone_number":
        prop_val = {"phone_number": value}
    elif ptype == "status":
        prop_val = {"status": {"name": value}}
    else:
        return f"[Notion] Property type '{ptype}' is not directly editable via API."

    notion.patch(f"/pages/{page_id}", json={"properties": {property_name: prop_val}})
    return f"✓ Updated '{property_name}' → '{value}' on page {page_id}"


@register_tool(
    description="Get all comments on a Notion page.",
    params=[
        param("page_id", "Notion page ID or URL"),
    ]
)
def notion_get_comments(page_id: str, _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    page_id = _parse_id(page_id)

    data     = notion.get("/comments", params={"block_id": page_id})
    comments = data.get("results", [])

    if not comments:
        return "No comments on this page."

    lines = []
    for c in comments:
        author  = c.get("created_by", {}).get("name", "Unknown")
        created = c.get("created_time", "")[:10]
        text    = _rich_text_to_str(c.get("rich_text", []))
        lines.append(f"[{created}] {author}: {text}")

    return "\n".join(lines)


@register_tool(
    description="Add a comment to a Notion page.",
    params=[
        param("page_id", "Notion page ID or URL"),
        param("comment", "Comment text to add"),
    ]
)
def notion_add_comment(page_id: str, comment: str, _ctx: ToolContext = None) -> str:
    notion  = _notion(_ctx)
    page_id = _parse_id(page_id)

    notion.post("/comments", json={
        "parent":    {"page_id": page_id},
        "rich_text": [{"text": {"content": comment}}],
    })

    return f"✓ Comment added to page {page_id}"


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_id(id_or_url: str) -> str:
    """Accept a full Notion URL or bare UUID, always return a clean UUID."""
    s = id_or_url.strip()
    if s.startswith("http"):
        # https://www.notion.so/Page-Title-abc123def456...  → last 32-char hex segment
        slug = s.rstrip("/").split("/")[-1].split("?")[0]
        # Remove the title prefix, keep the last 32-char ID
        if "-" in slug:
            slug = slug.split("-")[-1]
        if len(slug) == 32:
            return f"{slug[:8]}-{slug[8:12]}-{slug[12:16]}-{slug[16:20]}-{slug[20:]}"
        return slug
    return s


def _get_object_type(notion: HttpClient, object_id: str) -> str:
    """Return 'page', 'database', or 'block'."""
    try:
        page = notion.get(f"/pages/{object_id}")
        return page.get("object", "page")
    except Exception:
        pass
    try:
        db = notion.get(f"/databases/{object_id}")
        return db.get("object", "database")
    except Exception:
        pass
    return "page"


def _get_all_blocks(notion: HttpClient, block_id: str) -> list:
    """Fetch all blocks, following pagination."""
    blocks   = []
    cursor   = None
    while True:
        params: dict = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        data     = notion.get(f"/blocks/{block_id}/children", params=params)
        results  = data.get("results", [])
        blocks  += results
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def _markdown_to_blocks(text: str) -> list:
    """
    Convert simple markdown-ish text into Notion block objects.

    Supported:
      # Heading 1        → heading_1
      ## Heading 2       → heading_2
      ### Heading 3      → heading_3
      - item / * item    → bulleted_list_item
      1. item            → numbered_list_item
      [x] done           → to_do (checked)
      [ ] todo           → to_do (unchecked)
      > quote            → quote
      ```code```         → code block
      plain text         → paragraph
    """
    blocks = []
    lines  = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.strip().startswith("```"):
            code_lines = []
            lang = line.strip()[3:].strip()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language":  lang or "plain text",
                }
            })
            i += 1
            continue

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("### "):
            btype, content = "heading_3", stripped[4:]
        elif stripped.startswith("## "):
            btype, content = "heading_2", stripped[3:]
        elif stripped.startswith("# "):
            btype, content = "heading_1", stripped[2:]
        elif stripped.startswith(("- ", "* ")):
            btype, content = "bulleted_list_item", stripped[2:]
        elif stripped[:3] in ("1. ", "2. ", "3. ") and stripped[1:3] == ". ":
            btype, content = "numbered_list_item", stripped[3:]
        elif stripped.lower().startswith("[x] "):
            btype, content = "to_do", stripped[4:]
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "checked":   True,
                }
            })
            i += 1
            continue
        elif stripped.lower().startswith("[ ] "):
            btype, content = "to_do", stripped[4:]
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "checked":   False,
                }
            })
            i += 1
            continue
        elif stripped.startswith("> "):
            btype, content = "quote", stripped[2:]
        else:
            btype, content = "paragraph", stripped

        blocks.append({
            "object": "block",
            "type":   btype,
            btype:    {"rich_text": [{"type": "text", "text": {"content": content}}]},
        })
        i += 1

    return blocks