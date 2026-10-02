// D9 team_grid — şablon v2.0 about.html: .bg-gray-1.py-12.mb-10.mb-lg-15 > .container > .row
//   > .col-md-4.mb-5.mb-xl-0.col-xl.text-center > img.img-fluid.mb-3.rounded-circle (300×300)
//   + h2.font-size-18.font-weight-semi-bold.mb-0 + span.text-gray-41 (görev)
// Bant rengi ve boşluklar bölüm ayarlarından (_section: #f5f5f5, 88 px iç boşluk).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "./style.css";

const COL = { 6: "col-md-4 col-xl", 5: "col-md-4 col-xl", 4: "col-md-6 col-xl-3", 3: "col-md-4" };

export default function Render({ settings, ctx }) {
  const st = settings;
  const members = (st.members || []).filter((m) => m && (m.name || (m.photo && m.photo.url)));
  if (!members.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Ekip üyesi ekleyin.</div> : null;
  const col = COL[Number(st.columns) || 6] || COL[6];
  return (
    <div className="pd-team" data-testid="team-grid" style={{ "--pd-team-role": st.role_color || "#989898" }}>
      {st.title && <h2 className="font-size-22 font-weight-semi-bold text-center mb-6" data-pd-field="title">{st.title}</h2>}
      <div className="row">
        {members.map((m, i) => {
          const f = `members.${i}`;
          return (
            <div key={m._id || i} className={`${col} mb-5 mb-xl-0 text-center`}>
              <SmartLink link={m.link} fallback="div" className="d-block text-reset">
                <SmartImage image={m.photo} size={[300, 300]} width={600} className={`img-fluid mb-3${st.round ? " rounded-circle" : ""}`}
                  phClassName={`mb-3 pd-team__ph${st.round ? " rounded-circle" : ""}`} field={`${f}.photo`} alt={m.name} />
                {m.name && <h2 className="font-size-18 font-weight-semi-bold mb-0" data-pd-field={`${f}.name`}>{m.name}</h2>}
              </SmartLink>
              {m.role && <span className="pd-team__role" data-pd-field={`${f}.role`}>{m.role}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
