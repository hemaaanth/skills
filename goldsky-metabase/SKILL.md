---
name: goldsky-metabase
description: Create and manage Metabase dashboards and queries on the CDP ClickHouse instance
trigger: /goldsky-metabase
env_requires:
  - METABASE_URL
  - METABASE_API_KEY
---

# Metabase Dashboard & Query Management

You are a Metabase expert. You help users create dashboards, write queries, and manage analytics on a Metabase instance connected to a ClickHouse CDP (Customer Data Platform) database.

## Environment Verification

Credentials are stored in `.env` at the repo root (gitignored). Before doing anything, source it and verify:

```bash
# Source credentials from repo root .env
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '.')"
if [ -f "$REPO_ROOT/.env" ]; then
  set -a && source "$REPO_ROOT/.env" && set +a
fi

# Check env vars are set
[ -z "$METABASE_URL" ] && echo "ERROR: Set METABASE_URL in .env" && exit 1
[ -z "$METABASE_API_KEY" ] && echo "ERROR: Set METABASE_API_KEY in .env" && exit 1

# Test connectivity
curl -s -o /dev/null -w "%{http_code}" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/user/current"
```

If verification fails, tell the user which variable is missing or invalid and stop. The `.env` file should contain:

```
METABASE_URL=https://dash.goldsky.com
METABASE_API_KEY=mb_...
```

## Decision Tree

When the user invokes this skill, use AskUserQuestion to determine their intent:

**"What would you like to do?"**

| Option | Description |
|--------|-------------|
| Browse existing dashboards & questions | See what already exists — list, search, inspect dashboards and saved questions |
| Explore data / schema | Browse databases, tables, and columns |
| Create a dashboard | Build a new dashboard with cards |
| Create or run a query | Write and execute SQL against ClickHouse |
| Modify existing dashboard | Update cards, layout, or parameters on an existing dashboard |
| Manage collections | Organize dashboards and queries into collections |
| Export data | Download query results as CSV, JSON, or XLSX |
| Configure drill-throughs | Set up click behaviors on dashboard cards |
| Share publicly | Create public links for dashboards or cards |

---

## Workflow 0: Browse Existing Dashboards & Questions

Use this workflow to see what already exists in Metabase before creating anything new.

### List all dashboards

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/dashboard/" \
  | jq '.[] | {id, name, collection_id, created_at}'
```

### Search for dashboards or questions by name

```bash
# Search dashboards
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/search?q=SEARCH_TERM&models=dashboard" \
  | jq '.data[] | {id, name, collection: .collection.name}'

# Search saved questions (cards)
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/search?q=SEARCH_TERM&models=card" \
  | jq '.data[] | {id, name, display, collection: .collection.name}'
```

### Inspect a dashboard (full details)

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/dashboard/{DASHBOARD_ID}" \
  | jq '{
    name, description, collection_id,
    parameters: [.parameters[] | {name, slug, type}],
    cards: [.dashcards[] | {
      dashcard_id: .id,
      card_id: .card_id,
      card_name: .card.name,
      display: .card.display,
      position: {row: .row, col: .col, size_x: .size_x, size_y: .size_y}
    }]
  }'
```

This shows the dashboard layout, all cards with their positions, display types, and any parameters (filters).

### Inspect a saved question (card)

```bash
# Get card details and its SQL query
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/card/{CARD_ID}" \
  | jq '{
    name, description, display, type,
    database_id: .dataset_query.database,
    query: .dataset_query.native.query,
    visualization_settings
  }'
```

### Run a saved question and see its results

```bash
curl -s -X POST "$METABASE_URL/api/card/{CARD_ID}/query" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  | jq '{
    columns: [.data.cols[] | .name],
    row_count: .row_count,
    rows: .data.rows[:5]
  }'
```

### Browse items in a collection

```bash
# List dashboards and cards in a collection
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/collection/{COLLECTION_ID}/items?models=dashboard&models=card" \
  | jq '.data[] | {id, name, model, description}'
```

### Get a dashboard's query metadata

Useful for understanding what databases and tables a dashboard's cards query:

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/dashboard/{DASHBOARD_ID}/query_metadata" \
  | jq '.databases[] | {id, name, tables: [.tables[] | .name]}'
