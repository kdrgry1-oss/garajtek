import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";
import { useAuth } from "../context/AuthContext";
import axios from "axios";
import {
  createGooglePopupFlow,
  googleErrorMessage,
  isEmbeddedWebView,
  safeReturnPath,
} from "../lib/googleAuthFlow";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BUILD_GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID_V2 || process.env.REACT_APP_GOOGLE_CLIENT_ID || "";
const GOOGLE_FLOW_VERSION = "2026-09-08-popup-fallback-1";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const _redirectTo = safeReturnPath(new URLSearchParams(location.search).get("redirect"));
  const { login, register, user, loginWithToken } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  // FAZ 3+ — Hangi sosyal sağlayıcılar aktif?
  const [socialProviders, setSocialProviders] = useState({
    apple: false,
    facebook: false,
    google: Boolean(BUILD_GOOGLE_CLIENT_ID),
    google_client_id: BUILD_GOOGLE_CLIENT_ID,
  });
  const [googleStatus, setGoogleStatus] = useState({ phase: "idle", message: "" });
  const embeddedGoogle = isEmbeddedWebView();
  useEffect(() => {
    fetch(`${API}/auth/social/providers`).then((r) => r.ok && r.json())
      .then((d) => d && setSocialProviders(d)).catch(() => {});
  }, []);
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    phone: "",
  });

  const googleBtnRef = useRef(null);
  const googleFlowRef = useRef(null);

  // Tam-sayfa Google dönüşü: URL'deki kısa ömürlü kodu backend'de bir kez JWT'ye çevir.
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const code = q.get("google_code");
    const error = q.get("google_error");
    if (!code && !error) return;
    const returnTo = safeReturnPath(q.get("redirect") || (() => {
      try { return sessionStorage.getItem("google_redirect_to"); } catch { return ""; }
    })());
    window.history.replaceState({}, "", `/giris?redirect=${encodeURIComponent(returnTo)}`);
    if (error) {
      const message = googleErrorMessage(error);
      setGoogleStatus({ phase: "error", message });
      toast.error(message);
      return;
    }
    (async () => {
      setLoading(true);
      setGoogleStatus({ phase: "exchanging", message: "Google oturumu doğrulanıyor…" });
      try {
        const res = await axios.post(`${API}/auth/google/exchange`, { code });
        if (res.data?.token) {
          loginWithToken(res.data.token, res.data.user);
          toast.success("Google ile giriş başarılı!");
          try { sessionStorage.removeItem("google_redirect_to"); } catch {}
          navigate(returnTo, { replace: true });
        } else {
          throw new Error("missing app token");
        }
      } catch (err) {
        const message = err.response?.data?.detail || googleErrorMessage("verification");
        setGoogleStatus({ phase: "error", message });
        toast.error(message);
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Facebook ile giriş (sunucu-taraflı OAuth code akışı) ----
  const FB_REDIRECT = typeof window !== "undefined" ? `${window.location.origin}/giris` : "";
  const handleFacebookLogin = () => {
    const appId = socialProviders.facebook_app_id;
    if (!appId) { toast.error("Facebook girişi yapılandırılmamış"); return; }
    try { sessionStorage.setItem("fb_redirect_to", _redirectTo); } catch {}
    const url = `https://www.facebook.com/v20.0/dialog/oauth?client_id=${encodeURIComponent(appId)}`
      + `&redirect_uri=${encodeURIComponent(FB_REDIRECT)}`
      + `&scope=${encodeURIComponent("email,public_profile")}`
      + `&response_type=code&state=facebook`;
    window.location.href = url;
  };
  // FB dönüşü: /giris?code=...&state=facebook → kodu backend'e verip giriş yap.
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    if (q.get("state") !== "facebook" || !q.get("code")) return;
    const code = q.get("code");
    window.history.replaceState({}, "", "/giris"); // kod tekrar kullanılmasın
    (async () => {
      setLoading(true);
      try {
        const res = await axios.post(`${API}/auth/facebook`, { code, redirect_uri: FB_REDIRECT });
        if (res.data?.token) {
          loginWithToken(res.data.token, res.data.user);
          toast.success("Facebook ile giriş başarılı!");
          let to = "/hesabim";
          try { to = sessionStorage.getItem("fb_redirect_to") || to; } catch {}
          navigate(to);
        }
      } catch (err) {
        toast.error(err.response?.data?.detail || "Facebook ile giriş başarısız");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Apple Sign In JS SDK — sağlayıcı aktif + Services ID girildiyse yükle & init et.
  useEffect(() => {
    if (!socialProviders.apple || !socialProviders.apple_client_id) return;
    const initApple = () => {
      if (!window.AppleID?.auth) return;
      try {
        window.AppleID.auth.init({
          clientId: socialProviders.apple_client_id,   // Services ID (ör. com.example.web)
          scope: "name email",
          redirectURI: `${window.location.origin}/giris`,  // Apple'da Return URL olarak kayıtlı olmalı
          usePopup: true,
        });
      } catch { /* init hatası sessiz */ }
    };
    if (window.AppleID?.auth) { initApple(); return; }
    let s = document.getElementById("appleid-script");
    if (!s) {
      s = document.createElement("script");
      s.id = "appleid-script";
      s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";
      s.async = true;
      document.body.appendChild(s);
    }
    s.addEventListener("load", initApple);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socialProviders.apple, socialProviders.apple_client_id]);

  const handleAppleLogin = async () => {
    if (!window.AppleID?.auth) { toast.error("Apple girişi henüz yüklenmedi, tekrar deneyin"); return; }
    setLoading(true);
    try {
      const resp = await window.AppleID.auth.signIn();
      const idToken = resp?.authorization?.id_token;
      if (!idToken) throw new Error("identity_token yok");
      // Ad-soyad Apple'dan YALNIZ ilk girişte gelir (sonraki girişlerde boş) — backend zaten
      // hesabı Apple'ın imzaladığı 'sub' ile eşler, isim yalnız görünürlük içindir.
      let userName = "";
      const nm = resp?.user?.name;
      if (nm) userName = `${nm.firstName || ""} ${nm.lastName || ""}`.trim();
      const res = await axios.post(`${API}/auth/apple`, { identity_token: idToken, user_name: userName });
      if (res.data?.token) {
        loginWithToken(res.data.token, res.data.user);
        toast.success("Apple ile giriş başarılı!");
        navigate(_redirectTo);
      }
    } catch (err) {
      const code = err?.error || "";
      if (code === "popup_closed_by_user" || code === "user_cancelled_authorize" || code === "user_trigger_new_signin_flow") {
        // kullanıcı vazgeçti → sessiz
      } else {
        toast.error(err.response?.data?.detail || "Apple ile giriş başarısız");
      }
    } finally { setLoading(false); }
  };

  useEffect(() => {
    const googleClientId = socialProviders.google_client_id || BUILD_GOOGLE_CLIENT_ID;
    if (!socialProviders.google || !googleClientId) return;
    if (embeddedGoogle) {
      setGoogleStatus({
        phase: "embedded",
        message: "Bu uygulama içi tarayıcı Google penceresini desteklemeyebilir.",
      });
      return;
    }
    let disposed = false;
    const flow = createGooglePopupFlow({
      exchangeCredential: async (credential) => {
        const res = await axios.post(`${API}/auth/google`, { credential });
        return res.data;
      },
      onSuccess: (result) => {
        if (disposed) return;
        loginWithToken(result.token, result.user);
        try { sessionStorage.removeItem("google_redirect_to"); } catch {}
        setLoading(false);
        setGoogleStatus({ phase: "success", message: "Giriş başarılı, yönlendiriliyorsunuz…" });
        navigate(_redirectTo, { replace: true });
      },
      onError: (code, error) => {
        if (disposed) return;
        const message = error?.response?.data?.detail || googleErrorMessage(code);
        setLoading(false);
        setGoogleStatus({ phase: "error", message });
      },
    });
    googleFlowRef.current = flow;
    const init = () => {
      if (disposed || !window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: (response) => flow.credential(response),
        error_callback: (event) => flow.popupError(event),
        ux_mode: "popup",
        button_auto_select: false,
        auto_select: false,
        itp_support: true,
      });
      if (googleBtnRef.current) {
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline",
          size: "large",
          type: "icon",       // kompakt ikon buton → Facebook ile yan yana sığar
          shape: "square",
          locale: "tr",
          click_listener: () => {
            try { sessionStorage.setItem("google_redirect_to", _redirectTo); } catch {}
            setLoading(true);
            setGoogleStatus({ phase: "popup", message: "Google hesap penceresi bekleniyor…" });
            flow.begin();
          },
        });
        setGoogleStatus((current) => current.phase === "idle" ? { phase: "ready", message: "" } : current);
      }
    };
    if (window.google?.accounts?.id) {
      init();
    } else {
      let s = document.getElementById("gsi-script");
      if (!s) {
        s = document.createElement("script");
        s.id = "gsi-script";
        s.src = "https://accounts.google.com/gsi/client";
        s.async = true;
        s.defer = true;
        document.body.appendChild(s);
      }
      s.addEventListener("load", init);
      s.addEventListener("error", () => {
        if (!disposed) setGoogleStatus({ phase: "error", message: "Google giriş bileşeni yüklenemedi." });
      }, { once: true });
    }
    return () => {
      disposed = true;
      flow.dispose();
      googleFlowRef.current = null;
    };
  }, [socialProviders.google, socialProviders.google_client_id, embeddedGoogle, _redirectTo, loginWithToken, navigate]);

  const handleGoogleRedirectFallback = () => {
    try { sessionStorage.setItem("google_redirect_to", _redirectTo); } catch {}
    setGoogleStatus({ phase: "redirect", message: "Google'ın güvenli giriş sayfasına yönlendiriliyorsunuz…" });
    const url = `${API}/auth/google/login?return_to=${encodeURIComponent(_redirectTo)}`;
    window.location.assign(url);
  };

  useEffect(() => {
    if (user) navigate(_redirectTo, { replace: true });
  }, [user, navigate, _redirectTo]);

  if (user) return <div className="sf-page electro"><div className="container py-10 text-center">Yönlendiriliyorsunuz…</div></div>;

  const submitAs = (mode) => async (e) => {
    e.preventDefault();
    const reg = mode === "register";
    if (reg && (!formData.first_name.trim() || !formData.last_name.trim())) {
      toast.error("Ad ve soyad zorunludur");
      return;
    }
    setIsRegister(reg);
    setLoading(true);
    try {
      if (reg) {
        await register({ ...formData, first_name: formData.first_name.trim(), last_name: formData.last_name.trim() });
        toast.success("Kayıt başarılı!");
      } else {
        await login(formData.email, formData.password);
        toast.success("Giriş başarılı!");
      }
      navigate(_redirectTo);
    } catch (err) {
      toast.error(err.response?.data?.detail || "İşlem başarısız");
    } finally {
      setLoading(false);
    }
  };
  const set = (k) => (e) => setFormData({ ...formData, [k]: e.target.value });

  const social = (
    <>
      {(socialProviders.google || socialProviders.facebook || socialProviders.apple) && (
        <div className="mb-4">
          <div className="d-flex align-items-center flex-wrap">
            {!embeddedGoogle && socialProviders.google && (
              <div ref={googleBtnRef} data-testid="google-login-btn" data-flow-version={GOOGLE_FLOW_VERSION} className="mr-2 mb-2" />
            )}
            {socialProviders.facebook && (
              <button type="button" onClick={handleFacebookLogin} disabled={loading} title="Facebook ile giriş" aria-label="Facebook ile giriş"
                className="btn btn-icon btn-facebook rounded-circle mr-2 mb-2" style={{ background: "#1877F2", color: "#fff" }} data-testid="facebook-login-btn">
                <span className="fab fa-facebook-f btn-icon__inner" />
              </button>
            )}
            {socialProviders.apple && (
              <button type="button" onClick={handleAppleLogin} disabled={loading} title="Apple ile giriş" aria-label="Apple ile giriş"
                className="btn btn-icon btn-dark rounded-circle mr-2 mb-2" data-testid="apple-login-btn">
                <span className="fab fa-apple btn-icon__inner" />
              </button>
            )}
          </div>
          {socialProviders.google && ["error", "embedded"].includes(googleStatus.phase) && (
            <div className="alert alert-warning font-size-13 mt-2" role="alert" data-testid="google-login-status">
              <div className="mb-1">{googleStatus.message}</div>
              <button type="button" onClick={handleGoogleRedirectFallback} disabled={googleStatus.phase === "redirect"} className="btn btn-link p-0 font-size-13" data-testid="google-redirect-fallback">
                Tam sayfa Google girişiyle devam et
              </button>
            </div>
          )}
          {["popup", "exchanging", "redirect", "success"].includes(googleStatus.phase) && googleStatus.message && (
            <p className="font-size-13 text-gray-90" role="status">{googleStatus.message}</p>
          )}
          <div className="font-size-13 text-gray-90">veya e-posta ile devam edin</div>
        </div>
      )}
    </>
  );

  return (
    <div className="sf-page" data-testid="login-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: "Hesabım" }]} />
        <div className="container">
          <div className="mb-4"><h1 className="text-center">Hesabım</h1></div>
          <div className="my-4 my-xl-8">
            <div className="row">
              <div className={`col-md-5 ml-xl-auto mr-md-auto mr-xl-0 mb-8 mb-md-0${isRegister ? " d-none d-md-block" : ""}`}>
                <div className="border-bottom border-color-1 mb-6">
                  <h3 className="d-inline-block section-title mb-0 pb-2 font-size-26">Giriş Yap</h3>
                </div>
                <p className="text-gray-90 mb-4">Tekrar hoş geldiniz! Hesabınıza giriş yapın.</p>
                {social}
                <form onSubmit={submitAs("login")} noValidate={false}>
                  <div className="form-group">
                    <label className="form-label" htmlFor="loginEmail">E-posta adresi <span className="text-danger">*</span></label>
                    <input type="email" className="form-control" id="loginEmail" autoComplete="email" placeholder="E-posta adresi" value={formData.email} onChange={set("email")} required data-testid="email-input" />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="loginPassword">Şifre <span className="text-danger">*</span></label>
                    <input type="password" className="form-control" id="loginPassword" autoComplete="current-password" placeholder="Şifre" value={formData.password} onChange={set("password")} required minLength={6} data-testid="password-input" />
                  </div>
                  <div className="mb-1">
                    <div className="mb-3">
                      <button type="submit" disabled={loading} className="btn btn-primary-dark-w px-5" data-testid="submit-btn">{loading && !isRegister ? "İşleniyor..." : "Giriş Yap"}</button>
                    </div>
                    <div className="mb-2">
                      <button type="button" className="btn btn-link p-0 text-blue" onClick={() => navigate("/sifremi-unuttum")}>Şifrenizi mi unuttunuz?</button>
                    </div>
                    <div className="d-md-none mt-3">
                      <button type="button" className="btn btn-link p-0 text-gray-90" onClick={() => setIsRegister(true)}>Hesabınız yok mu? <strong>Üye olun</strong></button>
                    </div>
                  </div>
                </form>
              </div>
              <div className="col-md-1 d-none d-md-block">
                <div className="flex-content-center h-100">
                  <div className="width-1 bg-1 h-100" />
                  <div className="width-50 height-50 border border-color-1 rounded-circle flex-content-center font-italic bg-white position-absolute">veya</div>
                </div>
              </div>
              <div className={`col-md-5 ml-md-auto ml-xl-0 mr-xl-auto${isRegister ? "" : " d-none d-md-block"}`}>
                <div className="border-bottom border-color-1 mb-6">
                  <h3 className="d-inline-block section-title mb-0 pb-2 font-size-26">Üye Ol</h3>
                </div>
                <p className="text-gray-90 mb-4">Size özel alışveriş deneyiminin avantajlarından yararlanmak için hemen hesap oluşturun.</p>
                <form onSubmit={submitAs("register")}>
                  <div className="row">
                    <div className="col-sm-6 form-group">
                      <label className="form-label" htmlFor="register-first-name">Ad <span className="text-danger">*</span></label>
                      <input type="text" className="form-control" id="register-first-name" autoComplete="given-name" maxLength={100} value={formData.first_name} onChange={set("first_name")} data-testid="first-name-input" />
                    </div>
                    <div className="col-sm-6 form-group">
                      <label className="form-label" htmlFor="register-last-name">Soyad <span className="text-danger">*</span></label>
                      <input type="text" className="form-control" id="register-last-name" autoComplete="family-name" maxLength={100} value={formData.last_name} onChange={set("last_name")} data-testid="last-name-input" />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="registerEmail">E-posta adresi <span className="text-danger">*</span></label>
                    <input type="email" className="form-control" id="registerEmail" autoComplete="email" placeholder="E-posta adresi" value={formData.email} onChange={set("email")} required />
                  </div>
                  <div className="form-group mb-4">
                    <label className="form-label" htmlFor="registerPassword">Şifre <span className="text-danger">*</span></label>
                    <input type="password" className="form-control" id="registerPassword" autoComplete="new-password" placeholder="En az 6 karakter" value={formData.password} onChange={set("password")} required minLength={6} />
                  </div>
                  <p className="text-gray-90 mb-4">Kişisel verileriniz siparişlerinizi yönetmek ve deneyiminizi geliştirmek amacıyla <a href="/sayfa/kvkk" className="text-blue">KVKK Aydınlatma Metni</a>'nde açıklandığı şekilde işlenir.</p>
                  <div className="mb-6">
                    <div className="mb-3">
                      <button type="submit" disabled={loading} className="btn btn-primary-dark-w px-5" data-testid="register-submit-btn">{loading && isRegister ? "İşleniyor..." : "Üye Ol"}</button>
                    </div>
                    <div className="d-md-none">
                      <button type="button" className="btn btn-link p-0 text-gray-90" onClick={() => setIsRegister(false)}>Zaten üye misiniz? <strong>Giriş yapın</strong></button>
                    </div>
                  </div>
                </form>
                <h3 className="font-size-18 mb-3">Üye olarak şunları yapabilirsiniz:</h3>
                <ul className="list-group list-group-borderless">
                  <li className="list-group-item px-0"><i className="fas fa-check mr-2 text-green font-size-16" /> Ödeme adımlarını hızla tamamlayın</li>
                  <li className="list-group-item px-0"><i className="fas fa-check mr-2 text-green font-size-16" /> Siparişlerinizi kolayca takip edin</li>
                  <li className="list-group-item px-0"><i className="fas fa-check mr-2 text-green font-size-16" /> Tüm alışveriş geçmişinize ulaşın</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
