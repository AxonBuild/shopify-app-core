"""
ingest_from_json.py
───────────────────
Reads the flat products.json and indexes every product into Meilisearch.

Each document gets:
  • _vectors.text  – OpenAI embedding of "Title | Type | Tags"  (1536-dim, text-embedding-3-small)
  • _vectors.image – SigLIP embedding of the product image URL  (768-dim)

Filterable metadata stored alongside:
  • color, size, price, handle, sku, image_url

Usage (run from the repo root):
    python ingest_from_json.py                        # uses products.json
    python ingest_from_json.py --file my_products.json
    python ingest_from_json.py --limit 50             # embed only first N products
    python ingest_from_json.py --skip-images          # text-only (faster for testing)
"""

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup ─────────────────────────────────────────────────────────────────
# Add the backend folder so we can reuse EmbeddingService and settings as-is.
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config.settings import settings
from app.services.embedding_service import embedding_service
from app.services.image_caption_service import image_caption_service

import meilisearch

# ── Config ─────────────────────────────────────────────────────────────────────
INDEX_NAME   = settings.meilisearch_index   # "products" by default
BATCH_SIZE   = 50                           # upload N docs per Meilisearch call
TEXT_DIM     = 1536                         # OpenAI text-embedding-3-small


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_text(product: Dict[str, Any]) -> str:
    """
    Build the unified search string used for both:
      - OpenAI text embedding (semantic vector)
      - Meilisearch full-text search (the ONLY searchable field)

    If body_html is missing/empty, falls back to OpenAI Vision captioning
    the product image, passing structured metadata as grounding context.
    """
    title  = (product.get("Title")  or "").strip()
    color  = (product.get("Color")  or "").strip()
    p_type = (product.get("Type")   or "").strip()
    size   = (product.get("Size")   or "").strip()

    # ── 1. Try body_html first ────────────────────────────────────────────────
    body_html  = (product.get("body_html") or product.get("Body (HTML)") or "").strip()
    clean_html = re.sub('<[^<]+>', ' ', body_html).strip()
    # Filter stale HTML comments like "<!---->"
    clean_html = re.sub(r'<!--.*?-->', '', clean_html).strip()

    if clean_html:
        return f"Title: {title}. Description: {clean_html}"

    # ── 2. No description — fall back to Vision captioning ────────────────────
    image_url = (product.get("Image_Src") or "").strip()
    # Image_Src can be comma-separated; take only the first URL
    if "," in image_url:
        image_url = image_url.split(",")[0].strip()

    if image_url:
        # Filter Tags: skip pure-sale/discount tags, keep meaningful ones
        raw_tags = (product.get("Tags") or "").strip()
        useful_tags = [
            t.strip() for t in raw_tags.split(",")
            if t.strip()
            and not any(kw in t.lower() for kw in [
                "sale", "discount", "flat", "off", "upload", "grade", "azadi",
                "eidi", "all category", "ref!", "summer", "winter",
            ])
        ]
        tags_str = ", ".join(useful_tags[:10])  # cap at 10 to avoid prompt bloat

        product_context = (
            f"- Title : {title}\n"
            f"- Type  : {p_type}\n"
            f"- Color : {color}\n"
            f"- Sizes : {size}\n"
            + (f"- Tags  : {tags_str}\n" if tags_str else "")
        )

        print(f"  [Captioner] No description for '{title}' — generating from image + metadata...")
        caption = image_caption_service.caption_image(image_url, product_context=product_context)
        if caption:
            return f"Title: {title}. Description: {caption}"

    # ── 3. No image either — build a minimal text from metadata ───────────────
    parts = [f"Title: {title}."]
    if p_type:
        parts.append(f"Type: {p_type}.")
    if color:
        parts.append(f"Color: {color}.")
    if size:
        parts.append(f"Available sizes: {size}.")
    return " ".join(parts)


def safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def make_doc_id(product: Dict[str, Any]) -> str:
    """Stable, Meilisearch-safe ID from Variant_SKUs (or Handle+Color+Size)."""
    sku = (product.get("Variant_SKUs") or "").strip()
    if sku:
        # Replace anything that isn't alphanumeric/dash/underscore
        return re.sub(r"[^a-zA-Z0-9_\-]", "_", sku)
    handle = product.get("Handle", "unknown")
    color  = product.get("Color",  "x")
    size   = product.get("Size",   "x")
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", f"{handle}_{color}_{size}")


# ──────────────────────────────────────────────────────────────────────────────
# Meilisearch index setup
# ──────────────────────────────────────────────────────────────────────────────

def configure_index(client: meilisearch.Client):
    """Create the index (if needed) and configure embedders + filterable attrs."""
    # Create index
    try:
        client.get_index(INDEX_NAME)
        print(f"[index] Using existing index '{INDEX_NAME}'")
    except meilisearch.errors.MeilisearchApiError:
        task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid)
        print(f"[index] Created index '{INDEX_NAME}'")

    index = client.get_index(INDEX_NAME)

    task = index.update_settings({
        "embedders": {
            "text": {"source": "userProvided", "dimensions": TEXT_DIM},
        },
        "filterableAttributes": [
            "color",
            "size",
            "price",
            "price_min",
            "price_max",
            "handle",
        ],
        "searchableAttributes": [
            "search_text",   # the ONLY field Meilisearch full-text searches
        ],
    })
    client.wait_for_task(task.task_uid)
    print("[index] Settings updated ✓")
    return index


# ──────────────────────────────────────────────────────────────────────────────
# Upload helper
# ──────────────────────────────────────────────────────────────────────────────

def upload_batch(index, docs: List[Dict[str, Any]], client: meilisearch.Client):
    task = index.add_documents(docs)
    client.wait_for_task(task.task_uid, timeout_in_ms=120_000)