```

---

## Workflow 1: Explore Data / Schema Discovery

### Step 1: List databases and find ClickHouse

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/database/" | jq '.data[] | {id, name, engine}'
```

Look for entries where `engine` is `"clickhouse"`. Note the database `id`.

### Step 2: List schemas

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/database/{DB_ID}/schemas"
```

### Step 3: List tables in a schema

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/database/{DB_ID}/schema/{SCHEMA_NAME}"
```

### Step 4: Get table metadata (columns, types)

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/table/{TABLE_ID}/query_metadata" \
  | jq '.fields[] | {name, database_type, base_type, semantic_type}'
```

### Step 5: Cache metadata

Save discovered metadata to `data/cache/schema-{db_id}.json` for reuse in query authoring:

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/database/{DB_ID}/metadata?include_hidden=true" \
  > skills/metabase/data/cache/schema-{DB_ID}.json
```

---

## Workflow 2: Create a Dashboard

### Step 1: Gather requirements

Use AskUserQuestion:
- Dashboard name and description
- Which collection to place it in (list collections first)
- What data/metrics to show
- How many cards and what chart types

### Step 2: Create the dashboard

```bash
curl -s -X POST "$METABASE_URL/api/dashboard/" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dashboard Name",
    "description": "Description",
    "collection_id": null
  }'
```

Save the returned `id` as `DASHBOARD_ID`.

### Step 3: Create cards (saved questions)

For each metric/chart, create a card first:

```bash
curl -s -X POST "$METABASE_URL/api/card/" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Card Name",
    "dataset_query": {
      "type": "native",
      "native": {
        "query": "SELECT ... FROM ..."
      },
      "database": DB_ID
    },
    "display": "bar",
    "type": "question",
    "visualization_settings": {},
    "collection_id": null
  }'
```

**Note:** The `type` field distinguishes questions from models. Use `"question"` for saved queries (default) and `"model"` for curated datasets. The older `dataset` boolean field is deprecated.

### Step 4: Add cards to dashboard

Use PUT to update the dashboard with dashcards. The grid is 24 columns wide:

```bash
curl -s -X PUT "$METABASE_URL/api/dashboard/{DASHBOARD_ID}" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dashcards": [
      {
        "id": -1,
        "card_id": CARD_ID,
        "row": 0,
        "col": 0,
        "size_x": 12,
        "size_y": 8,
        "parameter_mappings": []
      },
      {
        "id": -2,
        "card_id": CARD_ID_2,
        "row": 0,
        "col": 12,
        "size_x": 12,
        "size_y": 8,
        "parameter_mappings": []
      }
    ]
  }'
```

**Grid layout tips:**
- Full width: `size_x: 24`
- Half width: `size_x: 12`
- Third width: `size_x: 8`
- Quarter width: `size_x: 6`
- Use negative IDs (`-1`, `-2`, ...) for new dashcards
- `row` increments vertically, `col` positions horizontally (0–23)

**Text and heading cards:**

You can add text cards (markdown) and heading cards to dashboards without a saved question. Use `card_id: null` and set the `text` or `virtual_card` field:

```json
{
  "id": -3,
  "card_id": null,
  "row": 0, "col": 0, "size_x": 24, "size_y": 2,
  "visualization_settings": {
    "virtual_card": {
      "display": "text",
      "archived": false
    },
    "text": "## Section Heading\nDescriptive text in **markdown**."
  },
  "parameter_mappings": []
}
```

---

## Workflow 3: Create / Run a Query

### Step 1: Discover schema

Use Workflow 1 to find the right database, schema, table, and columns. Check the cache first:

```bash
cat skills/metabase/data/cache/schema-{DB_ID}.json | jq '.tables[] | .name'
```

### Step 2: Write the SQL query

Write ClickHouse-compatible SQL. See the ClickHouse SQL Quick Reference below.

### Step 3: Test the query

Run with a LIMIT first to verify results:

```bash
curl -s -X POST "$METABASE_URL/api/dataset/" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "native",
    "native": {
      "query": "SELECT ... FROM ... LIMIT 10"
    },
    "database": DB_ID
  }' | jq '.data.rows[:5]'
```

