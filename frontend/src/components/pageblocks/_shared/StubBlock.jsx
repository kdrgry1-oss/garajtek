// Henüz uygulanmamış blok (grup ajanı dolduracak) — vitrinde HİÇBİR ŞEY çizmez; Sayfa Tasarımı
// önizlemesinde blok adını gösteren nötr kutu.
import { usePageCtx } from "./PageCtx";

export default function StubBlock({ block, schema }) {
  const ctx = usePageCtx();
  if (!ctx.preview) return null;
  return (
    <div className="pd-stub" data-testid={`stub-${block?.type}`}>
      <strong>{schema?.title || block?.type}</strong>
      Bu blok hazırlanıyor — vitrinde henüz görünmez.
    </div>
  );
}
