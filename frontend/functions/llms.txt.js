/**
 * Cloudflare Pages Function — /llms.txt
 * AI (LLM) asistanları için marka/ürün özetini backend'in DİNAMİK /llms.txt ucundan
 * (gerçek kategorilerle) proxy'ler → her zaman güncel + <site>/llms.txt'te erişilir.
 * API_BASE (Pages env binding) tanımlı değilse doğrudan statik dosyaya düşer.
 * Backend erişilemezse statik public/llms.txt'e (next) düşer.
 */
export async function onRequest(context) {
  const { env, next } = context;
  if (!env || !env.API_BASE) return next(); // beyaz etiket: bootstrap adresi yoksa statik yedek
  const apiBase = String(env.API_BASE).replace(/\/api\/?$/, "");
  try {
    const r = await fetch(`${apiBase}/llms.txt`, {
      cf: { cacheTtl: 3600, cacheEverything: true },
      headers: { accept: "text/plain" },
    });
    if (r.ok) {
      const body = await r.text();
      if (body && body.length > 30) {
        return new Response(body, {
          headers: {
            "content-type": "text/plain; charset=utf-8",
            "cache-control": "public, max-age=3600",
          },
        });
      }
    }
  } catch (_) {
    /* fallthrough */
  }
  return next(); // statik public/llms.txt
}
