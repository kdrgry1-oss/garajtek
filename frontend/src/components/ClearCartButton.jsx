import React, { useEffect, useState } from "react";

/**
 * "Sepeti Temizle" — onay SAYFA İÇİNDE sorulur (window.confirm KULLANILMAZ).
 * WhatsApp/Instagram/Facebook uygulama içi tarayıcıları ve bazı mobil tarayıcılar
 * window.confirm'i sessizce engelleyip "hayır" döndürüyordu → buton hiçbir şey yapmıyordu.
 */
export default function ClearCartButton({ onClear, className = "", testId, align = "" }) {
  const [ask, setAsk] = useState(false);
  useEffect(() => {
    if (!ask) return undefined;
    const t = setTimeout(() => setAsk(false), 8000);  // cevap verilmezse eski haline dön
    return () => clearTimeout(t);
  }, [ask]);

  if (!ask) {
    return (
      <button type="button" className={`btn btn-link p-0 font-size-13 text-gray-90 ${className}`} data-testid={testId}
        onClick={() => setAsk(true)}>
        <i className="far fa-trash-alt mr-1" />Sepeti Temizle
      </button>
    );
  }
  return (
    <span className={`d-inline-flex align-items-center flex-wrap ${align} ${className}`} data-testid={testId ? `${testId}-confirm` : undefined}>
      <span className="font-size-13 text-gray-90 mr-2">Tümü silinsin mi?</span>
      <button type="button" className="btn btn-danger btn-xs py-1 px-3 mr-1 font-size-13" data-testid={testId ? `${testId}-yes` : undefined}
        onClick={() => { setAsk(false); onClear(); }}>Evet, temizle</button>
      <button type="button" className="btn btn-soft-secondary btn-xs py-1 px-3 font-size-13" onClick={() => setAsk(false)}>Vazgeç</button>
    </span>
  );
}
