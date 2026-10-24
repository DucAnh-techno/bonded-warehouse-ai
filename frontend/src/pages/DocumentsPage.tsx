import React, { useCallback, useEffect, useState } from 'react';
import { 
  Loader2, 
  AlertTriangle, 
  Inbox, 
  Sparkles, 
  Trash2, 
  CheckCircle2, 
  AlertCircle,
  XCircle, 
  FileText, 
  ChevronDown,
  ChevronUp,
  ArrowRight
} from 'lucide-react';

import { api } from '../services/api';
import { DocumentItem, Shipment, BatchShipmentReconciliationResponse } from '../types';
import { DocumentViewer } from '../components/documents/DocumentViewer';
import { DocumentsPageSkeleton } from '../components/common/Skeletons';

interface DocumentsPageProps {
  initialShipmentId?: string;
  onNavigateReconciliation?: (shipmentId: string) => void;
}

export const DocumentsPage: React.FC<DocumentsPageProps> = ({ initialShipmentId, onNavigateReconciliation }) => {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [shipmentId, setShipmentId] = useState(initialShipmentId || '');
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconcilingAll, setReconcilingAll] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchShipmentReconciliationResponse | null>(null);
  const [showBatchDetails, setShowBatchDetails] = useState(true);
  const [deletingShipment, setDeletingShipment] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getShipments()
      .then((s) => {
        setShipments(s);
        if (initialShipmentId && s.some(item => item.id === initialShipmentId)) {
          setShipmentId(initialShipmentId);
        } else if (s.length) {
          setShipmentId(s[0].id);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [initialShipmentId]);

  const loadDocs = useCallback(async (id: string) => {
    try {
      const list = await api.getShipmentDocuments(id);
      setDocs(list);
      setSelectedId((cur) => (cur && list.some((d) => d.id === cur) ? cur : list[0]?.id ?? null));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    if (shipmentId) loadDocs(shipmentId);
  }, [shipmentId, loadDocs]);

  const handleBatchReconcile = async () => {
    if (!shipmentId) return;
    setReconcilingAll(true);
    setError(null);
    try {
      const res = await api.batchReconcileShipment(shipmentId);
      setBatchResult(res);
      setShowBatchDetails(true);
      await loadDocs(shipmentId);
      if (onNavigateReconciliation) {
        onNavigateReconciliation(shipmentId);
      }
    } catch (e: any) {
      setError(e.message || 'Lỗi khi trích xuất & đối soát toàn bộ lô hàng.');
    } finally {
      setReconcilingAll(false);
    }
  };

  const handleDeleteShipment = async () => {
    if (!shipmentId) return;
    setDeletingShipment(true);
    try {
      await api.deleteShipment(shipmentId);
      setShowDeleteConfirm(false);
      const updated = await api.getShipments();
      setShipments(updated);
      if (updated.length > 0) {
        setShipmentId(updated[0].id);
      } else {
        setShipmentId('');
        setDocs([]);
      }
    } catch (e: any) {
      setError(e.message || 'Lỗi khi xóa lô hàng.');
    } finally {
      setDeletingShipment(false);
    }
  };

  const handleSetInboundSource = async (newSource: 'DOMESTIC' | 'FOREIGN') => {
    if (!shipmentId) return;
    setError(null);
    try {
      const updated = await api.updateShipment(shipmentId, { inbound_source: newSource });
      setShipments(prev => prev.map(s => s.id === updated.id ? { ...s, ...updated } : s));
    } catch (err: any) {
      setError(err.message || 'Lỗi khi cập nhật nguồn hàng');
    }
  };

  const currentShipment = shipments.find((s) => s.id === shipmentId);
  const selected = docs.find((d) => d.id === selectedId) ?? null;

  if (loading) {
    return <DocumentsPageSkeleton />;
  }

  if (shipments.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <Inbox className="w-10 h-10 mx-auto mb-2" />
        Chưa có lô hàng nào. Hãy tạo lô hàng trước khi tải chứng từ.
        {error && <p className="text-rose-600 mt-2 text-sm">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Unclassified shipment alert */}
      {(!currentShipment?.inbound_source || currentShipment?.requires_classification) && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-900 shadow-xs">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-sm">Hồ sơ chưa được phân loại nguồn hàng nhập kho</p>
              <p className="text-xs text-amber-800 mt-0.5">
                Vui lòng phân loại nguồn nhập để xác định chính xác danh mục chứng từ bắt buộc theo quy định Hải quan:
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => handleSetInboundSource('DOMESTIC')}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              Chọn Nhập nội địa (3 chứng từ bắt buộc)
            </button>
            <button
              onClick={() => handleSetInboundSource('FOREIGN')}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              Chọn Nhập nước ngoài (6 chứng từ bắt buộc)
            </button>
          </div>
        </div>
      )}

      {/* Mandatory documents checklist status */}
      {currentShipment?.inbound_source && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Nguồn hàng:
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                currentShipment.inbound_source === 'DOMESTIC'
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  : 'bg-blue-100 text-blue-800 border border-blue-200'
              }`}>
                {currentShipment.inbound_source === 'DOMESTIC' ? 'Nhập nội địa (3 chứng từ bắt buộc)' : 'Nhập nước ngoài (6 chứng từ bắt buộc)'}
              </span>
              <button
                onClick={() => handleSetInboundSource(currentShipment.inbound_source === 'DOMESTIC' ? 'FOREIGN' : 'DOMESTIC')}
                className="text-[11px] text-slate-500 hover:text-slate-800 underline ml-1 cursor-pointer"
                title="Thay đổi nguồn hàng sẽ tính lại bộ chứng từ bắt buộc và yêu cầu duyệt lại"
              >
                (Đổi sang {currentShipment.inbound_source === 'DOMESTIC' ? 'Nhập nước ngoài' : 'Nhập nội địa'})
              </button>
            </div>
            <span className="text-[11px] text-slate-500 hidden sm:inline">
              Tình trạng bộ chứng từ bắt buộc & Hợp đồng mua bán (SC tùy chọn)
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-1">
            {(currentShipment.inbound_source === 'DOMESTIC'
              ? [
                  { type: 'PACKING_LIST', label: '1. Packing List (PL)', optional: false },
                  { type: 'CUSTOMS_DECLARATION', label: '2. Tờ khai HQ', optional: false },
                  { type: 'COMMERCIAL_INVOICE', label: '3. Invoice (INV)', optional: false },
                  { type: 'SALE_CONTRACT', label: 'SC (Tùy chọn)', optional: true },
                ]
              : [
                  { type: 'BILL_OF_LADING', label: '1. Vận đơn (BL)', optional: false },
                  { type: 'ARRIVAL_NOTICE', label: '2. Báo hàng đến (AN)', optional: false },
                  { type: 'COMMERCIAL_INVOICE', label: '3. Invoice (INV)', optional: false },
                  { type: 'PACKING_LIST', label: '4. Packing List (PL)', optional: false },
                  { type: 'CUSTOMS_DECLARATION', label: '5. Tờ khai HQ', optional: false },
                  { type: 'WAREHOUSE_CONTRACT', label: '6. HĐ thuê kho', optional: false },
                  { type: 'SALE_CONTRACT', label: 'SC (Tùy chọn)', optional: true },
                ]
            ).map((item) => {
              const uploadedDoc = docs.find(d => d.document_type === item.type || (item.type === 'SALE_CONTRACT' && d.document_type === 'PURCHASE_ORDER'));
              return (
                <div
                  key={item.type}
                  className={`p-2 rounded-lg border text-xs flex flex-col justify-between ${
                    uploadedDoc
                      ? 'bg-emerald-50/80 border-emerald-300 text-emerald-950'
                      : item.optional
                      ? 'bg-slate-100/80 border-slate-200 text-slate-600'
                      : 'bg-amber-50/80 border-amber-300 text-amber-950'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-bold truncate">{item.label}</span>
                    {uploadedDoc ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : item.optional ? (
                      <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    ) : (
                      <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    )}
                  </div>
                  <span className="text-[10px] truncate text-slate-500">
                    {uploadedDoc ? uploadedDoc.original_filename : item.optional ? 'Không bắt buộc' : 'Chưa tải (Thiếu)'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Top Toolbar Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <label className="text-xs font-semibold text-slate-700">
              Lô hàng đang chọn:
            </label>
            <select
              className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm font-mono font-semibold text-slate-800 bg-slate-50"
              value={shipmentId}
              onChange={(e) => {
                setShipmentId(e.target.value);
                setBatchResult(null);
              }}
            >
              {shipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.shipment_code} {s.customs_declaration_no ? `(${s.customs_declaration_no})` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleBatchReconcile}
              disabled={reconcilingAll || docs.length === 0}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer"
              title="Gửi toàn bộ chứng từ hiện có vào AI trong 1 prompt để trích xuất và đối soát chéo toàn diện"
            >
              {reconcilingAll ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Đang đối soát toàn bộ ({docs.length} tệp)...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Trích Xuất & Đối Soát Toàn Bộ Hồ Sơ</span>
                </>
              )}
            </button>

            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center space-x-1 px-3 py-2 border border-rose-200 hover:bg-rose-50 text-rose-600 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
              title="Xóa toàn bộ lô hàng này"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Xóa Lô Hàng</span>
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* BATCH RECONCILIATION RESULT CARD */}
      {batchResult && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4 animate-in fade-in duration-200">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center space-x-2.5">
              <div className={`p-2 rounded-lg ${
                batchResult.overall_validity === 'VALID'
                  ? 'bg-emerald-100 text-emerald-700'
                  : batchResult.overall_validity === 'INVALID'
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-amber-100 text-amber-700'
              }`}>
                {batchResult.overall_validity === 'VALID' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : batchResult.overall_validity === 'INVALID' ? (
                  <XCircle className="w-5 h-5" />
                ) : (
                  <AlertTriangle className="w-5 h-5" />
                )}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="font-bold text-base text-slate-900">
                    Kết Quả Trích Xuất & Đối Soát Toàn Bộ Hồ Sơ Lô Hàng
                  </h3>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                    batchResult.overall_validity === 'VALID'
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : batchResult.overall_validity === 'INVALID'
                      ? 'bg-rose-100 text-rose-800 border border-rose-300'
                      : 'bg-amber-100 text-amber-800 border border-amber-300'
                  }`}>
                    {batchResult.overall_validity === 'VALID'
                      ? 'ĐẠT (HỢP LỆ)'
                      : batchResult.overall_validity === 'INVALID'
                      ? 'KHÔNG ĐẠT (CÓ SAI LỆCH)'
                      : 'CẦN LƯU Ý'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Đã đối chiếu chéo số lượng, mã HS, đơn giá, container và chữ ký chứng từ trong 1 lượt phân tích Gemini AI.
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              {onNavigateReconciliation && (
                <button
                  onClick={() => onNavigateReconciliation(shipmentId)}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-xs cursor-pointer"
                >
                  <span>Chuyển Sang Đối Soát & Xử Lý Lỗi</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => setShowBatchDetails(prev => !prev)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
                title={showBatchDetails ? "Thu gọn" : "Mở rộng"}
              >
                {showBatchDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {showBatchDetails && (
            <div className="space-y-4 text-xs">
              {/* AI Validity Summary */}
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
                <span className="font-semibold text-slate-700 block mb-1">
                  Đánh giá chi tiết của AI và Động cơ đối soát:
                </span>
                <p className="text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
                  {batchResult.validity_reason}
                </p>
              </div>

              {/* Discrepancies Table */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
                    Sai lệch phát hiện được ({batchResult.discrepancies.length})
                  </span>
                </div>

                {batchResult.discrepancies.length === 0 ? (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Không có mâu thuẫn số liệu nào giữa Tờ khai, Hóa đơn thương mại, Phiếu đóng gói và Vận đơn.</span>
                  </div>
                ) : (
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-left border-collapse">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold text-[10px]">
                        <tr>
                          <th className="py-2 px-3">Mã Quy Tắc</th>
                          <th className="py-2 px-3">Mức Độ</th>
                          <th className="py-2 px-3">Trường Dữ Liệu</th>
                          <th className="py-2 px-3">Mô Tả Sai Lệch</th>
                          <th className="py-2 px-3">Chứng Từ A</th>
                          <th className="py-2 px-3">Chứng Từ B</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {batchResult.discrepancies.map((d, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/60">
                            <td className="py-2 px-3 font-mono font-medium text-slate-800">{d.rule_code}</td>
                            <td className="py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                d.severity === 'ERROR'
                                  ? 'bg-rose-100 text-rose-700'
                                  : 'bg-amber-100 text-amber-700'
                              }`}>
                                {d.severity}
                              </span>
                            </td>
                            <td className="py-2 px-3 font-medium text-slate-800">{d.field_name}</td>
                            <td className="py-2 px-3 text-slate-700">{d.description_vi}</td>
                            <td className="py-2 px-3 font-mono text-slate-600">
                              {d.source_doc_a ? `${d.source_doc_a}: ${d.value_a ?? '--'}` : '--'}
                            </td>
                            <td className="py-2 px-3 font-mono text-slate-600">
                              {d.source_doc_b ? `${d.source_doc_b}: ${d.value_b ?? '--'}` : '--'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Documents Summary Grid */}
              <div>
                <span className="font-bold text-slate-800 uppercase tracking-wider text-[11px] block mb-2">
                  Hồ sơ chứng từ được đối chiếu ({batchResult.documents.length})
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {batchResult.documents.map((docItem, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                      <div className="flex items-center space-x-1.5 font-bold text-slate-900">
                        <FileText className="w-3.5 h-3.5 text-indigo-600" />
                        <span className="truncate">{docItem.document_type_detected}</span>
                      </div>
                      <p className="text-slate-600 font-mono text-[11px]">
                        Số: {docItem.document_number || 'Chưa nhận diện'}
                      </p>
                      <p className="text-slate-500 text-[11px]">
                        Ngày: {docItem.issue_date || '--'} · {docItem.items.length} dòng SKU
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Documents selector and viewer */}
      {docs.length === 0 ? (
        <div className="text-center py-12 text-slate-500 bg-white border border-dashed border-slate-300 rounded-xl">
          Lô hàng này chưa có chứng từ. Hãy tải lên chứng từ bằng thanh công cụ phía trên.
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs font-semibold text-slate-500 mr-1">Tài liệu đã tải:</span>
            {docs.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
                  d.id === selectedId
                    ? 'bg-slate-900 text-white border-slate-900 shadow-2xs'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {d.original_filename}
              </button>
            ))}
          </div>
          {selected && (
            <DocumentViewer
              document={selected}
              onDocumentChanged={(u) => setDocs((prev) => prev.map((d) => (d.id === u.id ? u : d)))}
            />
          )}
        </>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && currentShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-5 space-y-4">
            <div className="flex items-center space-x-3 text-rose-600">
              <div className="p-2 bg-rose-100 rounded-lg">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-base text-slate-900">Xác Nhận Xóa Lô Hàng</h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Bạn có chắc chắn muốn xóa lô hàng <strong className="font-mono text-slate-900">{currentShipment.shipment_code}</strong>? 
              Toàn bộ {docs.length} tệp chứng từ và dữ liệu đối soát liên quan sẽ bị xóa vĩnh viễn trên hệ thống.
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={deletingShipment}
                onClick={() => setShowDeleteConfirm(false)}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-lg transition-colors"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                disabled={deletingShipment}
                onClick={handleDeleteShipment}
                className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
              >
                {deletingShipment && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{deletingShipment ? 'Đang xóa...' : 'Xác Nhận Xóa'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

