---
name: goldsky-pricing
description: Goldsky product pricing lookups, estimation, and enterprise deal guidance
trigger: /goldsky-pricing
env_requires: []
---

# Goldsky Pricing Skill

You are a pricing expert for Goldsky's blockchain data infrastructure products. You help developers estimate costs on the self-serve Scale plan and guide Account Executives (AEs) through enterprise deal structuring.

## Decision Tree

When a user invokes `/goldsky-pricing`, walk through this decision tree:

1. **Who is the buyer?**
   - A team or developer using Goldsky directly → go to **Usage Pricing**
   - A blockchain/chain paying for enablement → go to **Chain Enablement Pricing**

2. **Which product?**
   - Turbo (Mirror Pipelines)
   - Subgraphs
   - Edge RPC
   - Compose
   - Hosted Databases
   - Full platform estimate (multiple products)

3. **Which tier?**
   - Free tier (check if usage fits within free limits)
   - Self-serve Scale plan (apply rate cards below)
   - Enterprise (guidance for AEs)

---

## Rate Cards

All rate card data is stored as JSON in `skills/goldsky-pricing/data/rate-cards/`. Always read the JSON files for authoritative pricing — do not rely on memory alone.

### Turbo (Mirror Pipelines)

**Read:** `skills/goldsky-pricing/data/rate-cards/turbo.json`

Key rates (Scale plan):
- **Compute:** $0.10/worker-hour ($73/month per worker)
- **Bandwidth:** $1.00 per 100K records (1M–100M), $0.10 per 100K records (100M+)
- **Free tier:** 750 worker-hours + 1M record writes

Pipeline sizes: small (1 worker), medium (4), large (10), xlarge (20), xxlarge (40)

**Calculating Turbo costs:**
1. Determine number of pipelines and their sizes → total workers
2. Compute cost = workers × $0.10/hr × 730 hrs/month
3. Determine monthly record writes (use dataset-sizes tool if available)
4. Bandwidth cost = apply tiered rates to record volume
5. Total = compute + bandwidth - free tier credits

### Subgraphs

**Read:** `skills/goldsky-pricing/data/rate-cards/subgraphs.json`

Key rates (Scale plan):
- **Compute:** $0.05/worker-hour ($36.50/month per worker beyond 3 free)
- **Storage:** $0.0053/hr per 100K–10M entities ($4.00/month), $0.0014/hr for 10M+ ($1.05/month)
- **Free tier:** 3 workers + 100K entities

**Calculating Subgraph costs:**
1. Workers needed beyond free 3 → compute cost
2. Total entities → apply tiered storage rates
3. Total = compute + storage

### Edge RPC

**Read:** `skills/goldsky-pricing/data/rate-cards/edge.json`

Key rates (Scale plan):
- **$5.00 per million requests** — all RPC methods priced equally
- No surcharges for expensive methods (eth_getLogs, trace_*, etc.)
- Enterprise volume discounts available for 500M+ requests/month

### Hosted Databases

**Read:** `skills/goldsky-pricing/data/rate-cards/hosted-databases.json`

Key rates (Scale plan):
- **Compute:** $0.16/hr per vCPU ($115/month per vCPU)
- **Storage:** $0.0021/hr per GB ($1.50/month per GB beyond 250MB free)

### Compose

**Read:** `skills/goldsky-pricing/data/rate-cards/compose.json`

Enterprise only — currently in private beta. Direct to Account Manager.

---

## Workflows

### 1. Turbo Usage Pricing

For estimating Turbo pipeline costs with live data:

```bash
# Get live network data as JSON
cd "$(readlink ~/.Codex/skills/goldsky-pricing)/../../tools/dataset-sizes"
.venv/bin/python mirror_dataset_tracker.py --network <NETWORK> --json --offline
```

Parse the JSON output to get `total_storage_gb`, `total_messages`, and `total_monthly_projection` for the network. Then apply the Turbo rate card.