### Step 4: Save as a card

Once verified, save the query as a card using the card creation endpoint from Workflow 2, Step 3.

---

## Workflow 4: Modify Existing Dashboard

### Step 1: Find the dashboard

```bash
# Search by name
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/search?q=dashboard+name&models=dashboard"

# Get full dashboard details
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/dashboard/{DASHBOARD_ID}"
```

### Step 2: Determine changes

Use AskUserQuestion: "What would you like to change?"
- Add new cards
- Remove existing cards
- Rearrange card layout
- Update card queries or display settings
- Add/modify dashboard parameters (filters)

### Step 3: Apply changes

For layout changes, PUT the updated `dashcards` array to `/api/dashboard/{DASHBOARD_ID}`.

For card query changes, PUT to `/api/card/{CARD_ID}`.

**Important:** When updating dashcards, include ALL existing dashcards (with their real IDs) plus any new ones (with negative IDs). Omitting existing dashcards will remove them.

---

## Workflow 5: Manage Collections

### Step 1: View collection tree

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/collection/tree" \
  | jq '.[] | {id, name, location}'
```

### Step 2: List items in a collection

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/collection/{COLLECTION_ID}/items?models=dashboard&models=card"
```

### Step 3: Create a collection

```bash
curl -s -X POST "$METABASE_URL/api/collection/" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Collection Name",
    "parent_id": null
  }'
```

---

## Workflow 6: Export Data

### Export card results

```bash
# CSV
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/card/{CARD_ID}/query/csv" -o results.csv

# JSON
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/card/{CARD_ID}/query/json" -o results.json

# XLSX
curl -s -H "X-Api-Key: $METABASE_API_KEY" \
  "$METABASE_URL/api/card/{CARD_ID}/query/xlsx" -o results.xlsx
```

### Export ad-hoc query results

```bash
curl -s -X POST "$METABASE_URL/api/dataset/csv" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "native",
    "native": {"query": "SELECT ..."},
    "database": DB_ID
  }' -o results.csv
```

---

## Workflow 7: Configure Drill-Throughs

Drill-throughs define what happens when a user clicks on a card in a dashboard. They are configured via `click_behavior` in a dashcard's `visualization_settings`.

### Click behavior types

| Type | Description |
|------|-------------|
| `link` | Navigate to another dashboard, saved question, or external URL |
| `crossfilter` | Click on a value to filter other cards on the same dashboard |
| `actionMenu` | Show Metabase's default action menu (default behavior) |

### Step 1: Get the current dashboard

```bash
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/dashboard/{DASHBOARD_ID}" \
  | jq '.dashcards[] | {id, card_id, visualization_settings}'
```

Note the dashcard `id` values — these are what you update (not the card IDs).

### Step 2: Configure click behavior

Update the dashboard with modified dashcard `visualization_settings`. Include ALL dashcards in the PUT (omitting a dashcard removes it).

#### Link to another dashboard

Pass column values as parameter mappings to pre-filter the target dashboard:

```bash
curl -s -X PUT "$METABASE_URL/api/dashboard/{DASHBOARD_ID}" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dashcards": [
      {
        "id": DASHCARD_ID,
        "card_id": CARD_ID,
        "row": 0, "col": 0, "size_x": 12, "size_y": 8,
        "visualization_settings": {
          "click_behavior": {
            "type": "link",
            "linkType": "dashboard",
            "targetId": TARGET_DASHBOARD_ID,
            "parameterMapping": {
              "TARGET_PARAM_ID": {
                "source": { "type": "column", "id": "COLUMN_NAME", "name": "Column Name" },
                "target": { "type": "parameter", "id": "TARGET_PARAM_ID" },
                "id": "TARGET_PARAM_ID"
              }
            }
          }
        },
        "parameter_mappings": []
      }
    ]
  }'
```

#### Link to a saved question

```json
{
  "click_behavior": {
    "type": "link",
    "linkType": "question",
    "targetId": CARD_ID
  }
}
```

#### Link to an external URL

Use `{{COLUMN_NAME}}` template variables to inject row values into the URL:

```json
{
  "click_behavior": {
    "type": "link",
    "linkType": "url",
    "linkTemplate": "https://example.com/details/{{user_id}}"
  }
}
```

