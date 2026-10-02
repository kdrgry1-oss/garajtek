// A11 video_banner — video (otomatik/sessiz/döngü ayarlı) veya kapak görseli + başlık, metin, düğme.
// Video da kapak da yoksa vitrinde çizilmez; önizlemede kapak ölçüsünde yer tutucu.
import { useState } from "react";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import Placeholder from "../_shared/Placeholder";
import { usePageCtx } from "../_shared/PageCtx";

const ASPECT = { "16_9": "16 / 9", "21_9": "21 / 9", "1170_500": "1170 / 500", "4_3": "4 / 3" };

export default function Render({ settings }) {
  const ctx = usePageCtx();
  const st = settings;
  const [playing, setPlaying] = useState(false);
  const video = st.video?.url;
  const ratio = ASPECT[st.aspect] || ASPECT["16_9"];
  const radius = Number(st.radius ?? 4);
  if (!video && !st.poster?.url && !ctx.preview) return null;
  const auto = video && st.autoplay;
  const hasBtn = st.button?.text && linkHref(st.button?.link);
  return (
    <div data-testid="video-banner">
      {video ? (
        <div className="position-relative bg-dark" style={{ aspectRatio: ratio, overflow: "hidden", borderRadius: radius }}>
          {playing || auto ? (
            <video src={video} autoPlay muted={st.muted !== false} loop={st.loop !== false} playsInline controls={!auto} poster={st.poster?.url}
              className="w-100 h-100" style={{ objectFit: "cover" }} data-pd-field="video" />
          ) : (
            <>
              {st.poster?.url && <SmartImage image={st.poster} width={1400} className="w-100 h-100" fit="cover" field="poster" />}
              <button type="button" onClick={() => setPlaying(true)} className="btn btn-primary rounded-circle position-absolute"
                style={{ left: "50%", top: "50%", transform: "translate(-50%,-50%)", width: 72, height: 72 }} aria-label={st.play_label}>
                <i className="fas fa-play" />
              </button>
            </>
          )}
        </div>
      ) : st.poster?.url ? (
        <SmartLink link={st.button?.link} fallback="div" className="d-block overflow-hidden" style={{ borderRadius: radius }}>
          <SmartImage image={st.poster} width={1400} className="img-fluid w-100" field="poster" />
        </SmartLink>
      ) : <Placeholder size={[1170, 500]} field="poster" />}
      {(st.title || st.text || hasBtn) && (
        <div className={`text-${st.text_align || "center"} mt-4`}>
          {st.title && <h3 className="font-size-22 mb-2" data-pd-field="title">{st.title}</h3>}
          {st.text && <p className="font-size-16 text-gray-90" data-pd-field="text">{st.text}</p>}
          {hasBtn && <SmartLink link={st.button.link} className="btn btn-primary px-5 rounded-pill" field="button.text">{st.button.text}</SmartLink>}
        </div>
      )}
    </div>
  );
}
