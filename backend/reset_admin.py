import asyncio
import bcrypt
import os

# Uygulamayla AYNI veritabanı (routes/deps.py ile aynı mantık): gömülü localdb (DB_PATH);
# yalnız DB_BACKEND=mongo + MONGO_URL verilirse Motor/MongoDB.
# NOT: localdb tek-süreçlidir — bu betiği uygulama DURDURULMUŞKEN çalıştırın.
from localdb import make_client

db_name = os.environ.get('DB_NAME', 'test_database')

async def reset():
    client = make_client()
    db = client[db_name]
    
    # GÜVENLİK: sabit "admin123" varsayılanı kaldırıldı. ADMIN_RESET_PASSWORD env
    # zorunlu; verilmezse betik hiçbir şey yapmadan durur (zayıf parola dayatılmaz).
    new_password = os.environ.get("ADMIN_RESET_PASSWORD", "").strip()
    if len(new_password) < 10:
        print("HATA: ADMIN_RESET_PASSWORD ortam değişkeni (>=10 karakter) gerekli. İşlem iptal.")
        return
    admin_email = (os.environ.get("ADMIN_INITIAL_EMAIL") or "").strip().lower()
    if not admin_email:
        print("HATA: ADMIN_INITIAL_EMAIL ortam değişkeni (yönetici e-postası) gerekli. İşlem iptal.")
        return
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    
    result = await db.users.update_one(
        {"email": admin_email},
        {"$set": {"password": hashed}},
        upsert=False
    )
    
    if result.matched_count == 0:
        # Admin user doesn't exist, create it
        import uuid
        from datetime import datetime, timezone
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password": hashed,
            "first_name": "Admin",
            "last_name": "User",
            "is_admin": True,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"Admin user CREATED: {admin_email} (parola ADMIN_RESET_PASSWORD ile ayarlandı)")
    else:
        print(f"Admin password RESET. Matched: {result.matched_count}, Modified: {result.modified_count}")
        print(f"Login: {admin_email} (parola ADMIN_RESET_PASSWORD ile ayarlandı)")
    client.close()

if __name__ == "__main__":
    asyncio.run(reset())