#### Cross-filter other cards

Clicking a value on this card filters other cards on the same dashboard via their parameter mappings:

```json
{
  "click_behavior": {
    "type": "crossfilter",
    "parameterMapping": {
      "DASHBOARD_PARAM_ID": {
        "source": { "type": "column", "id": "COLUMN_NAME", "name": "Column Name" },
        "target": { "type": "parameter", "id": "DASHBOARD_PARAM_ID" },
        "id": "DASHBOARD_PARAM_ID"
      }
    }
  }
}
```

**Important:** Cross-filter requires that the dashboard has parameters defined and that the target cards have `parameter_mappings` linking those parameters to their query template tags or columns.

### Common patterns

**Summary → Detail dashboard:** A top-level dashboard shows aggregates (e.g., wallets by chain). Clicking a chain row links to a detail dashboard filtered by that chain.

1. Create the detail dashboard with a parameter (e.g., `chain` of type `string/=`)
2. On the summary dashboard, set `click_behavior` on the summary card to `link` → `dashboard` with `parameterMapping` from the `chain` column to the detail dashboard's `chain` parameter

**Cross-filter grid:** Multiple cards on one dashboard filter each other. Clicking "Ethereum" on a pie chart filters the table, line chart, and bar chart to show only Ethereum data.

1. Add a dashboard parameter (e.g., `chain`)
2. Map each card's relevant column to that parameter via `parameter_mappings`
3. Set `click_behavior: { type: "crossfilter" }` on the pie chart card with a mapping from its `chain` column to the dashboard parameter

---

## Workflow 8: Public Sharing

Create public links to share dashboards or cards without requiring Metabase login.

### Share a dashboard publicly

```bash
# Create public link
curl -s -X POST "$METABASE_URL/api/dashboard/{DASHBOARD_ID}/public_link" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json"
```

Response includes a `uuid`. The public URL is: `$METABASE_URL/public/dashboard/{uuid}`

### Share a card publicly

```bash
curl -s -X POST "$METABASE_URL/api/card/{CARD_ID}/public_link" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json"
```

Public URL: `$METABASE_URL/public/question/{uuid}`

### List public dashboards and cards

```bash
# Public dashboards
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/dashboard/public"

# Public cards
curl -s -H "X-Api-Key: $METABASE_API_KEY" "$METABASE_URL/api/card/public"
```

### Revoke a public link

```bash
# Dashboard
curl -s -X DELETE "$METABASE_URL/api/dashboard/{DASHBOARD_ID}/public_link" \
  -H "X-Api-Key: $METABASE_API_KEY"

# Card
curl -s -X DELETE "$METABASE_URL/api/card/{CARD_ID}/public_link" \
  -H "X-Api-Key: $METABASE_API_KEY"
```

### Copy a dashboard

Duplicate an existing dashboard (including all its cards) into a target collection:

```bash
curl -s -X POST "$METABASE_URL/api/dashboard/{DASHBOARD_ID}/copy" \
  -H "X-Api-Key: $METABASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Copy of Dashboard",
    "collection_id": TARGET_COLLECTION_ID,
    "is_deep_copy": true
  }'
```

Set `is_deep_copy: true` to also duplicate the underlying cards (not just reference them).

---

## Command Reference

### Database & Schema

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/database/` | List all databases |
| GET | `/api/database/{id}` | Get database by ID |
| GET | `/api/database/{id}/metadata` | Full database metadata (tables, columns, types) |
| GET | `/api/database/{id}/schemas` | List schemas |
| GET | `/api/database/{id}/schema/{name}` | List tables in schema |
| GET | `/api/database/{id}/fields` | List all fields in database |
| GET | `/api/database/{id}/autocomplete_suggestions` | SQL autocomplete suggestions |
| GET | `/api/database/{id}/healthcheck` | Database connection health |
| POST | `/api/database/{id}/sync_schema` | Trigger schema resync |
| POST | `/api/database/{id}/rescan_values` | Rescan field values |
| GET | `/api/table/{id}/query_metadata` | Table columns and types |

### Cards (Saved Questions)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/card/{id}` | Get a saved question |
| POST | `/api/card/` | Create a saved question (`type`: `"question"` or `"model"`) |
| PUT | `/api/card/{id}` | Update a saved question |
| DELETE | `/api/card/{id}` | Delete a saved question |
| POST | `/api/card/{id}/query` | Run a saved card's query |
| GET | `/api/card/{id}/query/csv` | Export card results as CSV |
| GET | `/api/card/{id}/query/json` | Export card results as JSON |
| GET | `/api/card/{id}/query/xlsx` | Export card results as XLSX |
| POST | `/api/card/{id}/public_link` | Create public link for card |
| DELETE | `/api/card/{id}/public_link` | Revoke public link |
| GET | `/api/card/public` | List all publicly shared cards |
| GET | `/api/card/embeddable` | List embeddable cards |

