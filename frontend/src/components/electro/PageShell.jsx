// Vitrin sayfa iskeleti: Header + breadcrumb şeridi + içerik + Footer.
// Kendi Header/Footer'ı olmayan yardımcı sayfalar (iade, ödeme bildirimi) tema içinde açılsın diye.
import Header from "../Header";
import Footer from "../Footer";
import Breadcrumb from "./Breadcrumb";

export default function PageShell({ title, crumbs, children, testId }) {
  return (
    <div className="sf-page" data-testid={testId}>
      <Header />
      <div className="electro el-page" style={{ minHeight: 0 }}>
        <Breadcrumb items={crumbs || [{ label: title }]} />
      </div>
      <div className="el-account-main pb-12">{children}</div>
      <Footer />
    </div>
  );
}
