"""Shipping eligibility is based on merchandise after discounts, never charges.

Gift cards/store credit are payment instruments, not merchandise discounts.
The threshold is supplied by settings/campaigns; no tenant amount is hardcoded.
"""
from decimal import Decimal, ROUND_HALF_UP


def match_shipping_rule(rules, cart_total):
    """Panel › Kargo Kuralları (db.shipping_rules) içinden sepet tutarına uyan kuralı döndürür.
    En yüksek min_cart'lı uyan kural kazanır (eski /admin/rules/shipping/resolve ile aynı).
    Taban = ARA TOPLAM (ürün tutarı, indirim öncesi) — vitrin (lib/shippingRules.js) ile aynı.
    Uyan kural yoksa None."""
    try:
        total = float(cart_total or 0)
    except (TypeError, ValueError):
        total = 0.0
    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0
    active = [r for r in (rules or []) if isinstance(r, dict) and r.get("is_active", True) is not False]
    for r in sorted(active, key=lambda r: _f(r.get("min_cart")), reverse=True):
        mx = _f(r.get("max_cart"))
        if total >= _f(r.get("min_cart")) and (not mx or total <= mx):
            return r
    return None


def shipping_quote(subtotal, discounts, threshold, fee, free_shipping_promotion=False, rules=None):
    """Kargo kararı — TEK KURAL (vitrin lib/shippingRules.js birebir aynısı):
      - Kargo kuralı (rules) eşleşirse: 'Kargo bedava' → ücretsiz; değilse ücret = kuralın ücreti.
      - Ücretsiz kargo EŞİĞİ: taban (ara toplam − kupon/kampanya indirimi − puan) ≥ eşik.
        Ödeme yöntemi indirimi (havale vb.) tabana GİRMEZ: aksi halde "indirimli" havale,
        ücretsiz kargoyu kaybettirip müşteriye sepetten PAHALIYA geliyordu.
      - Kupon/kampanya free_shipping bayrağı (eşiği belirleyen otomatik kampanya HARİÇ —
        bkz. promo_free_shipping) eşikten BAĞIMSIZ ücretsiz kargo verir. Eskiden eşik varken
        bayrak yok sayılıyordu → 'Kargo bedava' kuponu 'uygulandı' deyip kargoyu alıyordu."""
    money = lambda value: Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    basis = max(Decimal(0), money(subtotal) - sum((money(d) for d in discounts), Decimal(0)))
    rule = match_shipping_rule(rules, subtotal) if rules else None
    if rule is not None and not rule.get("free_shipping"):
        fee = rule.get("shipping_cost") or 0
    free = (bool(free_shipping_promotion) or bool(rule is not None and rule.get("free_shipping"))
            or (threshold is not None and basis >= money(threshold)))
    return {"basis": float(basis), "free": free, "cost": 0.0 if free else float(money(fee)),
            "fee": float(money(fee))}


# Bu alanlardan biri doluysa kampanya KOŞULLUDUR (ödeme yöntemi/kategori/ürün/ilk sipariş/
# kullanım limiti/kişiye özel/adet): genel ücretsiz kargo EŞİĞİNİ belirleyemez, yalnız kampanya
# motoru (coupons.evaluate_cart_promotions) koşulları doğrulayıp free_shipping bayrağı verir.
_THRESHOLD_RESTRICTING_FIELDS = (
    "payment_methods", "categories", "products", "first_order_only", "usage_limit",
    "usage_limit_per_user", "min_quantity", "reward_email", "reward_user_id",
)


def campaign_sets_threshold(c, now=None):
    """Bu kampanya genel (koşulsuz) ücretsiz kargo eşiğini mi belirler?
    KÖK SEBEP: eşik, TÜM otomatik free_shipping kampanyalarının en düşük min tutarından
    hesaplanıyordu → yalnız 'Kapıda ödeme' ya da yalnız 'Liftler' için açılan min 0 kampanya
    eşiği 0 yapıp HER sepete ücretsiz kargo veriyordu."""
    if not (c and c.get("is_active") and c.get("free_shipping") and c.get("auto_apply")):
        return False
    if any(c.get(k) for k in _THRESHOLD_RESTRICTING_FIELDS):
        return False
    return campaign_live(c, now)


def threshold_from_campaigns(campaigns, now=None):
    """Koşulsuz otomatik free_shipping kampanyalarının EN DÜŞÜK min tutarı (yoksa None)."""
    threshold = None
    for c in campaigns or []:
        if not campaign_sets_threshold(c, now):
            continue
        mc = c.get("min_cart_total")
        if mc in (None, ""):
            continue
        try:
            mc = float(mc)
        except (TypeError, ValueError):
            continue
        if threshold is None or mc < threshold:
            threshold = mc
    return threshold


def promo_free_shipping(applied):
    """Kampanya motoru sonucundan, EŞİKTEN BAĞIMSIZ ücretsiz kargo veren promosyon var mı?
    Eşiği belirleyen kampanya (threshold_campaign) sayılmaz — onun minimumu eşikle
    (puan düşülmüş taban) zaten uygulanır; bayrağı ayrıca sayılırsa eşik baypas edilirdi."""
    return any(bool(p.get("free_shipping")) and not p.get("threshold_campaign")
               for p in (applied or []) if isinstance(p, dict))


def campaign_live(c, now=None):
    """Is a campaign within its start/end window right now? Same rule as the
    coupon evaluator (routes/coupons.py): a date-only end_at is valid until the
    end of that day. The free-shipping threshold resolvers must use this — an
    `is_active` campaign past its end_at must NOT keep lowering the threshold."""
    from datetime import datetime, timezone
    now_iso = (now or datetime.now(timezone.utc)).isoformat()
    start = c.get("start_at")
    if start and str(start) > now_iso:
        return False
    end = c.get("end_at")
    if end:
        end = str(end)
        if len(end) == 10 and "T" not in end:
            end = f"{end}T23:59:59+00:00"
        if end < now_iso:
            return False
    return True
