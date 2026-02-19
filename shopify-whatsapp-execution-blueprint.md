# Shopify + WhatsApp AI Commerce Execution Blueprint

## Product Goal
Build a WhatsApp-first AI commerce app for Shopify that improves:
- Product discovery conversion
- Support resolution speed
- Repeat purchase rate

Primary wedge:
- Conversational Product Finder with smart recommendations

---

## Overall Execution Plan (Unified Scope)

Build all scoped features under one integrated plan, executed through parallel workstreams with clear dependencies.

## Workstream A: Platform Foundation
**Goal**
- Establish reliable Shopify + WhatsApp integration and production-ready backend foundations.

**Includes**
- Shopify app install/OAuth and token management
- Shopify webhooks ingestion (products, inventory, orders, fulfillments)
- WhatsApp webhook receive/send pipeline
- Idempotency, retries, queueing, and observability

**Deliverable**
- Stable event-driven backbone where all user and commerce events are captured and processed safely.

## Workstream B: Catalog Intelligence and Retrieval
**Goal**
- Power high-quality product discovery in chat.

**Includes**
- Catalog normalization from Shopify to internal schema
- Meilisearch indexing (full-text + embeddings)
- Query classifier (`color`, `size`, `price`, `category`, intent)
- Hybrid retrieval + constraint filters + ranking

**Deliverable**
- Conversational Product Finder returning relevant, in-stock, price-aware results with media and links.

## Workstream C: Commerce AI Experiences
**Goal**
- Deliver complete customer-facing experiences across discovery, support, retention, and lead management.

**Includes**
- Conversational Product Finder
- Purchase-history-aware recommendations
- AI Support and Policy Agent (FAQ + returns + policy)
- Shopify order status flow
- Post-purchase automation (feedback/review/reorder nudges)
- Multimodal search (voice/image) for product matching
- CRM integration using Google Sheets (lead status, notes, tags, custom fields)

**Deliverable**
- End-to-end WhatsApp commerce assistant covering pre-purchase, purchase support, and post-purchase engagement.

## Workstream D: Measurement and Optimization
**Goal**
- Make performance measurable and improve outcomes continuously.

**Includes**
- Event taxonomy (`query_received`, `result_clicked`, `purchase_attributed`, `faq_resolved`)
- Attribution logic (message -> click -> order)
- KPI dashboard (conversion, deflection, repeat purchase, response time, lead pipeline movement)
- Prompt tuning and ranking optimization loop

**Deliverable**
- Clear ROI visibility for merchants and a feedback loop for model and product improvement.

## Cross-Workstream Dependency Order
1. Platform Foundation starts first and runs continuously.
2. Catalog Intelligence starts once Shopify data sync is live.
3. Commerce AI Experiences layer on top of retrieval and policy/order data access.
4. Measurement and Optimization is integrated from day one and expanded as features go live.

## Success Criteria for the Overall Plan
- Product discovery: higher search-to-click and click-to-purchase rates
- Support: lower repetitive query burden and higher self-service completion
- Retention: improved repeat purchase and review capture
- CRM: improved lead qualification and follow-up completion
- Reliability: low failure rate for webhooks/jobs and acceptable response latency

---

## End-to-End Integration Architecture

## 1) Channels and APIs
- **WhatsApp layer:** WhatsApp Business API (Cloud API or BSP)
- **Commerce layer:** Shopify Admin API + Webhooks
- **App backend:** API service handling conversation orchestration and business logic
- **Search layer:** Meilisearch (full-text + vector/embedding retrieval)
- **AI layer:** LLM for intent parsing, ranking, response generation

## 2) Core Services
- **Webhook Ingestion Service**
  - Shopify webhooks: products, inventory, orders, fulfillments
  - WhatsApp message webhooks: incoming text/voice/image events
- **Catalog Sync Service**
  - Normalizes Shopify catalog into search documents
  - Keeps Meilisearch index fresh (incremental updates)
- **Conversation Orchestrator**
  - Classifies user intent: `product_search`, `support`, `order_status`, `other`
  - Maintains short session memory (recent user preferences)
- **Recommendation Engine**
  - Uses purchase history + behavior signals
  - Produces cross-sell/reorder prompts
- **Policy/Support Retrieval**
  - Ingests text, file, and URL sources
  - Retrieves relevant passages for grounded responses
- **CRM Sync Service (Google Sheets)**
  - Pushes lead/contact records and interaction summaries
  - Supports lead labels (`first_time`, `returning`), notes, tags, and custom fields
- **Analytics/Attribution Service**
  - Tracks message -> click -> order journey
  - Reports conversion and revenue contribution

---

## Search and Retrieval Design (Meilisearch)

## Product document schema (suggested)
- `product_id`
- `title`
- `description`
- `category`
- `tags`
- `price_min`, `price_max`
- `sizes[]`
- `colors[]`
- `image_urls[]`
- `availability`
- `embedding` (text/image representation)

## Query understanding schema (incoming classifier)
```json
{
  "intent": "product_search",
  "color": "red",
  "size": "L",
  "price_min": 1000,
  "price_max": 5000,
  "category": "shoes",
  "sort_preference": "best_match"
}
```

## Retrieval strategy
1. Parse constraints from user query.
2. Run lexical + semantic retrieval in Meilisearch.
3. Filter by hard constraints (price range, size, stock).
4. Re-rank by relevance + margin/business rules.
5. Return top 3-5 products with concise explanation.

