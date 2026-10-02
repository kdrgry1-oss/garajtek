// Şemadan otomatik form (SPEC §2.2–2.4): sekmeler, show_if, responsive değerler, alan başına
// "↺ Şablon varsayılanına dön", satır içi Türkçe hatalar, tıkla-odaklan (önizlemeden gelen alan yolu).
// Elle yazılmış blok formu YOK — her widget alan tipinden seçilir.
import { useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { deepEqual, getPath, isObj, itemDefault, showIf, stripIds } from "../_shared/schema";
import {
  BoolInput, CarouselInput, ColorInput, CountdownInput, DateTimeInput, HtmlInput, IconInput, NumberInput, RepeaterInput,
  ResponsiveWrap, SectionHeaderInput, SelectInput, SpacingInput, TextInput,
} from "./widgets";
import ImageField from "./ImageField";
import LinkField from "./LinkField";
import RichTextField from "./RichTextField";
import ProductSourceField from "./ProductSourceField";
import { BrandPicker, CategoryPicker, ProductPicker } from "./Pickers";

const SPAN = { full: "col-span-6", half: "col-span-6 sm:col-span-3", third: "col-span-6 sm:col-span-2" };

/** Backend hata yolu "settings.slides[2].button" → "slides.2.button" */
export const normErrPath = (p) => String(p || "").replace(/^settings\./, "").replace(/\[(\d+)\]/g, ".$1");

function Widget({ field, value, onChange, ctx, path, defaults, renderFields }) {
  const props = { field, value, onChange, ctx };
  switch (field.type) {
    case "text": return <TextInput {...props} />;
    case "textarea": return <TextInput {...props} multiline />;
    case "rich_text": return <RichTextField {...props} />;
    case "html": return <HtmlInput {...props} />;
    case "number": return <NumberInput {...props} />;
    case "bool": return <BoolInput {...props} />;
    case "select": return <SelectInput {...props} />;
    case "color": return <ColorInput {...props} />;
    case "date_time": return <DateTimeInput {...props} />;
    case "icon": return <IconInput {...props} />;
    case "spacing": return <SpacingInput {...props} />;
    case "image": return <ImageField {...props} />;
    case "link": return <LinkField {...props} />;
    case "product_source": return <ProductSourceField {...props} />;
    case "product_picker": return <ProductPicker {...props} />;
    case "category_picker": return <CategoryPicker {...props} />;
    case "brand_picker": return <BrandPicker {...props} />;
    case "group": return (
      <div className="grid grid-cols-6 gap-2 border rounded p-2 bg-gray-50/60">
        {renderFields(field.fields || [], isObj(value) ? value : {}, onChange, path, isObj(defaults) ? defaults : {})}
      </div>
    );
    case "repeater": return <RepeaterInput {...props} path={path} renderFields={(f, v, oc, p) => renderFields(f, v, oc, p, itemDefault(field))} />;
    case "carousel": return <CarouselInput {...props} path={path} renderFields={(f, v, oc, p) => <div className="grid grid-cols-6 gap-2">{renderFields(f, v, oc, p, isObj(defaults) ? defaults : {})}</div>} />;
    case "countdown": return <CountdownInput {...props} path={path} renderFields={(f, v, oc, p) => <div className="grid grid-cols-6 gap-2">{renderFields(f, v, oc, p, isObj(defaults) ? defaults : {})}</div>} />;
    case "section_header": return <SectionHeaderInput {...props} path={path} renderFields={(f, v, oc, p) => <div className="grid grid-cols-6 gap-2">{renderFields(f, v, oc, p, isObj(defaults) ? defaults : {})}</div>} />;
    default: return <div className="text-xs text-red-600">Desteklenmeyen alan tipi: {field.type}</div>;
  }
}

function FieldRow({ field, value, onChange, ctx, path, def, errors, renderFields }) {
  const err = errors.filter((e) => e.p === path);
  const canReset = def !== undefined && !deepEqual(stripIds(value ?? null), stripIds(def ?? null));
  const block = ["group", "repeater", "carousel", "countdown", "section_header"].includes(field.type);
  const resetBtn = canReset ? (
    <button type="button" className="text-gray-400 hover:text-gray-800" title="Şablon varsayılanına dön" aria-label={`${field.label}: şablon varsayılanına dön`}
      onClick={() => onChange(JSON.parse(JSON.stringify(def)))} data-testid={`reset-${path}`}>
      <RotateCcw size={12} />
    </button>
  ) : null;
  const label = (
    <div className="flex items-center justify-between gap-2 mb-1">
      <label className="text-xs font-semibold text-gray-700">{field.label}{field.required ? <span className="text-red-500"> *</span> : null}</label>
      {resetBtn}
    </div>
  );
  const widget = field.responsive
    ? <ResponsiveWrap value={value} onChange={onChange}>{(cur, set) => <Widget field={{ ...field, responsive: false }} value={cur} onChange={set} ctx={ctx} path={path} defaults={def} renderFields={renderFields} />}</ResponsiveWrap>
    : <Widget field={field} value={value} onChange={onChange} ctx={ctx} path={path} defaults={def} renderFields={renderFields} />;
  return (
    <div className={`${SPAN[block ? "full" : field.width || "full"]} ${err.length ? "rounded ring-1 ring-red-300 p-1 -m-1" : ""}`} data-field-path={path}>
      {field.type === "bool" ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-gray-700">{field.label}</span>
          <div className="flex items-center gap-2">{resetBtn}{widget}</div>
        </div>
      ) : (<>{label}{widget}</>)}
      {field.help && <div className="text-[11px] text-gray-500 mt-0.5">{field.help}</div>}
      {err.map((e, i) => <div key={i} className="text-[11px] text-red-600 mt-0.5" role="alert">{e.message}</div>)}
    </div>
  );
}

