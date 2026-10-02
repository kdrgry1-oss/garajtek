"""
Import data from data_export/ JSON files into the store database (localdb/SQLite).
Usage: python3 import_data.py
"""
import asyncio
import json
import os

async def main():
    from dotenv import load_dotenv
    load_dotenv()
    # Uygulamayla AYNI veritabanı: gömülü localdb (DB_PATH) — DB_BACKEND=mongo + MONGO_URL
    # verilirse eski Motor/MongoDB bağlantısı kullanılır.
    from localdb import make_client

    DB_NAME = os.getenv("DB_NAME", "test_database")

    client = make_client()
    db = client[DB_NAME]

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data_export")
    collections = ["products", "categories", "orders", "banners", "settings"]

    for col_name in collections:
        path = os.path.join(data_dir, f"{col_name}.json")
        if not os.path.exists(path):
            print(f"[SKIP] {col_name}: dosya bulunamadı")
            continue
        with open(path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        if not docs:
            print(f"[SKIP] {col_name}: veri yok")
            continue
        # Insert - skip existing by id
        inserted = 0
        for doc in docs:
            try:
                await db[col_name].update_one(
                    {"id": doc["id"]} if "id" in doc else {"_id": doc.get("_id")},
                    {"$setOnInsert": doc},
                    upsert=True
                )
                inserted += 1
            except Exception as e:
                print(f"  [!] Atlandı: {e}")
        print(f"[OK] {col_name}: {inserted}/{len(docs)} kayıt işlendi")

    client.close()
    print("\nİçe aktarma tamamlandı.")

if __name__ == "__main__":
    asyncio.run(main())