### Dashboards

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/` | List all dashboards |
| GET | `/api/dashboard/{id}` | Get dashboard with cards |
| POST | `/api/dashboard/` | Create a dashboard |
| PUT | `/api/dashboard/{id}` | Update dashboard (incl. dashcards layout) |
| DELETE | `/api/dashboard/{id}` | Delete a dashboard |
| PUT | `/api/dashboard/{id}/cards` | Update dashboard cards only |
| POST | `/api/dashboard/{id}/copy` | Copy dashboard (with `is_deep_copy` option) |
| GET | `/api/dashboard/{id}/query_metadata` | Query metadata for dashboard cards |
| GET | `/api/dashboard/{id}/related` | Related dashboards |
| GET | `/api/dashboard/{id}/params/{param}/values` | Parameter filter values |
| GET | `/api/dashboard/{id}/params/{param}/search/{q}` | Search parameter values |
| POST | `/api/dashboard/{id}/public_link` | Create public link |
| DELETE | `/api/dashboard/{id}/public_link` | Revoke public link |
| GET | `/api/dashboard/public` | List all publicly shared dashboards |
| GET | `/api/dashboard/embeddable` | List embeddable dashboards |
| POST | `/api/dashboard/pivot/{id}/dashcard/{dc}/card/{c}/query` | Pivot query for dashcard |
| POST | `/api/dashboard/{id}/dashcard/{dc}/card/{c}/query` | Run query for specific dashcard |
| POST | `/api/dashboard/{id}/dashcard/{dc}/card/{c}/query/{fmt}` | Export dashcard query results |

### Dataset (Ad-hoc Queries)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dataset/` | Execute a query |
| POST | `/api/dataset/{export-format}` | Execute query and export (`csv`, `json`, `xlsx`) |
| POST | `/api/dataset/native` | Execute a native SQL query |
| POST | `/api/dataset/pivot` | Execute a pivot query |
| POST | `/api/dataset/query_metadata` | Get metadata for a query |

### Collections

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/collection/` | List all collections |
| POST | `/api/collection/` | Create a collection |
| GET | `/api/collection/tree` | Collection hierarchy |
| GET | `/api/collection/root/items` | Items in root collection |
| GET | `/api/collection/{id}` | Get collection by ID |
| GET | `/api/collection/{id}/items` | Items in a collection |
| PUT | `/api/collection/{id}` | Update a collection |
| DELETE | `/api/collection/{id}` | Delete a collection |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/user/current` | Current user (auth verification) |
| GET | `/api/search` | Search across all models (cards, dashboards, collections) |

## ClickHouse SQL Quick Reference

### Counting & Uniqueness

```sql
uniq(user_id)                      -- Approximate unique count (fast, default choice)
uniqExact(user_id)                 -- Exact unique count (more memory)
uniqHLL12(user_id)                 -- HyperLogLog unique count
count()                            -- Row count
```

### Conditional Aggregation (-If combinator)

Append `-If` to any aggregate function to filter inline — avoids subqueries:

```sql
countIf(status = 'active')
sumIf(amount, status = 'completed')
avgIf(latency, chain = 'ethereum')
uniqIf(user_id, event_type = 'transfer')
```

### Statistical & Advanced Aggregates

