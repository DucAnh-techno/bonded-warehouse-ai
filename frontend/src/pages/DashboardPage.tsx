import React, { useEffect, useState } from 'react';
import { 
  Building2, 
  Package, 
  ArrowDownLeft, 
  ArrowUpRight, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  Plus, 
  Search, 
  RefreshCw,
  FileText,
  Filter,
  Trash2,
  Loader2
} from 'lucide-react';


import { api } from '../services/api';
import { Shipment, ShipmentStats, ShipmentStatus } from '../types';
import { CreateShipmentModal } from '../components/shipments/CreateShipmentModal';
import { DashboardSkeleton } from '../components/common/Skeletons';

interface Props {
  onSelectShipment?: (shipmentId: string) => void;
  onNavigateDocuments?: (shipmentId?: string) => void;
}

export const DashboardPage: React.FC<Props> = ({ onSelectShipment, onNavigateDocuments }) => {
  const [stats, setStats] = useState<ShipmentStats | null>(null);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [directionFilter, setDirectionFilter] = useState<string>('ALL');

  // Modal
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [shipmentToDelete, setShipmentToDelete] = useState<Shipment | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  const handleDeleteConfirm = async () => {
    if (!shipmentToDelete) return;
    setDeleting(true);
    try {
      await api.deleteShipment(shipmentToDelete.id);
      setShipments(prev => prev.filter(s => s.id !== shipmentToDelete.id));
      setShipmentToDelete(null);
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Lỗi khi xóa lô hàng.');
    } finally {
      setDeleting(false);
    }
  };

  const fetchData = async () => {

    try {
      setError(null);
      const [statsData, shipmentsData] = await Promise.all([
        api.getShipmentStats().catch(() => null),
        api.getShipments({
          search: search.trim() || undefined,
          status: statusFilter,
          direction: directionFilter,
        }),
      ]);

      if (statsData) setStats(statsData);
      setShipments(shipmentsData);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải dữ liệu dashboard.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [statusFilter, directionFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchData();
  };

  const handleCreated = (newShipment: Shipment) => {
    setShipments(prev => [newShipment, ...prev]);
    fetchData();
  };

  const getStatusBadge = (status: ShipmentStatus) => {
    switch (status) {
      case 'DRAFT':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">Bản nháp</span>;
      case 'EXTRACTING':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">Đang trích xuất</span>;
      case 'RECONCILING':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 border border-purple-200">Đang đối soát</span>;
      case 'DISCREPANT':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-100 text-rose-800 border border-rose-200">Có sai lệch</span>;
      case 'VALIDATED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">Đã hợp lệ</span>;
      case 'APPROVED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-teal-100 text-teal-800 border border-teal-200">Đã phê duyệt</span>;
      case 'TRANSMITTED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-800 border border-sky-200">Đã truyền WMS</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  if (loading && !refreshing) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Building2 className="w-6 h-6 text-emerald-600" />
            <span>Bảng Điều Khiển Lô Hàng Kho Ngoại Quan</span>
          </h2>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setRefreshing(true);
              fetchData();
            }}
            disabled={refreshing}
            className="p-2 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
            title="Làm mới"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center space-x-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Tạo Lô Hàng Mới</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
              <span>Tổng số lô hàng</span>
              <Package className="w-4 h-4 text-slate-400" />
            </div>
            <div className="text-2xl font-bold text-slate-900">{stats.total_shipments}</div>
            <div className="text-[11px] text-slate-400 mt-1">
              {stats.inbound_count} Nhập · {stats.outbound_count} Xuất
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-amber-600 text-xs font-medium mb-1">
              <span>Đang xử lý / Nháp</span>
              <Clock className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl font-bold text-amber-600">
              {stats.draft_count + stats.reconciling_count}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              {stats.draft_count} Nháp · {stats.reconciling_count} Đang soát
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-rose-600 text-xs font-medium mb-1">
              <span>Có sai lệch</span>
              <AlertTriangle className="w-4 h-4 text-rose-500" />
            </div>
            <div className="text-2xl font-bold text-rose-600">{stats.discrepant_count}</div>
            <div className="text-[11px] text-slate-400 mt-1">Yêu cầu can thiệp HITL</div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between text-emerald-600 text-xs font-medium mb-1">
              <span>Đã hợp lệ / Đã duyệt</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="text-2xl font-bold text-emerald-600">
              {stats.validated_count + stats.approved_count}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              {stats.approved_count} Đã phê duyệt ký
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between text-sky-600 text-xs font-medium mb-1">
              <span>Đã truyền WMS</span>
              <Package className="w-4 h-4 text-sky-500" />
            </div>
            <div className="text-2xl font-bold text-sky-600">{stats.transmitted_count}</div>
            <div className="text-[11px] text-slate-400 mt-1">Hoàn tất quy trình kho</div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3" />
          <input
            type="text"
            placeholder="Tìm theo mã lô hàng (SHP-...), số tờ khai hoặc đối tác..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-24 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none"
          />
          <button
            type="submit"
            className="absolute right-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-md transition-colors"
          >
            Tìm kiếm
          </button>
        </form>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
          <div className="flex items-center space-x-1 shrink-0 text-xs text-slate-500">
            <Filter className="w-3.5 h-3.5" />
            <span>Bộ lọc:</span>
          </div>

          <select
            value={directionFilter}
            onChange={(e) => setDirectionFilter(e.target.value)}
            className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white focus:ring-1 focus:ring-emerald-500 outline-none"
          >
            <option value="ALL">Tất cả hướng (In/Out)</option>
            <option value="INBOUND">Nhập kho (Inbound)</option>
            <option value="OUTBOUND">Xuất kho (Outbound)</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white focus:ring-1 focus:ring-emerald-500 outline-none"
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="DRAFT">Bản nháp (DRAFT)</option>
            <option value="RECONCILING">Đang đối soát</option>
            <option value="DISCREPANT">Có sai lệch</option>
            <option value="VALIDATED">Đã hợp lệ</option>
            <option value="APPROVED">Đã phê duyệt</option>
            <option value="TRANSMITTED">Đã truyền WMS</option>
          </select>
        </div>
      </div>

      {/* Shipment Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-600" />
            <span>Đang tải danh sách lô hàng...</span>
          </div>
        ) : error ? (
          <div className="p-6 text-center text-rose-600 text-sm">
            <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
            <span>{error}</span>
          </div>
        ) : shipments.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Package className="w-10 h-10 mx-auto mb-2 text-slate-300" />
            <p className="text-sm font-medium text-slate-700">Chưa có lô hàng nào phù hợp bộ lọc.</p>
            <p className="text-xs text-slate-400 mt-1">Bấm "Tạo Lô Hàng Mới" để bắt đầu tiếp nhận hồ sơ kho ngoại quan.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase">
                  <th className="py-3 px-4">Mã Lô Hàng</th>
                  <th className="py-3 px-4">Hướng Luân Chuyển</th>
                  <th className="py-3 px-4">Số Tờ Khai (VNACCS)</th>
                  <th className="py-3 px-4">Đối Tác / Khách Hàng</th>
                  <th className="py-3 px-4">Số Chứng Từ</th>
                  <th className="py-3 px-4">Trạng Thái Xử Lý</th>
                  <th className="py-3 px-4">Ngày Tiếp Nhận</th>
                  <th className="py-3 px-4 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shipments.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      {s.shipment_code}
                    </td>
                    <td className="py-3 px-4">
                      {s.direction === 'INBOUND' ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                          <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Nhập Kho</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-blue-700 font-medium">
                          <ArrowUpRight className="w-3.5 h-3.5 text-blue-600" />
                          <span>Xuất Kho</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700">
                      {s.customs_declaration_no ? (
                        <span>{s.customs_declaration_no} ({s.declaration_type || 'C11'})</span>
                      ) : (
                        <span className="text-slate-400 italic">Chưa khai báo</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-700 truncate max-w-xs">
                      {s.partner_name || <span className="text-slate-400 italic">--</span>}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-mono">
                        <FileText className="w-3 h-3 text-slate-500" />
                        <span>{s.document_count ?? 0} tệp</span>
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {getStatusBadge(s.status)}
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                      {new Date(s.created_at).toLocaleDateString('vi-VN', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </td>
                    <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                      <button
                        onClick={() => {
                          if (onSelectShipment) onSelectShipment(s.id);
                          if (onNavigateDocuments) onNavigateDocuments(s.id);
                        }}
                        className="px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium rounded text-xs transition-colors cursor-pointer"
                      >
                        Hồ Sơ Chứng Từ
                      </button>
                      <button
                        onClick={() => setShipmentToDelete(s)}
                        className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors inline-flex items-center cursor-pointer"
                        title="Xóa lô hàng này"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateShipmentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreated={handleCreated}
      />

      {/* Delete Confirmation Modal */}
      {shipmentToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center space-x-3 text-rose-600">
              <div className="p-2 bg-rose-100 rounded-lg">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-base text-slate-900">Xác Nhận Xóa Lô Hàng</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Bạn có chắc chắn muốn xóa lô hàng <strong className="font-mono text-slate-900">{shipmentToDelete.shipment_code}</strong>? 
              Toàn bộ hồ sơ chứng từ, dữ liệu trích xuất và tệp đính kèm trên ổ đĩa sẽ bị xóa vĩnh viễn và không thể khôi phục.
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={deleting}
                onClick={() => setShipmentToDelete(null)}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-lg transition-colors"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDeleteConfirm}
                className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
              >
                {deleting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{deleting ? 'Đang xóa...' : 'Xác Nhận Xóa'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