# ──────────────────────────────────────────────────────────────────────────────
# Main ingestion loop  (3 phases)
# ──────────────────────────────────────────────────────────────────────────────

def ingest(json_path: Path, limit: Optional[int]):
    print(f"\n{'─'*60}")
    print(f"  Source : {json_path}")
    print(f"  Index  : {INDEX_NAME}  @ {settings.meilisearch_url}")
    print(f"  Images : disabled (text-only mode)")
    print(f"{'─'*60}\n")

    # Load products
    with open(json_path, "r", encoding="utf-8") as f:
        all_products: List[Dict[str, Any]] = json.load(f)

    # ── Filter: keep only products that have a usable description ────────────
    # Products without body_html are skipped for now (no Vision captioning).
    def has_description(p: Dict[str, Any]) -> bool:
        raw = (p.get("body_html") or p.get("Body (HTML)") or "").strip()
        # Strip HTML tags and HTML comments
        clean = re.sub(r'<!--.*?-->', '', re.sub('<[^<]+>', ' ', raw)).strip()
        return bool(clean)

    valid_products   = [p for p in all_products if has_description(p)]
    skipped_no_desc  = len(all_products) - len(valid_products)

    if limit:
        products = valid_products[:limit]
    else:
        products = valid_products

    total   = len(products)
    print(f"Loaded {len(all_products)} products from JSON.")
    if skipped_no_desc:
        print(f"  ⏭️  Skipped {skipped_no_desc} products with no body description.")
    print(f"  ✅  Indexing {total} products with valid descriptions.\n")

    # Connect to Meilisearch
    client = meilisearch.Client(settings.meilisearch_url, settings.meilisearch_master_key)
    try:
        client.health()
    except Exception as e:
        print(f"❌  Cannot reach Meilisearch at {settings.meilisearch_url}: {e}")
        sys.exit(1)

    index = configure_index(client)

    # ── Pre-extract all fields once ───────────────────────────────────────────
    rows = []
    for p in products:
        price = safe_float(p.get("Price"))
        rows.append({
            "id":          make_doc_id(p),
            "handle":      (p.get("Handle")       or "").strip(),
            "sku":         (p.get("Variant_SKUs")  or "").strip(),
            "title":       (p.get("Title")         or "").strip(),
            "type":        (p.get("Type")          or "").strip(),
            "color":       (p.get("Color")         or "").strip(),
            "size":        (p.get("Size")          or "").strip(),
            "price":       price,
            "price_min":   safe_float(p.get("Price_Min")) or price,
            "price_max":   safe_float(p.get("Price_Max")) or price,
            "image_url":   (p.get("Image_Src")     or "").strip() or None,
            "search_text": build_text(p),
        })

    # ── PHASE 1 — Batch text embeddings (OpenAI) ──────────────────────────────
    print(f"[Phase 1/3] Text embeddings via OpenAI ({total} products)…")
    TEXT_CHUNK = 100          # safe chunk size; OpenAI supports up to 2048
    text_vectors: List[Optional[List[float]]] = []

    for start in range(0, total, TEXT_CHUNK):
        chunk = [r["search_text"] for r in rows[start : start + TEXT_CHUNK]]
        end   = min(start + TEXT_CHUNK, total)
        print(f"  [{start+1}–{end}] …", end=" ", flush=True)
        try:
            vecs = embedding_service.embed_text(chunk)   # list → List[List[float]]
            text_vectors.extend(vecs)
            print("✓")
        except Exception as e:
            print(f"❌  ({e})")
            text_vectors.extend([None] * len(chunk))     # keep indices aligned

    # ── PHASE 2 — Image embeddings removed (text-only mode) ──────────────────
    print(f"\n[Phase 2/2] Skipped — image search disabled.")


    # ── PHASE 3 — Assemble documents and upload ───────────────────────────────
    print(f"\n[Phase 3/3] Assembling and uploading to Meilisearch…")
    docs_batch: List[Dict[str, Any]] = []
    skipped = 0

    for i, row in enumerate(rows):
        tv = text_vectors[i]

        if tv is None:
            print(f"  ⚠️  [{i+1}] No text vector — skipping '{row['title']}'")
            skipped += 1
            continue

        doc: Dict[str, Any] = {
            "id":          row["id"],
            "handle":      row["handle"],
            "sku":         row["sku"],
            "search_text": row["search_text"],
            "title":       row["title"],
            "type":        row["type"],
            "color":       row["color"],
            "size":        row["size"],
            "price":       row["price"],
            "price_min":   row["price_min"],
            "price_max":   row["price_max"],
            "image_url":   row["image_url"],
            "_vectors":    {"text": tv},
        }
        docs_batch.append(doc)

        if len(docs_batch) >= BATCH_SIZE:
            print(f"  → Uploading batch of {len(docs_batch)} docs…", end=" ", flush=True)
            upload_batch(index, docs_batch, client)
            docs_batch = []
            print("✓")

    if docs_batch:
        print(f"  → Uploading final batch of {len(docs_batch)} docs…", end=" ", flush=True)
        upload_batch(index, docs_batch, client)
        print("✓")

    print(f"\n{'─'*60}")
    print(f"  ✅  Ingestion complete.")
    print(f"  Indexed : {total - skipped} / {total}")
    print(f"  Skipped : {skipped}")
    print(f"{'─'*60}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest products.json into Meilisearch")
    parser.add_argument(
        "--file", type=Path,
        default=SCRIPT_DIR / "products.json",
        help="Path to the products JSON file (default: products.json)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N products (useful for testing)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"❌  File not found: {args.file}")
        sys.exit(1)

    ingest(args.file, args.limit)
