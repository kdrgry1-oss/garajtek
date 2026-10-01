"""
Export products, categories and orders from the store database (localdb/SQLite) to JSON files for GitHub.
"""
import asyncio
import json
import os
from datetime import datetime

async def main():
    from dotenv import load_dotenv
    load_dotenv()
    # Uygulamayla AYNI veritabanı: gömülü localdb (DB_PATH) — DB_BACKEND=mongo + MONGO_URL
    # verilirse eski Motor/MongoDB bağlantısı kullanılır.
    from localdb import make_client

    DB_NAME = os.getenv("DB_NAME", "test_database")

    client = make_client()
    db = client[DB_NAME]

    output_dir = os.path.join(os.path.dirname(__file__), "..", "data_export")
    os.makedirs(output_dir, exist_ok=True)

    collections = ["products", "categories", "orders", "banners", "settings", "trendyol_category_mappings"]

    for col_name in collections:
        docs = await db[col_name].find({}, {"_id": 0}).to_list(None)
        path = os.path.join(output_dir, f"{col_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2, default=str)
        print(f"[OK] {col_name}: {len(docs)} kayıt -> {path}")

    client.close()
    print(f"\nTüm veriler data_export/ klasörüne aktarıldı.")

if __name__ == "__main__":
    asyncio.run(main())
