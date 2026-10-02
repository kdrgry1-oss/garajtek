// A11 video_banner — video (veya kapak görseli) + başlık/metin/düğme.
import { useState } from "react";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";

export default function Render({ settings }) {
  const st = settings;
  const [playing, setPlaying] = useState(false);
  const video = st.video?.url;
  if (!video && !st.poster?.url) return null;
  const auto = video && st.autoplay;
  return (
    <div data-testid="video-banner">
      {video ? (
        <div className="position-relative bg-dark rounded" style={{ aspectRatio: "16 / 9", overflow: "hidden" }}>
          {playing || auto ? (
            <video src={video} autoPlay muted={st.muted !== false} loop={st.loop !== false} playsInline poster={st.poster?.url} className="w-100 h-100" style={{ objectFit: "cover" }} data-pd-field="video" />
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
      ) : (
        <SmartLink link={st.button?.link} fallback="div" className="d-block"><SmartImage image={st.poster} width={1400} className="img-fluid w-100" field="poster" /></SmartLink>
      )}
      {(st.title || st.text || (st.button?.text && linkHref(st.button?.link))) && (
        <div className="text-center mt-4">
          {st.title && <h3 className="font-size-22 mb-2" data-pd-field="title">{st.title}</h3>}
          {st.text && <p className="font-size-16 text-gray-90" data-pd-field="text">{st.text}</p>}
          {st.button?.text && linkHref(st.button?.link) && <SmartLink link={st.button.link} className="btn btn-primary px-5 rounded-pill" field="button.text">{st.button.text}</SmartLink>}
        </div>
      )}
    </div>
  );
}
