import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function MaintenanceScreen({ title, message, logoUrl, siteName }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle"); // idle | sending | done | error
  const [feedback, setFeedback] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("sending");
    try {
      const res = await axios.post(`${API}/settings/maintenance/notify`, { email: email.trim() });
      setFeedback(res.data?.message || "Teşekkürler!");
      setStatus("done");
      setEmail("");
    } catch (err) {
      setFeedback(err.response?.data?.detail || "Bir hata oluştu, lütfen tekrar deneyin.");
      setStatus("error");
    }
  };

  return (
    <div
      data-testid="maintenance-screen"
      className="fixed inset-0 z-[9999] overflow-y-auto bg-white text-[#333e48]"
      style={{ fontFamily: "'Open Sans', system-ui, -apple-system, 'Segoe UI', sans-serif" }}
    >
      <div className="h-1.5 w-full bg-[#fed700]" />
      <div className="min-h-[calc(100%-6px)] flex items-center justify-center px-5 py-12">
        <div className="max-w-xl w-full text-center">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={siteName}
              className="h-12 mx-auto mb-10 object-contain"
              data-testid="maintenance-logo"
            />
          ) : (
            <div
              className="mb-10 text-4xl font-bold tracking-tight lowercase"
              data-testid="maintenance-sitename"
            >
              {siteName}
              <span className="text-[#fed700]">.</span>
            </div>
          )}

          <div className="mb-8 flex justify-center" aria-hidden="true">
            <svg width="120" height="96" viewBox="0 0 120 96" fill="none">
              <circle cx="60" cy="48" r="44" fill="#fff7c2" />
              <rect x="22" y="14" width="8" height="70" rx="2" fill="#333e48" />
              <rect x="90" y="14" width="8" height="70" rx="2" fill="#333e48" />
              <rect x="30" y="52" width="60" height="5" rx="2" fill="#fed700" />
              <path d="M38 52l6-12h32l6 12z" fill="#333e48" />
              <circle cx="46" cy="58" r="5" fill="#333e48" />
              <circle cx="74" cy="58" r="5" fill="#333e48" />
              <rect x="18" y="82" width="84" height="4" rx="2" fill="#333e48" />
            </svg>
          </div>

          <h1
            className="text-3xl sm:text-4xl font-bold leading-tight mb-4"
            data-testid="maintenance-title"
          >
            {title}
          </h1>

          <p
            className="text-base text-[#5a6570] leading-relaxed max-w-md mx-auto"
            data-testid="maintenance-message"
          >
            {message}
          </p>

          {/* Açılınca haber ver — e-posta toplama */}
          {status === "done" ? (
            <p
              className="mt-10 text-sm font-semibold max-w-md mx-auto"
              data-testid="maintenance-notify-success"
            >
              {feedback}
            </p>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="mt-10 max-w-md mx-auto"
              data-testid="maintenance-notify-form"
            >
              <p className="text-sm text-[#5a6570] mb-3">
                Açıldığımızda haber vermemizi ister misiniz?
              </p>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="E-posta adresiniz"
                  className="flex-1 bg-white border-2 border-[#fed700] rounded-full px-5 py-3 text-sm focus:outline-none focus:border-[#e6c200] placeholder:text-[#9aa3ab]"
                  data-testid="maintenance-notify-input"
                />
                <button
                  type="submit"
                  disabled={status === "sending"}
                  className="bg-[#fed700] text-[#333e48] font-bold rounded-full px-7 py-3 text-sm hover:bg-[#333e48] hover:text-white transition-colors disabled:opacity-50"
                  data-testid="maintenance-notify-submit"
                >
                  {status === "sending" ? "Gönderiliyor..." : "Haber Ver"}
                </button>
              </div>
              {status === "error" && (
                <p className="mt-3 text-xs text-red-600" data-testid="maintenance-notify-error">
                  {feedback}
                </p>
              )}
            </form>
          )}

          <p className="mt-12 text-xs text-[#9aa3ab]">
            © {new Date().getFullYear()} {siteName}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function MaintenanceGate({ children }) {
  const { isAdmin, loading: authLoading } = useAuth();
  const location = useLocation();
  const [status, setStatus] = useState(null);

  useEffect(() => {
    axios
      .get(`${API}/settings/maintenance`)
      .then((res) => setStatus(res.data))
      .catch(() => setStatus({ maintenance_mode: false }));
  }, []);

  // Admin paneline (giriş dahil) bakım modunda da her zaman erişilebilir olmalı.
  const isAdminRoute = location.pathname.startsWith("/admin");

  // Durum henüz yüklenmediyse içeriği göster (flash önleme).
  if (!status || !status.maintenance_mode || isAdminRoute) {
    return children;
  }

  // Bakım modu açık ve admin rotası değil: admin doğrulaması bitene kadar bekle.
  if (authLoading) return null;
  if (isAdmin) return children;

  return (
    <MaintenanceScreen
      title={status.maintenance_title}
      message={status.maintenance_message}
      logoUrl={status.logo_url}
      siteName={status.site_name}
    />
  );
}