---

## Shopify Integration Plan

## OAuth and app setup
- Implement Shopify app install + OAuth
- Store shop access tokens securely

## Required Shopify data access (high level)
- Products/variants/images/inventory
- Orders and fulfillments
- Customers (for purchase history-based recommendations)

## Webhooks to subscribe
- Product updates
- Inventory updates
- Order creation/updates
- Fulfillment events

## Operational safeguards
- Idempotent webhook handlers
- Retry queue for failed sync jobs
- Rate-limit aware Shopify API client

---

## WhatsApp Integration Plan

## Message handling
- Verify webhook signature and parse message payloads
- Support text, voice, and image inputs within the same product scope

## Response patterns
- Product cards (image, price, short CTA)
- Quick-reply style prompts for filters
- Human handoff fallback when low confidence

## Guardrails
- Confidence thresholds for generated replies
- Safe fallback for unknown or ambiguous queries
- Regional language support roadmap (English + Urdu/Roman Urdu)

---

## CRM Integration Plan (Google Sheets)

## CRM data model (sheet columns)
- `lead_id`
- `phone_number`
- `name`
- `lead_type` (`first_time`, `returning`, `high_intent`)
- `last_intent`
- `last_interaction_at`
- `tags` (comma separated or structured)
- `notes`
- `custom_fields_json`
- `assigned_owner` (optional)
- `next_followup_at` (optional)

## CRM workflows
1. Create/update lead row on first WhatsApp interaction.
2. Update lead type based on purchase history and behavior signals.
3. Append notes after meaningful conversations (support, product inquiry, complaint).
4. Add tags from classifier and agent outcomes (e.g., `hot_lead`, `needs_size_help`).
5. Store custom fields for merchant-specific workflows.

## Operational rules
- Use upsert logic keyed by `phone_number` or `lead_id`.
- Queue writes to avoid API throttling and lost updates.
- Keep an interaction audit trail in app storage if sheet write fails temporarily.

---

## Feature-by-Feature Execution Table

| Feature | Merchant Value | User Flow | Data Needed | KPI | Complexity |
| --- | --- | --- | --- | --- | --- |
| Conversational Product Finder | Better product discovery conversion | Query -> classify -> retrieve -> recommend | Product catalog + inventory | Search-to-click | M |
| Purchase-History Recommendations | Higher AOV/repeat purchase | Detect returning user -> suggest relevant items | Customer orders/history | Recommendation CTR | M |
| AI Support & Policy Agent | Ticket deflection | Ask FAQ/order -> grounded answer -> fallback | Policy KB + order status | Deflection rate | M |
| Post-Purchase Automation | Increased retention | Delivery -> feedback/review -> reorder prompts | Fulfillment + lifecycle timing | Repeat purchase rate | M |
| Multimodal Search (Voice/Image) | Premium experience + intent quality | Upload VN/image -> extract intent -> match products | CLIP-like embeddings + catalog media | Multimodal conversion | H |
| CRM Integration (Google Sheets) | Better lead follow-up and sales visibility | Conversation -> classify lead -> sync labels/notes/tags/custom fields | WhatsApp identity + behavior signals + order history | Lead progression and follow-up completion | M |

---

## Execution Milestones (Overall Program)

## Milestone 1: Integration Ready
- Shopify OAuth + webhooks operational
- WhatsApp webhook receive/send operational
- Core monitoring, retry, and idempotency safeguards in place

## Milestone 2: Discovery and Retrieval Ready
- Catalog sync stable and searchable in Meilisearch
- Query classifier and hybrid retrieval producing quality results
- Product cards with image/price/link returned in WhatsApp

## Milestone 3: Support and Order Assistance Ready
- Policy/FAQ knowledge ingestion live (text/file/URL)
- Grounded support responses live with fallback handoff
- Order status retrieval live via Shopify integration

## Milestone 4: Retention and Multimodal Ready
- Post-purchase automations active (feedback/review/reorder)
- Voice and image query ingestion and matching active
- Measurement dashboards reflect full-funnel behavior

## Milestone 5: CRM Operations Ready
- Google Sheets CRM sync live with upsert and retry logic
- Lead labels, notes, tags, and custom fields auto-updated from conversations
- Lead pipeline reporting visible in dashboard

---

## Pilot Rollout Checklist
- 3-5 pilot stores selected
- Baseline metrics captured before launch
- Weekly KPI review (clicks, conversion, support deflection, repeats, lead movement)
- Merchant feedback loop and prompt tuning
- Production-readiness checks (monitoring, retries, alerts)

---

## Risks and Mitigations
- **Noisy product metadata**
  - Add normalization and fallback heuristics for color/size extraction
- **Slow responses under load**
  - Cache frequent queries and precompute embeddings
- **Attribution ambiguity**
  - Define clear attribution window and event taxonomy early
- **Hallucinated support answers**
  - Restrict answers to retrieved policy chunks + confidence threshold
- **CRM data inconsistency**
  - Enforce sheet schema validation and deterministic upsert keys

---

## Delivery Principle
Implement as one unified program with dependency-aware sequencing and shared analytics, not as disconnected MVP phases. This keeps architecture coherent while still allowing progressive go-live by milestone.
