import { useState, useEffect } from "react";
import { sanitizeHtml } from "../lib/sanitizeHtml";
import { useParams } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";
import IconDocPage from "./IconDocPage";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Bu sayfalar ikon-kart düzeninde gösterilir (İade & Değişim, İletişim). İçerik yine
// TAMAMEN CMS'ten gelir; sadece SUNUM ikonlu — kullanıcı metni panelden düzenler.
const ICON_LAYOUT_SLUGS = new Set(["iade-kosullari", "iletisim"]);

export default function StaticPage() {
  const { slug } = useParams();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPage();
  }, [slug]);

  const fetchPage = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/pages/${slug}`);
      setPage(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const iconLayout = page && ICON_LAYOUT_SLUGS.has(slug);
  return (
    <div className="sf-page" data-testid="static-page">
      <Header />
      <div className="electro">
        <Breadcrumb items={[{ label: page?.title || (loading ? "…" : "Sayfa") }]} />
      </div>
      {iconLayout ? (
        <div className="container-main py-6 md:py-8 max-w-3xl">
          <IconDocPage page={page} />
        </div>
      ) : (
        <main id="content" role="main" className="electro el-page">
          <div className="container">
            {loading ? (
              <div className="mb-12">
                <div className="el-skel mx-auto mb-4" style={{ height: 36, width: "40%" }} />
                <div className="el-skel mb-2" style={{ height: 16 }} />
                <div className="el-skel mb-2" style={{ height: 16, width: "80%" }} />
              </div>
            ) : page ? (
              <>
                <div className="mb-12 text-center">
                  <h1>{page.title}</h1>
                  {page.updated_at && <p className="text-gray-44">Son güncelleme: {new Date(page.updated_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}</p>}
                </div>
                <div className="mb-12 el-prose mx-xl-10" dangerouslySetInnerHTML={{ __html: sanitizeHtml(page.content) }} />
              </>
            ) : (
              <div className="mb-12 text-center">
                <h1 className="font-size-sl-72 font-weight-light mb-3">404!</h1>
                <p className="text-gray-90 font-size-20 font-weight-light">Sayfa bulunamadı.</p>
              </div>
            )}
          </div>
        </main>
      )}
      <Footer />
    </div>
  );
}
