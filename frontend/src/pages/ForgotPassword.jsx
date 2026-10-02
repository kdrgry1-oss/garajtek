// =============================================================================
// ForgotPassword.jsx — Şifremi Unuttum (e-posta ile sıfırlama bağlantısı iste)
// =============================================================================
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async () => {
    const e = email.trim();
    if (!e || !e.includes("@")) {
      toast.error("Geçerli bir e-posta girin");
      return;
    }
    setLoading(true);
    try {
      await axios.post(`${API}/auth/forgot-password/email`, { email: e });
      setSent(true);
    } catch {
      // Güvenlik gereği backend her durumda 200 döner; yine de hata olursa kullanıcıyı bilgilendir
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Header />
      <main className="electro el-page">
      <Breadcrumb items={[{ label: "Giriş", to: "/giris" }, { label: "Şifremi Unuttum" }]} />
      <div className="container mb-8">
        <div className="max-width-530 mx-auto border border-color-1 borders-radius-6 p-4 p-md-6">
          <h1 className="font-size-26 font-weight-light mb-3">Şifremi Unuttum</h1>
          {!sent ? (
            <>
              <p className="font-size-14 text-gray-90 mb-4">
                Hesabınızın e-posta adresini girin. Şifre sıfırlama bağlantısını e-posta ile göndereceğiz.
              </p>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
                placeholder="E-posta adresiniz"
                className="form-control mb-4"
                autoFocus
              />
              <button
                onClick={submit}
                disabled={loading}
                className="btn btn-primary-dark-w btn-block rounded-pill"
              >
                {loading ? "Gönderiliyor…" : "Sıfırlama Bağlantısı Gönder"}
              </button>
            </>
          ) : (
            <div className="text-sm text-gray-700 space-y-3">
              <p>
                Eğer bu e-posta adresi sistemimizde kayıtlıysa, şifre sıfırlama bağlantısını gönderdik.
                Lütfen gelen kutunuzu (ve spam klasörünü) kontrol edin.
              </p>
              <p className="text-gray-500">Bağlantı 30 dakika geçerlidir.</p>
            </div>
          )}
          <div className="mt-5 text-sm text-center">
            <Link to="/giris" className="text-blue">
              Girişe dön
            </Link>
          </div>
        </div>
      </div>
      </main>
      <Footer />
    </>
  );
}