```sql
quantile(0.95)(latency)            -- 95th percentile
quantiles(0.5, 0.9, 0.99)(latency) -- Multiple percentiles at once
topK(10)(chain)                    -- Top 10 most frequent values
groupArray(name)                   -- Collect values into an array
groupUniqArray(tag)                -- Collect unique values into an array
argMin(name, created_at)           -- Value of name at minimum created_at
argMax(name, updated_at)           -- Value of name at maximum updated_at
any(status)                        -- Arbitrary value from group
anyLast(status)                    -- Last value in insertion order
```

### Date & Time Functions

```sql
-- Ranges
WHERE event_date >= today() - INTERVAL 7 DAY
WHERE event_date BETWEEN '2026-01-01' AND '2026-01-31'

-- Truncation
toStartOfDay(event_time)
toStartOfWeek(event_date)
toStartOfMonth(event_date)
toStartOfHour(event_time)
toStartOfMinute(event_time)

-- Formatting & conversion
formatDateTime(event_time, '%Y-%m-%d %H:%M')
toDate(event_time)                 -- Extract date from datetime
toDateTime('2026-01-01 00:00:00')  -- Parse datetime string

-- Differences
dateDiff('day', start_date, end_date)
dateDiff('hour', start_time, end_time)
```

### Array Functions

```sql
arrayJoin(tags)                    -- Expand array into rows
has(tags, 'vip')                   -- Check if array contains value
length(tags)                       -- Array length
arrayDistinct(tags)                -- Deduplicate array
arraySort(tags)                    -- Sort array
arrayFilter(x -> x > 0, values)   -- Filter array elements
```

### Window Functions

```sql
ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_time DESC)
rank() OVER (PARTITION BY chain ORDER BY volume DESC)
dense_rank() OVER (PARTITION BY chain ORDER BY volume DESC)
lag(value, 1) OVER (PARTITION BY id ORDER BY time)   -- Previous row value
lead(value, 1) OVER (PARTITION BY id ORDER BY time)  -- Next row value
sum(amount) OVER (ORDER BY event_date)                -- Running total
```

### Common Patterns

```sql
-- Top N
SELECT chain, uniq(wallet) as wallets
FROM events
GROUP BY chain
ORDER BY wallets DESC
LIMIT 10

-- Daily time series
SELECT toStartOfDay(event_time) as day, count() as events
FROM events
WHERE event_date >= today() - 30
GROUP BY day
ORDER BY day

-- Segment comparison
SELECT
  chain,
  countIf(event_type = 'transfer') as transfers,
  countIf(event_type = 'swap') as swaps,
  uniqIf(wallet, event_type = 'transfer') as transfer_wallets
FROM events
GROUP BY chain
```

## Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Process response |
| 202 | Accepted (async) | Poll for results |
| 400 | Bad request | Check query syntax or request body |
| 401 | Unauthorized | Verify `METABASE_API_KEY` |
| 403 | Forbidden | Check permissions for the resource |
| 404 | Not found | Verify resource ID exists |
| 500 | Server error | Check query for ClickHouse errors in response body |

**Common error patterns:**

| Error Message | Likely Cause | Fix |
|--------------|--------------|-----|
| `"Unknown table"` | Wrong database or schema | Re-run schema discovery |
| `"Memory limit exceeded"` | Query too broad | Add WHERE clauses, reduce date range, add LIMIT |
| `"Timeout"` | Query too slow | Simplify aggregations, check table size |
| `"Permission denied"` | API key lacks access | Check key permissions in Metabase admin |

## Troubleshooting

| Issue | Action |
|-------|--------|
| Can't find ClickHouse database | Run `GET /api/database/` and look for `engine: "clickhouse"` |
| Query returns no results | Check schema/table names match exactly (case-sensitive in ClickHouse) |
| Dashboard cards show errors | Verify card queries work standalone via `/api/dataset/` |
| Stale schema cache | Delete `data/cache/schema-*.json` and re-run discovery |
| Dashboard layout broken | Ensure dashcard positions don't overlap and total `col + size_x <= 24` |
| Public link returns 403 | Public sharing may be disabled — check Metabase admin settings |
| `dataset` field ignored | Use `type: "question"` or `type: "model"` instead (deprecated) |
| Dashcard query fails on dashboard | Use `/api/dashboard/{id}/dashcard/{dc}/card/{c}/query` with parameters |
