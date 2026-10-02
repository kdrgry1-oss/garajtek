// Panel görsel yükleme (POST /api/upload/image) — tam URL döner (eski HomeBlockFields.uploadImageFile).
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BACKEND_ORIGIN = String(process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "").replace(/\/api$/, "");

export async function uploadImageFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await axios.post(`${API}/upload/image`, fd, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }, timeout: 90000,
  });
  const raw = res.data?.url || `/api/upload/files/${res.data?.path}`;
  return raw.startsWith("http") ? raw : `${BACKEND_ORIGIN}${raw}`;
}

export default uploadImageFile;