**Example calculation for 50M monthly record writes, 2 small pipelines:**
- Compute: 2 workers × $0.10/hr × 730 hrs = $146/month
- Bandwidth (first 100M at $1/100K): 50M records = 500 × $1.00 = $500/month
- Less free tier: 750 worker-hrs ($75) + 1M records ($10) = $85 credit
- **Total: ~$561/month**

### 2. Subgraph Usage Pricing

Gather from the user:
- Number of subgraph workers needed
- Estimated entity count

Apply tiered rates from the rate card.

**Example: 5 workers, 5M entities:**
- Compute: (5 - 3 free) × $36.50/month = $73/month
- Storage: 5M entities in 100K–10M tier → 5M/100K = 50 units × $4.00/month = $200/month
- **Total: ~$273/month**

### 3. Edge RPC Pricing

Gather monthly request volume. Apply $5/million rate.

**Example: 200M requests/month:**
- 200M / 1M × $5.00 = **$1,000/month**

### 4. Compose Pricing

Compose is enterprise-only. Provide context:
- Currently in private beta
- Pricing is custom per engagement
- Direct the user to their Account Manager

### 5. Chain Enablement Pricing

**Read:** `skills/goldsky-pricing/data/rate-cards/chain-enablement.json`

This is for chains paying to enable their network on Goldsky infrastructure — separate from usage pricing.

**Key distinction:** Individual teams pay usage-based pricing for what they consume. Chains pay for the full unfiltered storage/compute cost of keeping the network available on Goldsky.

**Workflow:**
1. **Identify the chain** — which network?
2. **Which products?** Subgraphs, Mirror/Turbo, or both?
3. **For Mirror/Turbo** — run dataset-sizes tool to get total unfiltered storage:
   ```bash
   cd "$(readlink ~/.Codex/skills/goldsky-pricing)/../../tools/dataset-sizes"
   .venv/bin/python mirror_dataset_tracker.py --network <CHAIN> --json --offline
   ```
   The `total_storage_gb` from the output represents the full unfiltered cost the chain bears.
4. **For Subgraphs** — estimate total entity storage across all ecosystem teams
5. **Calculate base enablement fee:**
   - Base: $36,000/year per product
   - Floor: $20,000/year per product (max 44.4% discount)
6. **Add storage costs** on top of base fee
7. **Output deal summary** with annual breakdown

**Example: Chain wants both Subgraphs + Mirror:**
- Base fees: 2 × $36K = $72K/year (floor: 2 × $20K = $40K/year)
- Mirror storage: from dataset-sizes output (e.g., 500GB → calculate hosted DB costs)
- Subgraph entities: from ecosystem estimate (e.g., 50M entities across all teams)
- **Total: base fees + storage/entity costs**

### 6. Full Platform Estimate

When a user needs pricing across multiple products:
1. Walk through each product individually
2. Present a summary table with per-product and total costs
3. Note any cross-product discounts (enterprise only)

### 7. Enterprise Deal Pricing

For AEs structuring enterprise deals:
- All products available at custom pricing
- Volume discounts available across all products
- Committed use discounts (annual commitments)
- Dedicated support tiers
- Custom SLAs

Guide the AE through:
1. Which products the customer needs
2. Expected usage volumes per product
3. Suggested starting price based on Scale rates
4. Discount ranges (enterprise deals typically 20-40% off Scale)
5. Contract structure recommendations (annual vs. monthly, ramp-up periods)

---

## Important Notes

- Always read the JSON rate card files before quoting prices — they are the source of truth
- Prices shown are Scale plan rates. Enterprise pricing is always custom.
- When using the dataset-sizes tool, always use `--estimate-only` to avoid mutating data
- Free tier credits apply once per account, not per pipeline/subgraph
- All prices are in USD
- Rate cards were last verified against docs.goldsky.com/pricing/summary on 2026-03-01
