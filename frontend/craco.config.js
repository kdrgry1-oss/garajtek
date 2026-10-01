// craco.config.js
const path = require("path");
require("dotenv").config();

// ---------------------------------------------------------------------------
// Beyaz etiket: public/index.html'deki %REACT_APP_*% yer tutucuları tanımsız kalırsa
// CRA onları olduğu gibi (ham "%...%") bırakır. Önce CRA'nın .env dosya sırasını
// (.env.<mode>.local → .env.<mode> → .env.local → .env) yükleyip SONRA yalnız
// eksik kalanlara nötr varsayılan veriyoruz (dotenv mevcut değeri ezmez).
// Firma kimliği (ad, logo, iletişim, sosyal) çalışma anında backend ayarlarından gelir.
// ---------------------------------------------------------------------------
(() => {
  const fs = require("fs");
  const mode = process.env.NODE_ENV || "development";
  [`.env.${mode}.local`, `.env.${mode}`, ".env.local", ".env"].forEach((f) => {
    const fp = path.resolve(__dirname, f);
    if (fs.existsSync(fp)) require("dotenv").config({ path: fp });
  });
  const siteUrl = (process.env.REACT_APP_SITE_URL || "").replace(/\/+$/, "");
  const defaults = {
    REACT_APP_SITE_NAME: "Mağaza",
    REACT_APP_SITE_URL: siteUrl,
    REACT_APP_CANONICAL_HOST: "",
    REACT_APP_DEFAULT_OG_IMAGE: `${siteUrl}/og-image.jpg`,
    REACT_APP_CDN_URL: "",
    REACT_APP_GTM_ID: "",
    REACT_APP_POSTHOG_KEY: "",
    REACT_APP_POSTHOG_HOST: "",
  };
  Object.entries(defaults).forEach(([k, v]) => {
    if (process.env[k] === undefined) process.env[k] = v;
  });
  process.env.REACT_APP_SITE_URL = siteUrl; // sondaki "/" kırpılmış hali (canonical = SITE_URL + "/")
  // Vitrin teması CSS'i (public/electro/electro.css) hash'siz bir dosya → içerik özeti sorgu
  // parametresi olur (?v=<özet>): tema güncellenince tarayıcı/Cloudflare eski CSS'i KULLANMAZ.
  try {
    const sum = require("crypto").createHash("md5")
      .update(fs.readFileSync(path.resolve(__dirname, "public/electro/electro.css"))).digest("hex").slice(0, 10);
    process.env.REACT_APP_ELECTRO_CSS_VER = sum;
  } catch (e) {
    process.env.REACT_APP_ELECTRO_CSS_VER = String(Date.now());
  }
})();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    // Production build'de (Cloudflare/CI) ESLint'i kapat — exhaustive-deps gibi
    // zararsız uyarılar CI=true yüzünden "hata" sayılıp build'i durdurmasın.
    // Dev/preview modunda ESLint açık kalır.
    enable: isDevServer,
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

// NOT: emergent.sh 'visual-edits' dev aracı kaldırıldı — tarball'ı (assets.emergent.sh)
// erişilemez olup npm install'ı kilitliyor, Cloudflare build'lerini bozuyordu. Prod/dev'de
// gerekli değil.

module.exports = webpackConfig;
