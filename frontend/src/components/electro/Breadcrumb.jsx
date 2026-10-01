// Electro breadcrumb (bg-gray-13 bg-md-transparent şerit).
import { Link } from "react-router-dom";

export default function Breadcrumb({ items = [], testId = "breadcrumb" }) {
  return (
    <div className="bg-gray-13 bg-md-transparent">
      <div className="container">
        <div className="my-md-3">
          <nav aria-label="breadcrumb" data-testid={testId}>
            <ol className="breadcrumb mb-3 flex-nowrap flex-xl-wrap overflow-auto overflow-xl-visble">
              <li className="breadcrumb-item flex-shrink-0 flex-xl-shrink-1"><Link to="/">Anasayfa</Link></li>
              {items.map((it, i) => {
                const last = i === items.length - 1;
                return (
                  <li key={`${it.label}-${i}`} className={`breadcrumb-item flex-shrink-0 flex-xl-shrink-1${last ? " active" : ""}`} aria-current={last ? "page" : undefined}>
                    {!last && it.to ? <Link to={it.to}>{it.label}</Link> : it.label}
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>
      </div>
    </div>
  );
}
