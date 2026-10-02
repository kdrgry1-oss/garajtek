import { createContext, useContext, useState, useEffect, useRef, useMemo, useCallback } from "react";
import { toast } from "sonner";
import { useAuth } from "./AuthContext";
import { buildSetLines, mergeSetLines, readReplaceCtx, clearReplaceCtx, productInCategory, setLineFrom } from "../lib/productSets";

const CartContext = createContext();

/** Sepete tek ürün ekleme (saf fonksiyon) — addItem ve toplu ekleme (Hızlı Sipariş) ortak. */
function addToLines(prev, product, variant, quantity) {
  const key = variant ? `${product.id}-${variant.id}` : product.id;
  const existing = prev.find((item) => !item.setId && (
    variant ? item.variantId === variant.id : item.productId === product.id && !item.variantId
  ));
  if (existing && existing.needsReplacement) {
    // Tükendiği için bekleyen kalem yeniden eklendi (stok geldi) → taze kalemle değiştir
    return addToLines(prev.filter((it) => it !== existing), product, variant, quantity);
  }

  if (existing) {
    // Var olan kalemde adet artır + fiyat/indirim/kampanya alanlarını eldeki GÜNCEL ürün
    // verisinden tazele (eski kalemde kampanya eksikse bile artık doğru indirim görünür).
    const _listBase = Number(product.price) || 0;
    const _saleBase = product.sale_price && product.sale_price < _listBase ? product.sale_price : _listBase;
    const _pd = variant?.price_diff || variant?.price_adjustment || 0;
    return prev.map((item) => {
      if (item !== existing) return item;
      const cap = item.stock || Infinity;   // stok tavanı (eski sepet kalemlerinde stock yoksa sınırsız)
      const patch = _listBase > 0 ? {
        price: Math.round((_saleBase + _pd) * 100) / 100,
        listPrice: Math.round((_listBase + _pd) * 100) / 100,
        campaignPct: Number(product.campaign_discount_percent || 0),
      } : {};
      return { ...item, ...patch, quantity: Math.min(item.quantity + quantity, cap) };
    });
  }

  // Fiyat: para hesabı için sale_price tabanı (kampanya sepet/sunucu tarafında uygulanır).
  // listPrice + campaignPct: sepette "indirim uygulandı" görünümü için (üstü çizili + indirimli).
  const listBase = Number(product.price) || 0;
  const saleBase = product.sale_price && product.sale_price < listBase ? product.sale_price : listBase;
  const priceDiff = variant?.price_diff || variant?.price_adjustment || 0;
  const finalPrice = saleBase + priceDiff;

  return [
    ...prev,
    {
      id: key,
      productId: product.id,
      categoryId: product.category_id || null,
      slug: product.slug || product.id,
      variantId: variant?.id || null,
      name: product.name,
      price: finalPrice,
      listPrice: listBase + priceDiff,
      campaignPct: Number(product.campaign_discount_percent || 0),
      image: product.images?.[0] || "",
      size: variant?.size || null,
      color: variant?.color || null,
      stockCode: variant?.stock_code || product.stock_code || null,
      barcode: variant?.barcode || product.barcode || null,
      stock: (variant ? variant.stock : product.stock) ?? null,   // stok tavanı (oversell engeli)
      quantity: Math.min(quantity, (variant ? variant.stock : product.stock) || Infinity),
    },
  ];
}

