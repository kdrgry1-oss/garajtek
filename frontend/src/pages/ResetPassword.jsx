// =============================================================================
// ResetPassword.jsx — Şifre Sıfırla (e-postadaki ?token= ile yeni şifre belirle)
// Backend: POST /auth/forgot-password/reset { reset_token, new_password }
// =============================================================================
import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPassword() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // Jeton index.html'de adres çubuğundan silinip sessionStorage'a alınır (analitiğe sızmasın).
  const [token] = useState(() => {
    let t = params.get("token") || "";
    try { if (!t) t = sessionStorage.getItem("pw_reset_token") || ""; } catch (_) { /* noop */ }
    return t;
  });

  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!token) {
      toast.error("Bağlantı geçersiz. Lütfen yeni bir sıfırlama bağlantısı isteyin.");
      return;
    }
    if (pw.length < 6) {
      toast.error("Şifre en az 6 karakter olmalı");
      return;
    }
    if (pw !== pw2) {
      toast.error("Şifreler eşleşmiyor");
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${API}/auth/forgot-password/reset`, {
        reset_token: token,
        new_password: pw,
      });
      try { sessionStorage.removeItem("pw_reset_token"); } catch (_) { /* noop */ }
      toast.success("Şifreniz güncellendi. Şimdi giriş yapabilirsiniz.");
      navigate("/giris");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Bağlantı geçersiz veya süresi dolmuş");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Header />
      <main className="electro el-page">
      <Breadcrumb items={[{ label: "Giriş", to: "/giris" }, { label: "Şifre Sıfırla" }]} />
      <div className="container mb-8">
        <div className="max-width-530 mx-auto border border-color-1 borders-radius-6 p-4 p-md-6">
          <h1 className="font-size-26 font-weight-light mb-3">Yeni Şifre Belirle</h1>
          {!token ? (
            <div className="text-sm text-gray-700 space-y-3">
              <p>Bağlantı geçersiz veya eksik. Lütfen yeniden şifre sıfırlama bağlantısı isteyin.</p>
              <Link to="/sifremi-unuttum" className="inline-block text-black underline">
                Sıfırlama bağlantısı iste
              </Link>
            </div>
          ) : (
            <>
              <p className="font-size-14 text-gray-90 mb-4">Yeni şifrenizi belirleyin (en az 6 karakter).</p>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder="Yeni şifre"
                className="form-control mb-4"
                autoFocus
              />
              <input
                type="password"
                value={pw2}
                onChange={(e) => setPw2(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
                placeholder="Yeni şifre (tekrar)"
                className="form-control mb-4"
              />
              <button
                onClick={submit}
                disabled={loading}
                className="btn btn-primary-dark-w btn-block rounded-pill"
              >
                {loading ? "Güncelleniyor…" : "Şifreyi Güncelle"}
              </button>
            </>
          )}
          <div className="mt-5 text-sm text-center">
            <Link to="/giris" className="text-blue">Girişe dön</Link>
          </div>
        </div>
      </div>
      </main>
      <Footer />
    </>
  );
}
