import React, { useState, useEffect } from "react";
import { Plus, Edit, Trash2, ChevronRight, ChevronDown, RefreshCw } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminCategories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    image_url: "",
    parent_id: "",
    is_active: true,
    members_only: false,
    sort_order: 0,
  });

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/categories`);
      setCategories(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        parent_id: formData.parent_id || null
      };

      if (editingCategory) {
        await axios.put(`${API}/categories/${editingCategory.id}`, payload);
        toast.success("Kategori güncellendi");
      } else {
        await axios.post(`${API}/categories`, payload);
        toast.success("Kategori eklendi");
      }
      setModalOpen(false);
      resetForm();
      fetchCategories();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Hata oluştu");
    }
  };

  const handleDelete = async (id) => {
    toast('Kategoriyi silmek istediğinize emin misiniz?', {
      action: {
        label: 'Sil',
        onClick: async () => {
          try {
            const token = localStorage.getItem('token');
            await axios.delete(`${API}/categories/${id}`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            toast.success('Kategori silindi');
            fetchCategories();
          } catch (err) {
            toast.error('Silme başarısız');
          }
        }
      },
      cancel: { label: 'İptal', onClick: () => {} },
      duration: 8000,
    });
  };

  const openEditModal = (category) => {
    setEditingCategory(category);
    setFormData({
      name: category.name,
      slug: category.slug || "",
      image_url: category.image_url || "",
      parent_id: category.parent_id || "",
      is_active: category.is_active,
      members_only: !!category.members_only,
      sort_order: category.sort_order || 0,
    });
    setModalOpen(true);
  };

  const resetForm = () => {
    setEditingCategory(null);
    setFormData({
      name: "", slug: "", description: "", image_url: "", parent_id: "",
      is_active: true, members_only: false, sort_order: 0
    });
  };

  const generateSlug = (name) => {
    return name.toLowerCase()
      .replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's')
      .replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ç/g, 'c')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  };

  const toggleExpand = (id) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedNodes(newExpanded);
  };

  // Build tree structure - safe version with null parent_id handling
  const buildTree = (cats, parentId = null, depth = 0) => {
    if (depth > 10) return []; // prevent infinite recursion
    return cats
      .filter((c) => (c.parent_id ?? null) === parentId)
      .sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999))
      .map((c) => ({
        ...c,
        id: c.id || c._id,
        children: buildTree(cats, c.id, depth + 1),
      }));
  };

  const treeData = buildTree(categories);

  const renderTreeRows = (nodes, level = 0) => {
    return nodes.map((node) => {
      const hasChildren = node.children && node.children.length > 0;
      const isExpanded = expandedNodes.has(node.id) || level === 0;

      return (
        <React.Fragment key={node.id}>
          <tr className="hover:bg-gray-50 border-b">
            <td className="py-3 px-4">
              <div 
                className="flex items-center gap-2" 
                style={{ paddingLeft: `${level * 1.5}rem` }}
              >
                {hasChildren ? (
                  <button onClick={() => toggleExpand(node.id)} className="p-1 hover:bg-gray-200 rounded">
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                ) : (
                  <span className="w-6 h-6 inline-block"></span>
                )}
                {node.image_url ? (
                  <img src={node.image_url} alt="" className="w-8 h-8 object-cover rounded bg-gray-100" />
                ) : (
                  <div className="w-8 h-8 bg-gray-100 rounded" />
                )}
                <span className="font-medium">{node.name}</span>
              </div>
            </td>
            <td className="py-3 px-4 text-gray-500">{node.slug}</td>
            <td className="py-3 px-4">{node.sort_order}</td>
            <td className="py-3 px-4">
              <span className={`px-2 py-1 text-xs rounded ${node.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {node.is_active ? "Aktif" : "Pasif"}
              </span>
            </td>
            <td className="py-3 px-4">
              <div className="flex items-center gap-2">
                <button onClick={() => openEditModal(node)} className="p-1 hover:bg-gray-100 rounded text-blue-600" title="Düzenle">
                  <Edit size={16} />
                </button>
                <button onClick={() => handleDelete(node.id)} className="p-1 hover:bg-gray-100 rounded text-red-500" title="Sil">
                  <Trash2 size={16} />
                </button>
              </div>
            </td>
          </tr>
          {hasChildren && isExpanded && renderTreeRows(node.children, level + 1)}
        </React.Fragment>
      );
    });
  };

  return (
    <div data-testid="admin-categories">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold">Kategori Yönetimi</h1>
          <p className="text-gray-500 text-sm mt-1">Hiyerarşik kategori ağacı</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={async () => {
              try {
                const r = await axios.post(
                  `${API}/integrations/site/categories/sync-missing-from-products`,
                  {},
                  { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }
                );
                const created = r.data?.created_categories || [];
                if (created.length) {
                  toast.success(
                    `${r.data.created_count} eksik kategori bulundu: ${created
                      .map((c) => c.name)
                      .join(", ")} (${r.data.relinked_products} ürün bağlandı)`
                  );
                } else {
                  toast.success("Eksik kategori yok ✓");
                }
                fetchCategories();
              } catch (e) {
                toast.error("Eksik kategori senkronizasyonu başarısız");
              }
            }}
            className="flex items-center gap-2 bg-amber-500 text-white px-3 py-2 rounded hover:bg-amber-600 text-sm"
            title="Ürünlerden eksik kategorileri otomatik oluştur"
            data-testid="backfill-missing-cats"
          >
            <RefreshCw size={16} />
            Eksik Kategorileri Yükle
          </button>
          <button 
            onClick={() => { resetForm(); setModalOpen(true); }}
            className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded hover:bg-gray-800"
          >
            <Plus size={18} />
            Yeni Kategori
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50 text-gray-600 font-medium border-b">
              <tr>
                <th className="py-3 px-4">Kategori Adı</th>
                <th className="py-3 px-4">Slug</th>
                <th className="py-3 px-4">Sıra</th>
                <th className="py-3 px-4">Durum</th>
                <th className="py-3 px-4">İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-8">Yükleniyor...</td>
                </tr>
              ) : categories.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-gray-500">Kategori bulunamadı</td>
                </tr>
              ) : (
                renderTreeRows(treeData)
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingCategory ? "Kategori Düzenle" : "Yeni Kategori"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Üst Kategori</label>
              <select
                value={formData.parent_id}
                onChange={(e) => setFormData({ ...formData, parent_id: e.target.value })}
                className="w-full border px-3 py-2 rounded text-sm"
              >
                <option value="">Ana Kategori (Yok)</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id} disabled={editingCategory?.id === cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Kategori Adı *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value, slug: generateSlug(e.target.value) })}
                required
                className="w-full border px-3 py-2 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Slug</label>
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                className="w-full border px-3 py-2 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Görsel URL</label>
              <input
                type="url"
                value={formData.image_url}
                onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
                className="w-full border px-3 py-2 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Sıra</label>
              <input
                type="number"
                value={formData.sort_order}
                onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value) || 0 })}
                className="w-full border px-3 py-2 rounded text-sm"
              />
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              <span className="text-sm">Aktif</span>
            </label>
            <label className="flex items-center gap-2" data-testid="cat-members-only">
              <input
                type="checkbox"
                checked={!!formData.members_only}
                onChange={(e) => setFormData({ ...formData, members_only: e.target.checked })}
              />
              <span className="text-sm">Sadece üyelere özel <span className="text-gray-400">(giriş yapmayan göremez)</span></span>
            </label>
            <div className="flex justify-end gap-2 pt-4 border-t">
              <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 border rounded hover:bg-gray-50">
                İptal
              </button>
              <button type="submit" className="px-4 py-2 bg-black text-white rounded hover:bg-gray-800">
                {editingCategory ? "Güncelle" : "Ekle"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