export function useRenderFields(ctx, errors) {
  const renderFields = (fields, value, onChange, path, defaults) => (fields || []).map((f) => {
    if (f.super_admin && !ctx.superAdmin) return null;
    if (!showIf(f, value, { root: ctx.root, parent: ctx.parentOf ? ctx.parentOf(path) : undefined })) return null;
    const p = path ? `${path}.${f.name}` : f.name;
    return (
      <FieldRow key={f.name} field={f} value={value?.[f.name]} path={p} ctx={ctx} errors={errors}
        def={isObj(defaults) ? defaults[f.name] : undefined}
        onChange={(x) => onChange({ ...(value || {}), [f.name]: x })} renderFields={renderFields} />
    );
  });
  return renderFields;
}

/**
 * props: fields (şema + ortak alanlar), tabs, value (settings), onChange, defaults (şablon varsayılanı),
 *        errors (backend {path,message}[]), ctx ({superAdmin}), focusPath ("slides.0.title")
 */
export default function SchemaForm({ fields, tabs: tabOrder = [], value, onChange, defaults, errors = [], ctx = {}, focusPath, testId = "schema-form" }) {
  const root = value || {};
  const errs = useMemo(() => errors.map((e) => ({ ...e, p: normErrPath(e.path) })), [errors]);
  const fullCtx = { ...ctx, root, parentOf: (p) => { const parts = String(p).split("."); parts.pop(); return parts.length > 1 ? getPath(root, parts.slice(0, -1).join(".")) : root; } };
  const renderFields = useRenderFields(fullCtx, errs);
  const tabs = useMemo(() => {
    const order = [...tabOrder];
    (fields || []).forEach((f) => { const t = f.tab || "İçerik"; if (!order.includes(t)) order.push(t); });
    return order.filter((t) => (fields || []).some((f) => (f.tab || "İçerik") === t && (!f.super_admin || ctx.superAdmin)));
  }, [fields, tabOrder, ctx.superAdmin]);
  const [tab, setTab] = useState(tabs[0]);
  const boxRef = useRef(null);
  useEffect(() => { if (!tabs.includes(tab)) setTab(tabs[0]); }, [tabs]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!focusPath) return;
    const rootName = String(focusPath).split(".")[0];
    const f = (fields || []).find((x) => x.name === rootName);
    if (f) setTab(f.tab || "İçerik");
    setTimeout(() => {
      const parts = String(focusPath).split(".");
      let el = null;
      while (parts.length && !el) { el = boxRef.current?.querySelector(`[data-field-path="${parts.join(".")}"]`); parts.pop(); }
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("ring-2", "ring-yellow-400"); setTimeout(() => el.classList.remove("ring-2", "ring-yellow-400"), 1500); }
    }, 60);
  }, [focusPath]); // eslint-disable-line react-hooks/exhaustive-deps
  const tabErr = (t) => errs.some((e) => (fields || []).some((f) => (f.tab || "İçerik") === t && (e.p === f.name || e.p.startsWith(`${f.name}.`))));
  const shown = (fields || []).filter((f) => (f.tab || "İçerik") === tab);
  return (
    <div ref={boxRef} data-testid={testId}>
      {tabs.length > 1 && (
        <div className="flex flex-wrap gap-1 border-b mb-3" role="tablist">
          {tabs.map((t) => (
            <button key={t} type="button" role="tab" aria-selected={t === tab} onClick={() => setTab(t)}
              className={`px-2.5 py-1.5 text-xs -mb-px border-b-2 ${t === tab ? "border-yellow-400 font-semibold" : "border-transparent text-gray-600 hover:text-gray-900"}`}>
              {t}{tabErr(t) && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-red-500 align-middle" />}
            </button>
          ))}
        </div>
      )}
      <div className="grid grid-cols-6 gap-3">
        {renderFields(shown, root, onChange, "", defaults || {})}
      </div>
    </div>
  );
}
