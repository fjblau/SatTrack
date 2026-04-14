#!/usr/bin/env python3
"""
Enrich registration_documents collection with resolved English document links.

For each document, fetches the UNOOSA page and scrapes the English link,
then persists it as `english_link` on the document so the frontend can
display direct links without live scraping on every click.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from api.services.document_service import fetch_english_doc_link

BATCH_SIZE = 50
RATE_LIMIT_DELAY = 0.5  # seconds between requests to avoid hammering UNOOSA


def main():
    db_conn.connect_arangodb()
    db = db_conn.db
    collection = db.collection(db_conn.COLLECTION_REG_DOCS)

    total = collection.count()
    print(f"Found {total} registration documents to process")

    cursor = db.aql.execute(
        f"FOR doc IN {db_conn.COLLECTION_REG_DOCS} RETURN {{ _key: doc._key, url: doc.url, english_link: doc.english_link }}",
        batch_size=BATCH_SIZE,
    )

    processed = 0
    updated = 0
    skipped = 0
    failed = 0

    for doc in cursor:
        key = doc["_key"]
        url = doc.get("url", "")

        if doc.get("english_link"):
            skipped += 1
            processed += 1
            if processed % 50 == 0:
                print(f"  [{processed}/{total}] skipped (already have link): {url}")
            continue

        if not url:
            failed += 1
            processed += 1
            continue

        try:
            english_link = fetch_english_doc_link(url)
            time.sleep(RATE_LIMIT_DELAY)

            collection.update({"_key": key, "english_link": english_link})

            if english_link:
                updated += 1
                status = f"✓ {english_link[:80]}"
            else:
                failed += 1
                status = "✗ no link found"

            processed += 1
            print(f"  [{processed}/{total}] {url} → {status}")

        except Exception as e:
            failed += 1
            processed += 1
            print(f"  [{processed}/{total}] ERROR {url}: {e}")

    print(f"\nDone: {updated} updated, {skipped} already had links, {failed} failed/not found")


if __name__ == "__main__":
    main()