export function CartProvider({ children }) {
  // lines: TÜM sepet kalemleri (setin stokta olmayan, "değiştirilmesi gereken" bileşenleri dahil).
  // Dışarıya `items` = satın alınabilir kalemler (toplam/kasa/kampanya motoru bunları görür),
  // `pendingItems` = değiştirilmesi gereken set bileşenleri (sepette uyarı kutusuyla gösterilir).
  const [lines, setItems] = useState(() => {
    // Y26: Bozuk/eski bir "cart" değeri (ör. "null") JSON.parse'ta hataya ya da items=null'a
    // yol açıp items.reduce'u patlatarak TÜM mağazayı beyaz ekran yapıyordu. Güvenli parse.
    try {
      const saved = localStorage.getItem("cart");
      const parsed = saved ? JSON.parse(saved) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      try { localStorage.removeItem("cart"); } catch {}
      return [];
    }
  });
  const [isOpen, setIsOpen] = useState(false);

  const items = useMemo(() => lines.filter((it) => !it.needsReplacement), [lines]);
  const pendingItems = useMemo(() => lines.filter((it) => it.needsReplacement), [lines]);

  useEffect(() => {
    localStorage.setItem("cart", JSON.stringify(lines));
  }, [lines]);

  // CANLI FİYAT/İNDİRİM TAZELEME — sepet kalemlerinin fiyat/indirimli fiyat/otomatik kampanya
  // alanlarını mevcut ürün verisinden günceller. Böylece:
  //  • Kampanya kaydedilmeden (eski) eklenmiş kalem → indirim artık DOĞRU görünür,
  //  • Admin sonradan fiyat/kampanya değiştirmişse → sepet/kasa güncel indirimli fiyatı gösterir.
  // Sunucu fiyatı zaten otoriter (çekim); bu yalnız GÖRÜNÜMÜ canlıya çeker. Değişiklik yoksa
  // state'e dokunmaz (gereksiz re-render/döngü olmaz).
  const _refreshKey = items.map((it) => `${it.productId}:${it.variantId || ""}`).join(",");
  useEffect(() => {
    const list = items || [];
    if (list.length === 0) return;
    const API = process.env.REACT_APP_BACKEND_URL;
    if (!API) return;
    let cancel = false;
    const ids = [...new Set(list.map((it) => it.productId).filter(Boolean))];
    fetch(`${API}/api/products/cart-pricing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_ids: ids }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancel || !data || !data.items) return;
        setItems((prev) => {
          let changed = false;
          const next = prev.map((it) => {
            const info = data.items[it.productId];
            if (!info || it.needsReplacement) return it;
            const listBase = Number(info.price) || 0;
            const sp = Number(info.sale_price) || 0;
            const saleBase = sp > 0 && sp < listBase ? sp : listBase;
            const nextCamp = Number(info.campaign_discount_percent) || 0;
            let pd = null;
            if (it.variantId) {
              const vinfo = (info.variants || {})[it.variantId];
              pd = vinfo ? (Number(vinfo.price_diff) || 0) : null; // varyant bulunamazsa fiyata dokunma
            } else {
              pd = 0;
            }
            let nextPrice = Number(it.price);
            let nextList = Number(it.listPrice);
            if (pd !== null && listBase > 0) {
              nextPrice = Math.round((saleBase + pd) * 100) / 100;
              nextList = Math.round((listBase + pd) * 100) / 100;
            }
            if (nextPrice === Number(it.price) && nextList === Number(it.listPrice) && nextCamp === Number(it.campaignPct || 0)) {
              return it;
            }
            changed = true;
            return { ...it, price: nextPrice, listPrice: nextList, campaignPct: nextCamp };
          });
          return changed ? next : prev;
        });
      })
      .catch(() => {});
    return () => { cancel = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [_refreshKey]);

  // TERK EDİLEN SEPET TAKİBİ: sepet değişince (debounce 2.5sn) backend'e kaydet
  // (POST /api/cart/track). Daha önce storefront bunu HİÇ çağırmıyordu → cart_sessions
  // boş kalıyor, "Terk Edilen Sepet" paneli hep 0 gösteriyordu. Sipariş sonrası sepet
  // boşalınca (items=[]) kayıt "total 0" olur ve admin listesinde (total>0 filtresi) çıkmaz.
  // Giriş/çıkışta sepet yeniden izlenir → misafirken doldurulan sepet girişten sonra üyeye bağlanır.
  const { token: authToken } = useAuth() || {};
  const trackedNonEmptyRef = useRef(false);
  useEffect(() => {
    // Boş sepet yalnız daha önce dolu izlendiyse gönderilir (ürünleri elle silen müşteri
    // "sepetinde ürün unuttun" maili almasın); ilk açılıştaki boş sepet için istek atılmaz.
    if (!items || (items.length === 0 && !trackedNonEmptyRef.current)) return;
    trackedNonEmptyRef.current = items.length > 0;
    const t = setTimeout(() => {
      try {
        const API = process.env.REACT_APP_BACKEND_URL;
        if (!API) return;
        let sid = localStorage.getItem("cart_session_id");
        if (!sid) {
          if (!window.crypto?.getRandomValues) return;
          sid = window.crypto.randomUUID?.() || Array.from(
            window.crypto.getRandomValues(new Uint8Array(16)),
            (byte) => byte.toString(16).padStart(2, "0")
          ).join("");
          localStorage.setItem("cart_session_id", sid);
        }
        const payload = {
          session_id: sid,
          items: items.map((it) => ({
            product_id: it.productId, variant_id: it.variantId || null, size: it.size || null,
            name: it.name, qty: it.quantity, price: it.price, image: it.image,
          })),
          total: items.reduce((s, it) => s + (Number(it.price) || 0) * (it.quantity || 1), 0),
        };
        try {
          const u = JSON.parse(localStorage.getItem("user") || "null");
          if (u && u.email) payload.email = u.email;
          if (u && u.id) payload.user_id = u.id;
          if (u && u.phone) payload.phone = u.phone;
        } catch (_) { /* yoksay */ }
        // Oturum token'ı: sepet yalnız DOĞRULANMIŞ üyeye bağlanır (sunucu user_id'yi token'dan alır).
        const headers = { "Content-Type": "application/json" };
        try {
          const tok = localStorage.getItem("token");
          if (tok) headers.Authorization = `Bearer ${tok}`;
        } catch (_) { /* yoksay */ }
        fetch(`${API}/api/cart/track`, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(() => {});
      } catch (_) { /* sessiz */ }
    }, 2500);
    return () => clearTimeout(t);
  }, [items, authToken]);

  // ÜRÜN SETİ: tüm bileşenler ayrı kalem olarak (set_id/set_slot ile) eklenir; stokta olmayan
  // bileşen "değiştirilmesi gerekiyor" kalemi olur (bkz. lib/productSets.js, backend/product_sets.py).
  const addSet = (setData, quantity = 1) => {
    const built = buildSetLines(setData, quantity);
    if (!built.length) return 0;
    setItems((prev) => mergeSetLines(prev, built));
    setIsOpen(true);
    return built.length;
  };

  const addSetById = async (setRef, quantity = 1) => {
    const API = process.env.REACT_APP_BACKEND_URL;
    const r = await fetch(`${API}/api/product-sets/${encodeURIComponent(setRef)}`);
    if (!r.ok) throw new Error("Set yüklenemedi");
    return addSet(await r.json(), quantity);
  };

  // "Bu ürünü değiştir" akışı: bekleyen bileşenin yerine seçilen ürün setin yuvasına yazılır.
  const replacePending = (lineId, product, variant = null) => {
    let done = false;
    setItems((prev) => prev.map((it) => {
      if (it.id !== lineId || !it.needsReplacement) return it;
      done = true;
      return setLineFrom(it, product, variant);
    }));
    return done;
  };

  const addItem = (product, variant = null, quantity = 1) => {
    if (product && product.product_type === "set") {
      // Set kartı/sayfasından "Sepete Ekle": bileşenleri getir ve hepsini ekle
      addSetById(product.id, quantity).catch(() => {});
      return;
    }
    // Y28: Kimliksiz (uydurma) varyantı varyantsız gibi işle — aksi halde variantId=null ile
    // her ekleme yeni satır oluşturup birleşmiyordu.
    if (variant && !variant.id) variant = null;
    const ctx = readReplaceCtx();
    if (ctx && lines.some((it) => it.id === ctx.lineId && it.needsReplacement)
        && productInCategory(product, ctx.categoryId)) {
      replacePending(ctx.lineId, product, variant);
      clearReplaceCtx();
      try { toast.success(ctx.setName ? `“${ctx.setName}” seti için ${product.name} eklendi` : `${ctx.productName || "Tükenen ürün"} yerine ${product.name} eklendi`); } catch { /* yoksay */ }
      setIsOpen(true);
      return;
    }
    setItems((prev) => addToLines(prev, product, variant, quantity));
    setIsOpen(true);
  };

  // Hızlı Sipariş / toplu ekleme: [{product, variant, quantity}] TEK sepet güncellemesiyle eklenir.
  const addMany = (list) => {
    const rows = (list || []).filter((r) => r && r.product && r.product.product_type !== "set");
    if (!rows.length) return 0;
    setItems((prev) => rows.reduce((acc, r) => addToLines(acc, r.product, r.variant && r.variant.id ? r.variant : null,
      Math.max(1, Number(r.quantity) || 1)), prev));
    setIsOpen(true);
    return rows.length;
  };

  // STOK YENİDEN KONTROLÜ (sözleşme 7.3/7.4): sepet/çekmece/kasa açılınca kalemlerin güncel stoğu
  // sorulur. Tükenen kalem "değiştirilmesi gerekiyor" durumuna geçer (toplamdan çıkar, kasada
  // sipariş engellenir; müşteri aynı alt kategoriden stoklu bir ürün seçebilir). Stok gelirse geri döner.
  const linesRef = useRef(lines);
  linesRef.current = lines;
  const refreshStock = useCallback(async () => {
    const API = process.env.REACT_APP_BACKEND_URL;
    const cur = linesRef.current || [];
    if (!API || !cur.length || typeof fetch !== "function") return;
    let data = null;
    try {
      const r = await fetch(`${API}/api/storefront/cart-stock`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lines: cur.map((l) => ({ product_id: l.productId, variant_id: l.variantId || null, quantity: l.quantity })) }),
      });
      data = r.ok ? await r.json() : null;
    } catch { data = null; }
    if (!data || !data.items) return;
    const gone = cur.filter((l) => !l.needsReplacement && data.items[`${l.productId}|${l.variantId || ""}`]
      && !data.items[`${l.productId}|${l.variantId || ""}`].available).map((l) => l.name);
    setItems((prev) => {
      let changed = false;
      const next = prev.map((l) => {
        const info = data.items[`${l.productId}|${l.variantId || ""}`];
        if (!info) return l;
        if (!l.needsReplacement && !info.available) {
          changed = true;
          return { ...l, needsReplacement: true, oosAuto: true, stock: 0,
            replaceCategory: info.leaf_category || l.replaceCategory || null };
        }
        if (l.needsReplacement && info.available && info.stock >= (l.setQty || 1)) {
          changed = true;
          const { needsReplacement, oosAuto, replaceCategory, ...rest } = l; // eslint-disable-line no-unused-vars
          return { ...rest, stock: info.stock, quantity: Math.max(1, Math.min(l.quantity, info.stock)) };
        }
        if (!l.needsReplacement && info.available && info.stock !== l.stock) {
          changed = true;
          return { ...l, stock: info.stock, quantity: Math.min(l.quantity, info.stock) };
        }
        return l;
      });
      return changed ? next : prev;
    });
    if (gone.length) {
      try { toast.warning(`Sepetinizdeki ${gone.length === 1 ? `“${gone[0]}”` : `${gone.length} ürün`} stokta tükendi. Başka bir ürünle değiştirebilirsiniz.`); } catch { /* yoksay */ }
    }
  }, []);

  // Sayfa açılışında bir kez (eski sepet) — ayrıca sepet/çekmece/kasa bileşenleri kendileri çağırır.
  useEffect(() => { refreshStock(); }, [refreshStock]);

  const removeItem = (itemId) => {
    setItems((prev) => prev.filter((item) => item.id !== itemId));
    const ctx = readReplaceCtx();
    if (ctx && ctx.lineId === itemId) clearReplaceCtx();
  };

  const updateQuantity = (itemId, quantity) => {
    if (quantity < 1) {
      removeItem(itemId);
      return;
    }
    setItems((prev) =>
      prev.map((item) =>
        item.id === itemId
          ? { ...item, quantity: Math.min(quantity, item.stock || Infinity) }  // stok üstüne çıkma (oversell engeli)
          : item
      )
    );
  };

  const clearCart = () => {
    // Sipariş sonrası (veya elle boşaltma) sunucudaki terk-sepet kaydını SİL → satın alan
    // müşteri "terkedilmiş sepet" sayılıp hatırlatma maili almasın (denetim bulgusu #38).
    try {
      const API = process.env.REACT_APP_BACKEND_URL;
      const sid = localStorage.getItem("cart_session_id");
      if (API && sid) {
        fetch(`${API}/api/cart/mark-ordered`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid }),
          keepalive: true,
        }).catch(() => {});
      }
    } catch (_) { /* sessiz */ }
    setItems([]);
    clearReplaceCtx();
    setIsOpen(false);
  };

  const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const itemCount = items.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <CartContext.Provider
      value={{
        items,
        pendingItems,
        allItems: lines,
        isOpen,
        setIsOpen,
        addItem,
        addSet,
        addSetById,
        addMany,
        replacePending,
        refreshStock,
        removeItem,
        updateQuantity,
        clearCart,
        total,
        itemCount,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}
