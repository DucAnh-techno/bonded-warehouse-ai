import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Lock, 
  Unlock, 
  Sparkles, 
  Sliders, 
  Search, 
  Send, 
  X,
  FileText,
  Inbox,
  Loader2,
  ChevronDown,
  ChevronUp,
  Edit3,
  Truck,
  FileCheck,
  Container,
  Tag,
  DollarSign,
  ShieldCheck
} from 'lucide-react';
import { api } from '../services/api';
import { 
  Shipment, 
  ReconciliationMatrix,
  ValidationRuleSetting,
  ShipmentApprovalResponse,
  ConsolidatedShipmentHeader,
  DocumentItem
} from '../types';

interface ReconciliationPageProps {
  initialShipmentId?: string;
  onNavigateDocuments?: (shipmentId?: string) => void;
  onNavigateWMS?: (shipmentId?: string) => void;
}

export const ReconciliationPage: React.FC<ReconciliationPageProps> = ({ 
  initialShipmentId,
  onNavigateDocuments,
  onNavigateWMS
}) => {
  // Shipments state
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>(initialShipmentId || '');
  const [isLoadingShipments, setIsLoadingShipments] = useState<boolean>(true);

  // Reconciliation state
  const [matrixData, setMatrixData] = useState<ReconciliationMatrix | null>(null);
  const [isLoadingMatrix, setIsLoadingMatrix] = useState<boolean>(false);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);
  const [isAiBatchReconciling, setIsAiBatchReconciling] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Consolidated Header & Transport info state
  const [consolidatedHeader, setConsolidatedHeader] = useState<ConsolidatedShipmentHeader | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [isSkuMatrixExpanded, setIsSkuMatrixExpanded] = useState<boolean>(false);

  // Staff Manual Edit Modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [editFormData, setEditFormData] = useState({
    entry_date: '',
    partner_name: '',
    customs_declaration_no: '',
    doc_id: '',
    container_numbers: '',
    seal_numbers: '',
    total_gross_weight_kg: '',
    measurement_cbm: '',
    total_packages: '',
    package_unit: '',
    reason: 'Hiệu chỉnh dữ liệu vận chuyển và đối soát theo thực tế chứng từ'
  });
  const [isSavingEdit, setIsSavingEdit] = useState<boolean>(false);

  // Sub-tabs: 'matrix' | 'rules'
  const [activeSubTab, setActiveSubTab] = useState<'matrix' | 'rules'>('matrix');

  // Filters for Matrix
  const [skuSearchQuery, setSkuSearchQuery] = useState<string>('');
  const [skuMatchFilter, setSkuMatchFilter] = useState<'ALL' | 'MATCHED' | 'MISMATCHED'>('ALL');

  // Rules Configuration state
  const [ruleSettings, setRuleSettings] = useState<ValidationRuleSetting[]>([]);
  const [isLoadingRules, setIsLoadingRules] = useState<boolean>(false);
  const [savingRuleCode, setSavingRuleCode] = useState<string | null>(null);

  // Approval Modal state
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState<boolean>(false);
  const [approverName, setApproverName] = useState<string>('Cán bộ Giám sát Kho Ngoại quan');
  const [approvalNotes, setApprovalNotes] = useState<string>('Hồ sơ đã được đối soát tất định và kiểm tra đầy đủ.');
  const [isSubmittingApproval, setIsSubmittingApproval] = useState<boolean>(false);

  // Load Shipments list on mount
  useEffect(() => {
    loadShipments();
  }, []);

  // Update selected shipment when initialShipmentId changes
  useEffect(() => {
    if (initialShipmentId) {
      setSelectedShipmentId(initialShipmentId);
    }
  }, [initialShipmentId]);

  // Load Matrix & Discrepancies when selectedShipmentId changes
  useEffect(() => {
    if (selectedShipmentId) {
      loadReconciliationMatrix(selectedShipmentId);
    } else {
      setMatrixData(null);
    }
  }, [selectedShipmentId]);

  // Load Rule Settings when opening rules tab
  useEffect(() => {
    if (activeSubTab === 'rules') {
      loadRuleSettings();
    }
  }, [activeSubTab]);

  const loadShipments = async () => {
    setIsLoadingShipments(true);
    try {
      const data = await api.getShipments();
      setShipments(data);
      if (data.length > 0) {
        // If current selection is empty or invalid, pick the first valid shipment
        if (!selectedShipmentId || !data.some(s => s.id === selectedShipmentId)) {
          const target = initialShipmentId && data.some(s => s.id === initialShipmentId) 
            ? initialShipmentId 
            : data[0].id;
          setSelectedShipmentId(target);
        }
      }
    } catch (err: any) {
      console.error('Failed to load shipments:', err);
    } finally {
      setIsLoadingShipments(false);
    }
  };

  const loadConsolidatedHeader = async (shipmentId: string) => {
    try {
      const data = await api.getConsolidatedShipmentHeader(shipmentId);
      setConsolidatedHeader(data);
    } catch (err) {
      console.warn('Failed to load consolidated header:', err);
    }
  };

  const loadShipmentDocs = async (shipmentId: string) => {
    try {
      const list = await api.getShipmentDocuments(shipmentId);
      setDocs(list);
    } catch (err) {
      console.warn('Failed to load docs:', err);
    }
  };

  const loadReconciliationMatrix = async (shipmentId: string) => {
    if (!shipmentId) return;
    setIsLoadingMatrix(true);
    setActionMessage(null);
    try {
      // Use getReconciliationMatrix to load the saved reconciliation result from database
      const data = await api.getReconciliationMatrix(shipmentId);
      setMatrixData(data);
      loadConsolidatedHeader(shipmentId);
      loadShipmentDocs(shipmentId);
    } catch (err: any) {
      console.error('Failed to load saved reconciliation matrix:', err);
      setActionMessage({ type: 'error', text: 'Không thể tải kết quả đối soát đã lưu: ' + (err.message || 'Lỗi kết nối') });
    } finally {
      setIsLoadingMatrix(false);
    }
  };

  const handleOpenEditModal = () => {
    const s = shipments.find(item => item.id === selectedShipmentId);
    const primaryDoc = docs.find(d => ['PACKING_LIST', 'BILL_OF_LADING', 'ARRIVAL_NOTICE', 'CUSTOMS_DECLARATION'].includes(d.document_type)) || docs[0];

    const rawGw = consolidatedHeader?.total_gross_weight_kg?.value?.replace(/[^0-9.]/g, '') || '';
    const rawCbm = consolidatedHeader?.measurement_cbm?.value?.replace(/[^0-9.]/g, '') || '';
    const rawPkg = consolidatedHeader?.total_packages?.value?.replace(/[^0-9]/g, '') || '';
    const rawUnit = consolidatedHeader?.package_unit?.value || '';

    setEditFormData({
      entry_date: s?.entry_date || consolidatedHeader?.entry_date || new Date().toISOString().slice(0, 10),
      partner_name: s?.partner_name || consolidatedHeader?.consignee?.value || consolidatedHeader?.tenant_name?.value || '',
      customs_declaration_no: s?.customs_declaration_no || consolidatedHeader?.customs_declaration_no?.value || '',
      doc_id: primaryDoc?.id || '',
      container_numbers: consolidatedHeader?.container_numbers?.join(', ') || '',
      seal_numbers: consolidatedHeader?.seal_numbers?.join(', ') || '',
      total_gross_weight_kg: rawGw,
      measurement_cbm: rawCbm,
      total_packages: rawPkg,
      package_unit: rawUnit || 'CARTONS',
      reason: 'Cán bộ kiểm hóa hiệu chỉnh thông tin thực tế'
    });
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!selectedShipmentId) return;
    setIsSavingEdit(true);
    setActionMessage(null);
    try {
      // 1. Update Shipment
      await api.updateShipment(selectedShipmentId, {
        entry_date: editFormData.entry_date || undefined,
        partner_name: editFormData.partner_name || undefined,
        customs_declaration_no: editFormData.customs_declaration_no || undefined,
      });

      // 2. If doc_id selected, update document extraction header
      if (editFormData.doc_id) {
        const patchValues: Record<string, any> = {};
        if (editFormData.container_numbers) {
          patchValues.container_numbers = editFormData.container_numbers.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
        }
        if (editFormData.seal_numbers) {
          patchValues.seal_numbers = editFormData.seal_numbers.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
        }
        if (editFormData.total_gross_weight_kg && !isNaN(parseFloat(editFormData.total_gross_weight_kg))) {
          patchValues.total_gross_weight_kg = parseFloat(editFormData.total_gross_weight_kg);
        }
        if (editFormData.measurement_cbm && !isNaN(parseFloat(editFormData.measurement_cbm))) {
          patchValues.measurement_cbm = parseFloat(editFormData.measurement_cbm);
        }
        if (editFormData.total_packages && !isNaN(parseInt(editFormData.total_packages, 10))) {
          patchValues.total_packages = parseInt(editFormData.total_packages, 10);
        }
        if (editFormData.package_unit) {
          patchValues.package_unit = editFormData.package_unit.trim().toUpperCase();
        }

        if (Object.keys(patchValues).length > 0) {
          await api.updateDocumentHeader(
            editFormData.doc_id,
            patchValues,
            editFormData.reason.trim() || 'Hiệu chỉnh dữ liệu vận chuyển'
          );
        }
      }

      setIsEditModalOpen(false);
      setActionMessage({
        type: 'success',
        text: 'Đã cập nhật thông tin thành công! Hệ thống đã tự động thu hồi phê duyệt và tái đối soát lại toàn bộ hồ sơ.'
      });
      await loadReconciliationMatrix(selectedShipmentId);
      await loadShipments();
    } catch (err: any) {
      console.error('Failed to save manual edits:', err);
      setActionMessage({
        type: 'error',
        text: 'Lỗi khi lưu hiệu chỉnh: ' + (err.message || 'Lỗi hệ thống')
      });
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleTriggerReconcile = async () => {
    if (!selectedShipmentId) return;
    setIsReconciling(true);
    setActionMessage(null);
    try {
      // Manual re-run of deterministic cross-document reconciliation
      const data = await api.reconcileShipment(selectedShipmentId);
      setMatrixData(data);
      await loadConsolidatedHeader(selectedShipmentId);
      setActionMessage({
        type: 'success',
        text: `Tái đối soát thành công! Tìm thấy ${data.error_count} lỗi chặn (ERROR), ${data.warning_count} cảnh báo trên tổng số ${data.total_skus} SKU.`
      });
      loadShipments();
    } catch (err: any) {
      console.error('Reconciliation failed:', err);
      setActionMessage({ type: 'error', text: 'Lỗi khi chạy đối soát: ' + (err.message || 'Vui lòng thử lại') });
    } finally {
      setIsReconciling(false);
    }
  };

  const handleBatchReconcileWithAi = async () => {
    if (!selectedShipmentId) return;
    setIsAiBatchReconciling(true);
    setActionMessage(null);
    try {
      await api.batchReconcileShipment(selectedShipmentId);
      await loadReconciliationMatrix(selectedShipmentId);
      await loadShipments();
      setActionMessage({
        type: 'success',
        text: 'AI đã trích xuất và đối soát chéo toàn bộ hồ sơ thành công! Kết quả đã được lưu vĩnh viễn vào cơ sở dữ liệu.'
      });
    } catch (err: any) {
      console.error('Batch AI extraction failed:', err);
      setActionMessage({ type: 'error', text: 'Lỗi khi trích xuất AI toàn bộ hồ sơ: ' + (err.message || 'Lỗi kết nối') });
    } finally {
      setIsAiBatchReconciling(false);
    }
  };

  const loadRuleSettings = async () => {
    setIsLoadingRules(true);
    try {
      const rules = await api.getRuleConfigurations();
      setRuleSettings(rules);
    } catch (err: any) {
      console.error('Failed to load rules:', err);
    } finally {
      setIsLoadingRules(false);
    }
  };

  const handleUpdateRule = async (rule: ValidationRuleSetting) => {
    setSavingRuleCode(rule.rule_code);
    try {
      const updated = await api.updateRuleConfiguration(rule.rule_code, {
        enabled: rule.enabled,
        tolerance: rule.tolerance,
        severity: rule.severity
      });
      setRuleSettings(prev => prev.map(r => r.rule_code === updated.rule_code ? updated : r));
      setActionMessage({ type: 'success', text: `Đã cập nhật quy tắc ${rule.rule_code}.` });
      if (selectedShipmentId) {
        handleTriggerReconcile();
      }
    } catch (err: any) {
      console.error('Failed to update rule:', err);
      setActionMessage({ type: 'error', text: 'Lỗi khi cập nhật quy tắc: ' + (err.message || 'Lỗi kết nối') });
    } finally {
      setSavingRuleCode(null);
    }
  };

  // Gatekeeper Approval
  const handleSubmitApproval = async () => {
    if (!selectedShipmentId) return;
    setIsSubmittingApproval(true);
    try {
      const res: ShipmentApprovalResponse = await api.approveShipmentValidation(
        selectedShipmentId,
        approverName,
        approvalNotes
      );
      if (res.success) {
        setIsApprovalModalOpen(false);
        setActionMessage({
          type: 'success',
          text: 'Phê duyệt hồ sơ đối soát thành công! Lô hàng đã mở khóa truyền sang hệ thống kho (WMS).'
        });
        loadReconciliationMatrix(selectedShipmentId);
        loadShipments();
      } else {
        setActionMessage({
          type: 'error',
          text: res.message_vi + (res.blocking_reasons?.length ? `: ${res.blocking_reasons.join('; ')}` : '')
        });
      }
    } catch (err: any) {
      console.error('Approval failed:', err);
      setActionMessage({ type: 'error', text: 'Phê duyệt thất bại: ' + (err.message || 'Lỗi hệ thống') });
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  const selectedShipment = shipments.find(s => s.id === selectedShipmentId);
  const openErrorsCount = matrixData?.discrepancies?.filter(d => d && d.severity === 'ERROR' && d.status === 'OPEN').length ?? 0;
  const isApprovalBlocked = openErrorsCount > 0 || (selectedShipment ? selectedShipment.status === 'DISCREPANT' : false);
  const isApproved = selectedShipment?.approval_status === 'APPROVED';

  // Defensive Filtered SKU list
  const filteredSkus = (matrixData?.sku_matrix || []).filter(item => {
    if (!item) return false;
    const sku = (item.sku || '').toLowerCase();
    const desc = (item.description_vi || '').toLowerCase();
    const query = (skuSearchQuery || '').toLowerCase();
    const matchesSearch = sku.includes(query) || desc.includes(query);
    if (!matchesSearch) return false;

    if (skuMatchFilter === 'MATCHED') return item.is_matched;
    if (skuMatchFilter === 'MISMATCHED') return !item.is_matched;
    return true;
  });

  if (isLoadingShipments) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-slate-500 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        <p className="text-sm font-medium">Đang tải danh sách lô hàng...</p>
      </div>
    );
  }

  if (shipments.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-500 shadow-sm max-w-lg mx-auto my-8">
        <Inbox className="w-12 h-12 mx-auto mb-3 text-slate-400" />
        <h3 className="text-base font-bold text-slate-900 mb-1">Chưa có lô hàng nào trong hệ thống</h3>
        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
          Vui lòng tạo lô hàng mới tại tab "Dashboard & Lô Hàng" trước khi tiến hành đối soát và xử lý sai lệch.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner / Shipment Selector */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg">
                <Layers className="w-5 h-5" />
              </span>
              <h2 className="text-lg font-bold text-slate-900">
                Đối soát chứng từ & xử lý sai lệch
              </h2>
            </div>
          </div>

          {/* Shipment Select & Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-2">
              <label htmlFor="shipment-select" className="text-xs font-semibold text-slate-600 whitespace-nowrap">Lô Hàng:</label>
              <select
                id="shipment-select"
                value={selectedShipmentId}
                onChange={(e) => setSelectedShipmentId(e.target.value)}
                className="text-xs font-semibold bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-xs"
              >
                {shipments.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.shipment_code} — {s.customs_declaration_no || 'Chưa có số TK'} ({s.status})
                  </option>
                ))}
              </select>
            </div>

            {/* Batch AI Extraction Button */}
            <button
              onClick={handleBatchReconcileWithAi}
              disabled={isAiBatchReconciling || isReconciling || !selectedShipmentId}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
              title="Kích hoạt AI Gemini đọc lại toàn bộ chứng từ và tự động đối soát lưu vào hệ thống"
            >
              {isAiBatchReconciling ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>AI Đang Đối Soát...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Trích Xuất & Đối Soát AI</span>
                </>
              )}
            </button>

            {/* Run Deterministic Reconcile Button */}
            <button
              onClick={handleTriggerReconcile}
              disabled={isReconciling || isAiBatchReconciling || !selectedShipmentId}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
              title="Chạy lại bộ quy tắc đối soát toán học trên dữ liệu đã trích xuất"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isReconciling ? 'animate-spin' : ''}`} />
              <span>Tái Đối Soát</span>
            </button>

            {/* Gatekeeper Approval Button */}
            {isApproved ? (
              <div className="flex items-center gap-2">
                <div className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-emerald-800 bg-emerald-100 border border-emerald-300 rounded-lg">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Đã Phê Duyệt</span>
                </div>
                {onNavigateWMS && (
                  <button
                    onClick={() => onNavigateWMS(selectedShipmentId)}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors cursor-pointer"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Mở Cổng WMS & Xuất Excel</span>
                  </button>
                )}
              </div>
            ) : (
              <button
                onClick={() => setIsApprovalModalOpen(true)}
                disabled={isApprovalBlocked}
                title={isApprovalBlocked ? `Bị chặn phê duyệt: Còn ${openErrorsCount} Lỗi sai` : 'Phê duyệt để mở khóa truyền WMS'}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg shadow-sm transition-colors ${
                  isApprovalBlocked
                    ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                    : 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer'
                }`}
              >
                {isApprovalBlocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                <span>Phê Duyệt Lô Hàng</span>
              </button>
            )}
          </div>
        </div>

        {/* Action Message Alert */}
        {actionMessage && (
          <div className={`mt-4 p-3 rounded-lg text-xs font-medium flex items-center justify-between ${
            actionMessage.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
            actionMessage.type === 'error' ? 'bg-rose-50 text-rose-800 border border-rose-200' :
            'bg-blue-50 text-blue-800 border border-blue-200'
          }`}>
            <span>{actionMessage.text}</span>
            <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-slate-600">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Quick KPI Bar */}
        {matrixData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 mt-4 pt-4 border-t border-slate-100 text-xs">
            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block text-[11px]">Trạng Thái Hồ Sơ</span>
              <span className={`font-bold uppercase ${
                matrixData.validation_status === 'VALIDATED' ? 'text-emerald-600' :
                matrixData.validation_status === 'DISCREPANT' ? 'text-rose-600' : 'text-slate-700'
              }`}>
                {matrixData.validation_status}
              </span>
            </div>

            <div className="p-2.5 bg-slate-50 rounded-lg">
              <span className="text-slate-500 block text-[11px]">Tổng Số SKU</span>
              <span className="font-bold text-slate-900">{matrixData.total_skus} dòng hàng</span>
            </div>

            <div className="p-2.5 bg-emerald-50/60 rounded-lg">
              <span className="text-emerald-700 block text-[11px]">SKU Khớp Tuyệt Đối</span>
              <span className="font-bold text-emerald-700">{matrixData.matched_skus} / {matrixData.total_skus}</span>
            </div>

            <div className="p-2.5 bg-rose-50/60 rounded-lg">
              <span className="text-rose-700 block text-[11px]">Lỗi sai</span>
              <span className="font-bold text-rose-700">{matrixData.error_count} lỗi</span>
            </div>

            <div className="p-2.5 bg-amber-50/60 rounded-lg col-span-2 sm:col-span-1">
              <span className="text-amber-700 block text-[11px]">Cảnh Báo (WARNING)</span>
              <span className="font-bold text-amber-700">{matrixData.warning_count} lưu ý</span>
            </div>
          </div>
        )}
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex border-b border-slate-200 gap-4">
        <button
          onClick={() => setActiveSubTab('matrix')}
          className={`pb-3 text-sm font-semibold flex items-center gap-1.5 transition-colors border-b-2 ${
            activeSubTab === 'matrix'
              ? 'border-indigo-600 text-indigo-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileCheck className="w-4 h-4" />
          <span>Thông Tin Chung & Vận Chuyển · Ma Trận SKU ({matrixData?.total_skus ?? 0})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('rules')}
          className={`pb-3 text-sm font-semibold flex items-center gap-1.5 transition-colors border-b-2 ${
            activeSubTab === 'rules'
              ? 'border-indigo-600 text-indigo-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Cấu Hình Quy Tắc & Dung Sai</span>
        </button>
      </div>

      {/* SUB-TAB 1: General & Transport Primary View + Collapsible SKU Matrix */}
      {activeSubTab === 'matrix' && (
        <div className="space-y-5">
          {/* 14-FIELD x 7-DOCUMENT CROSS-DOCUMENT RECONCILIATION MATRIX */}
          {consolidatedHeader?.field_matrix && consolidatedHeader.field_matrix.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 bg-slate-900 text-white flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold text-sm text-white">
                      Ma trận đối soát
                    </h3>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleOpenEditModal}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-emerald-300 text-xs font-semibold rounded-lg border border-slate-700 transition-colors cursor-pointer self-start lg:self-auto shrink-0"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>Hiệu Chỉnh Dữ Liệu</span>
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200 text-[10px]">
                    <tr>
                      <th className="py-2.5 px-3 min-w-[160px] sticky left-0 bg-slate-100 z-10 border-r border-slate-200">
                        Trường Dữ Liệu
                      </th>
                      <th className="py-2.5 px-2.5 text-center min-w-[125px] border-r border-slate-200/70">BL (Vận đơn)</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[125px] border-r border-slate-200/70">AN (Báo hàng đến)</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[125px] border-r border-slate-200/70 bg-indigo-50/50">SC (Tùy chọn)</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[135px] border-r border-slate-200/70">INV (Hóa đơn)</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[135px] border-r border-slate-200/70">PL (Đóng gói)</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[140px] border-r border-slate-200/70">Tờ khai HQ</th>
                      <th className="py-2.5 px-2.5 text-center min-w-[135px] border-r border-slate-200">Hợp đồng kho</th>
                      <th className="py-2.5 px-3 text-center min-w-[120px]">Kết Quả</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-800">
                    {consolidatedHeader.field_matrix.map((row) => {
                      const docCols = ['BL', 'AN', 'SC', 'INV', 'PL', 'TK', 'HD'] as const;
                      return (
                        <tr
                          key={row.field_key}
                          className={`hover:bg-slate-50/80 ${
                            row.status === 'MISMATCHED'
                              ? 'bg-rose-50/25'
                              : row.status === 'WARNING'
                              ? 'bg-amber-50/20'
                              : ''
                          }`}
                        >
                          <td className="py-2.5 px-3 font-bold text-slate-900 sticky left-0 bg-white z-10 border-r border-slate-200">
                            <div className="flex items-center">
                              <span>{row.label_vi}</span>
                            </div>
                          </td>

                          {docCols.map((col) => {
                            const isApplicable = row.applicable_docs.includes(col);
                            const val = row.values_by_doc?.[col];
                            if (!isApplicable) {
                              return (
                                <td
                                  key={col}
                                  className="py-2.5 px-2 text-center text-slate-300 bg-slate-50/50 border-r border-slate-100 select-none align-top"
                                  title="Không yêu cầu đối soát ở chứng từ này"
                                >
                                  —
                                </td>
                              );
                            }

                            // Xác định màu nền shading cho ô cần đối soát (màu đậm rõ ràng)
                            // - Nếu chưa có dữ liệu / chưa trích xuất: xám đậm vừa (bg-slate-200/80)
                            // - Nếu dòng bị lệch dữ liệu (MISMATCHED): đỏ tươi rõ rệt (bg-rose-100 text-rose-950 border-rose-300)
                            // - Nếu bình thường / khớp: xanh lá tươi đậm rõ (bg-emerald-100 text-emerald-950 border-emerald-300)
                            const isMissing = !val || val.trim() === '';
                            const isMismatched = row.status === 'MISMATCHED';

                            const cellBgClass = isMissing
                              ? 'bg-slate-200/75 text-slate-500 border-slate-300'
                              : isMismatched
                              ? 'bg-rose-100 text-rose-950 border-rose-300 font-medium'
                              : 'bg-emerald-100/80 text-emerald-950 border-emerald-300/80';

                            return (
                              <td
                                key={col}
                                className={`py-2.5 px-2.5 border-r border-slate-200 align-top transition-colors ${cellBgClass}`}
                              >
                                {val ? (
                                  <div className="font-mono text-[11px] font-semibold break-words leading-snug">
                                    {val}
                                  </div>
                                ) : (
                                  <div className="text-[10px] italic text-slate-400">
                                    {col === 'SC' && !consolidatedHeader.has_sale_contract ? '(Không có SC)' : 'Chưa có'}
                                  </div>
                                )}
                              </td>
                            );
                          })}

                          <td className="py-2.5 px-3 text-center align-middle">
                            {row.status === 'MATCHED' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                                <span>Khớp</span>
                              </span>
                            )}
                            {row.status === 'MISMATCHED' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                                <AlertTriangle className="w-3 h-3 text-rose-600 shrink-0" />
                                <span>Lệch</span>
                              </span>
                            )}
                            {row.status === 'WARNING' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                                <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                                <span>Cảnh báo</span>
                              </span>
                            )}
                            {row.status === 'SINGLE_SOURCE' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-50 text-sky-700 border border-sky-200">
                                <span>1 nguồn</span>
                              </span>
                            )}
                            {row.status === 'MISSING' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500 border border-slate-200">
                                <span>Chưa có</span>
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* CONSOLIDATED GENERAL & TRANSPORT CARDS (Moved from DocumentExtractionPanel) */}
          {consolidatedHeader && (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2.5">
                  <div className="p-2 bg-indigo-100 text-indigo-700 rounded-lg">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-900">Thông Tin Chung & Vận Chuyển</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Tổng hợp toàn bộ thông tin chuẩn xác và đối soát của bộ hồ sơ lô hàng
                    </p>
                  </div>
                </div>
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold self-start sm:self-auto ${
                  consolidatedHeader.status === 'VALIDATED' 
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : consolidatedHeader.status === 'DISCREPANT'
                    ? 'bg-rose-100 text-rose-800 border border-rose-200'
                    : 'bg-amber-100 text-amber-800 border border-amber-200'
                }`}>
                  {consolidatedHeader.status}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {/* Section 1: Customs & Warehouse */}
                <div className="p-4 bg-slate-50/60 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                    <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-indigo-600" />
                      <span>1. Định Danh Tờ Khai HQ & Kho Ngoại Quan</span>
                    </h4>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Số Tờ khai HQ:</span>
                      <strong className="text-slate-900 font-mono text-sm block">
                        {consolidatedHeader.customs_declaration_no?.value || selectedShipment?.customs_declaration_no || 'Chưa có'}
                      </strong>
                      {consolidatedHeader.customs_declaration_no?.source_document_name && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100 mt-1">
                          <FileText className="w-2.5 h-2.5" />
                          {consolidatedHeader.customs_declaration_no.source_document_name}
                        </span>
                      )}
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Loại hình tờ khai:</span>
                      <strong className="text-slate-800 block">
                        {consolidatedHeader.declaration_type?.value || 'C11 (Nhập kho ngoại quan)'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Ngày đăng ký tờ khai:</span>
                      <strong className="text-slate-800 block">
                        {consolidatedHeader.declaration_date?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Kho ngoại quan tiếp nhận:</span>
                      <strong className="text-slate-800 block">
                        {consolidatedHeader.warehouse_name?.value || 'Kho Ngoại Quan U&I'}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Section 2: Commercial & POs */}
                <div className="p-4 bg-slate-50/60 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                    <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                      <DollarSign className="w-4 h-4 text-emerald-600" />
                      <span>2. Hóa Đơn Thương Mại & Đơn Hàng PO</span>
                    </h4>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Số Hóa đơn (CI):</span>
                      <strong className="text-slate-900 font-mono text-sm block">
                        {consolidatedHeader.commercial_invoice_no?.value || '—'}
                      </strong>
                      {consolidatedHeader.commercial_invoice_no?.source_document_name && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100 mt-1">
                          <FileText className="w-2.5 h-2.5" />
                          {consolidatedHeader.commercial_invoice_no.source_document_name}
                        </span>
                      )}
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Ngày hóa đơn:</span>
                      <strong className="text-slate-800 block">
                        {consolidatedHeader.invoice_date?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Tổng trị giá Hóa đơn:</span>
                      <strong className="text-emerald-700 font-mono text-sm block">
                        {consolidatedHeader.total_invoice_value?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Điều kiện Incoterms:</span>
                      <strong className="text-slate-800 font-mono block">
                        {consolidatedHeader.incoterms?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Số Phiếu đóng gói (PL):</span>
                      <strong className="text-slate-800 font-mono block">
                        {consolidatedHeader.packing_list_no?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Đơn đặt hàng (PO refs):</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {consolidatedHeader.po_numbers && consolidatedHeader.po_numbers.length > 0 ? (
                          consolidatedHeader.po_numbers.map((po, i) => (
                            <span key={i} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded font-mono font-semibold">
                              PO# {po}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400 italic">—</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section 3: Transport, Containers & Seals */}
                <div className="p-4 bg-slate-50/60 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                    <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                      <Container className="w-4 h-4 text-blue-600" />
                      <span>3. Vận Tải, Container & Niêm Phong Chì</span>
                    </h4>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Số Vận đơn (B/L No):</span>
                      <strong className="text-blue-900 font-mono text-sm block">
                        {consolidatedHeader.bill_of_lading_no?.value || '—'}
                      </strong>
                      {consolidatedHeader.bill_of_lading_no?.source_document_name && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-100 mt-1">
                          <FileText className="w-2.5 h-2.5" />
                          {consolidatedHeader.bill_of_lading_no.source_document_name}
                        </span>
                      )}
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Tàu & Chuyến (Vessel / Voyage):</span>
                      <strong className="text-slate-800 block">
                        {consolidatedHeader.vessel_voyage?.value || '—'}
                      </strong>
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-500 block text-[11px] mb-1">
                      Danh sách Container ({consolidatedHeader.container_numbers.length}):
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {consolidatedHeader.container_numbers && consolidatedHeader.container_numbers.length > 0 ? (
                        consolidatedHeader.container_numbers.map((c, i) => (
                          <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-800 border border-blue-200 rounded font-mono font-bold flex items-center gap-1">
                            <Container className="w-3 h-3 text-blue-500" />
                            {c}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-400 italic">—</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-500 block text-[11px] mb-1">
                      Danh sách Số Chì niêm phong ({consolidatedHeader.seal_numbers.length}):
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {consolidatedHeader.seal_numbers && consolidatedHeader.seal_numbers.length > 0 ? (
                        consolidatedHeader.seal_numbers.map((s, i) => (
                          <span key={i} className="px-2 py-0.5 bg-purple-50 text-purple-800 border border-purple-200 rounded font-mono font-bold flex items-center gap-1">
                            <Tag className="w-3 h-3 text-purple-500" />
                            {s}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-400 italic">—</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Section 4: Packaging, Weight & Partners */}
                <div className="p-4 bg-slate-50/60 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200/80">
                    <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                      <Truck className="w-4 h-4 text-amber-600" />
                      <span>4. Quy Cách Đóng Gói, Trọng Lượng & Chủ Thể</span>
                    </h4>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2 bg-amber-50/50 rounded-lg border border-amber-100">
                      <span className="text-slate-500 block text-[11px]">Tổng số kiện:</span>
                      <strong className="text-amber-900 font-mono text-sm block">
                        {consolidatedHeader.total_packages?.value || '—'}
                      </strong>
                      {consolidatedHeader.total_packages?.source_document_name && (
                        <span className="text-[9px] text-amber-700 block truncate" title={consolidatedHeader.total_packages.source_document_name}>
                          {consolidatedHeader.total_packages.source_document_name}
                        </span>
                      )}
                    </div>
                    <div className="p-2 bg-white rounded-lg border border-slate-200">
                      <span className="text-slate-500 block text-[11px]">Gross Weight:</span>
                      <strong className="text-slate-900 font-mono text-sm block">
                        {consolidatedHeader.total_gross_weight_kg?.value || '—'}
                      </strong>
                    </div>
                    <div className="p-2 bg-white rounded-lg border border-slate-200">
                      <span className="text-slate-500 block text-[11px]">Net Weight:</span>
                      <strong className="text-slate-900 font-mono text-sm block">
                        {consolidatedHeader.total_net_weight_kg?.value || '—'}
                      </strong>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-200/80 space-y-2">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Người xuất khẩu / Shipper / Bán:</span>
                      <strong className="text-slate-800 block text-xs">
                        {consolidatedHeader.shipper?.value || '—'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Người nhập khẩu / Consignee / Mua:</span>
                      <strong className="text-slate-800 block text-xs">
                        {consolidatedHeader.consignee?.value || '—'}
                      </strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}



          {/* COLLAPSIBLE ACCORDION: SKU Reconciliation Matrix */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            {/* Clickable Header Bar (Collapsed by default) */}
            <button
              type="button"
              onClick={() => setIsSkuMatrixExpanded(prev => !prev)}
              className="w-full px-5 py-4 bg-slate-50 hover:bg-slate-100 flex items-center justify-between transition-colors text-left cursor-pointer border-b border-slate-200"
            >
              <div className="flex items-center gap-2.5">
                <Layers className="w-4 h-4 text-indigo-600" />
                <div>
                  <span className="font-bold text-sm text-slate-900">
                    Ma Trận Đối Chiếu SKU ({matrixData?.error_count ?? 0} dòng lỗi / {matrixData?.total_skus ?? 0} tổng dòng)
                  </span>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Đối chiếu chi tiết từng mã SKU, đơn giá, số lượng giữa Hóa đơn (CI) và Phiếu đóng gói (PL) · Bấm để {isSkuMatrixExpanded ? 'thu gọn' : 'mở rộng chi tiết'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {matrixData?.error_count ? (
                  <span className="px-2.5 py-1 text-xs font-bold bg-rose-100 text-rose-800 rounded-full border border-rose-200">
                    {matrixData.error_count} lỗi chặn WMS
                  </span>
                ) : (
                  <span className="px-2.5 py-1 text-xs font-bold bg-emerald-100 text-emerald-800 rounded-full border border-emerald-200">
                    Khớp toàn bộ SKU
                  </span>
                )}
                {isSkuMatrixExpanded ? (
                  <ChevronUp className="w-5 h-5 text-slate-500" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-slate-500" />
                )}
              </div>
            </button>

            {/* Accordion Content (Revealed when expanded) */}
            {isSkuMatrixExpanded && (
              <div className="p-5 space-y-4 animate-in fade-in duration-200">
                {/* Filter Bar */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="relative w-full sm:w-80">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      value={skuSearchQuery}
                      onChange={(e) => setSkuSearchQuery(e.target.value)}
                      placeholder="Tìm SKU, Part Number, Tên hàng..."
                      className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <span className="text-xs text-slate-500">Lọc khớp:</span>
                    <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-50 text-xs">
                      <button
                        onClick={() => setSkuMatchFilter('ALL')}
                        className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                          skuMatchFilter === 'ALL' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'
                        }`}
                      >
                        Tất cả
                      </button>
                      <button
                        onClick={() => setSkuMatchFilter('MATCHED')}
                        className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                          skuMatchFilter === 'MATCHED' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600'
                        }`}
                      >
                        Khớp 100%
                      </button>
                      <button
                        onClick={() => setSkuMatchFilter('MISMATCHED')}
                        className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                          skuMatchFilter === 'MISMATCHED' ? 'bg-white text-rose-700 shadow-xs' : 'text-slate-600'
                        }`}
                      >
                        Có sai lệch
                      </button>
                    </div>
                  </div>
                </div>

                {/* Matrix Table */}
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-left text-xs text-slate-700">
                    <thead className="bg-slate-50 text-[11px] font-bold text-slate-600 uppercase border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-3">Mã SKU / Mô Tả</th>
                        <th className="px-3 py-3">Mã HS (Invoice)</th>
                        <th className="px-3 py-3 text-right">SL Hóa Đơn (CI)</th>
                        <th className="px-3 py-3 text-right">SL Packing List</th>
                        <th className="px-3 py-3 text-right">Đơn Giá CI</th>
                        <th className="px-3 py-3 text-center">ĐVT</th>
                        <th className="px-3 py-3 text-center">Trạng Thái</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {isLoadingMatrix ? (
                        <tr>
                          <td colSpan={7} className="py-12 text-center text-slate-400">
                            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                            <span>Đang nạp dữ liệu đối soát đã lưu...</span>
                          </td>
                        </tr>
                      ) : filteredSkus.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-12 text-center text-slate-400 space-y-3">
                            <Inbox className="w-8 h-8 mx-auto text-slate-300" />
                            <p className="font-medium text-slate-600">Lô hàng chưa có dữ liệu dòng hàng SKU hoặc chưa trích xuất.</p>
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={handleBatchReconcileWithAi}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700"
                              >
                                <Sparkles className="w-3.5 h-3.5" />
                                <span>Kích Hoạt Trích Xuất & Đối Soát AI</span>
                              </button>
                              {onNavigateDocuments && (
                                <button
                                  onClick={() => onNavigateDocuments(selectedShipmentId)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold hover:bg-slate-200"
                                >
                                  <FileText className="w-3.5 h-3.5" />
                                  <span>Xem / Tải Thêm Chứng Từ</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ) : (
                        filteredSkus.map((item, idx) => {
                          const hasQtyMismatch = 
                            (item.qty_packing_list !== undefined && item.qty_invoice !== undefined && item.qty_packing_list !== item.qty_invoice);

                          return (
                            <tr key={idx} className={`hover:bg-slate-50/80 transition-colors ${!item.is_matched ? 'bg-rose-50/30' : ''}`}>
                              <td className="px-3 py-2.5">
                                <span className="font-bold text-slate-900 block">{item.sku || 'N/A'} · PO: {item.po_reference || '—'}</span>
                                <span className="text-[11px] text-slate-500 line-clamp-1">{item.description_vi || item.sku}</span>
                              </td>
                              <td className="px-3 py-2.5 font-mono text-[11px]">{item.hs_code_invoice || "—"}</td>
                              <td className={`px-3 py-2.5 text-right font-medium ${hasQtyMismatch ? 'text-rose-600 font-bold bg-rose-50/50 rounded' : ''}`}>
                                {item.qty_invoice !== undefined && item.qty_invoice !== null ? item.qty_invoice.toLocaleString() : '—'}
                              </td>
                              <td className={`px-3 py-2.5 text-right font-medium ${hasQtyMismatch ? 'text-rose-600 font-bold bg-rose-50/50 rounded' : ''}`}>
                                {item.qty_packing_list !== undefined && item.qty_packing_list !== null ? item.qty_packing_list.toLocaleString() : '—'}
                              </td>
                              <td className="px-3 py-2.5 text-right text-slate-800">
                                {item.unit_price_invoice !== undefined && item.unit_price_invoice !== null ? `$${item.unit_price_invoice.toFixed(2)}` : '—'}
                              </td>
                              <td className="px-3 py-2.5 text-center text-slate-600">{item.uom || '—'}</td>
                              <td className="px-3 py-2.5 text-center">
                                {item.is_matched ? (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                                    <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
                                    Khớp
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800 border border-rose-200" title={item.discrepancies?.join('\n') || ''}>
                                    <AlertTriangle className="w-3 h-3 mr-1 text-rose-600" />
                                    Lệch ({item.discrepancies?.length ?? 0})
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}



      {/* SUB-TAB 3: Rules Configuration */}
      {activeSubTab === 'rules' && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Quản Lý Quy Tắc Đối Soát & Ngưỡng Dung Sai</h3>
              <p className="text-xs text-slate-500">Cấu hình bật/tắt và dung sai toán học cho từng điều kiện đối soát hải quan.</p>
            </div>
            <button
              onClick={loadRuleSettings}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
              title="Tải lại cài đặt"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-3">
            {isLoadingRules ? (
              <div className="py-8 text-center text-slate-400">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                <span>Đang tải cấu hình quy tắc...</span>
              </div>
            ) : ruleSettings.map((rule) => {
              const isSaving = savingRuleCode === rule.rule_code;
              return (
                <div key={rule.rule_code} className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 transition-colors bg-slate-50/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-xs">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold bg-slate-800 text-white px-2 py-0.5 rounded text-[11px]">
                        {rule.rule_code}
                      </span>
                      <span className="font-bold text-slate-900 text-sm">{rule.name_vi}</span>
                      <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                        {rule.category}
                      </span>
                    </div>
                    <p className="text-slate-600 text-xs">{rule.description_vi}</p>
                  </div>

                  {/* Settings Form for this rule */}
                  <div className="flex flex-wrap items-center gap-3">
                    {/* Tolerance Input if applicable */}
                    {rule.tolerance !== null && (
                      <div className="flex items-center gap-1.5">
                        <label htmlFor={`tol-${rule.rule_code}`} className="text-slate-500 font-semibold">Dung sai:</label>
                        <input
                          id={`tol-${rule.rule_code}`}
                          type="number"
                          step="0.001"
                          value={rule.tolerance ?? ''}
                          onChange={(e) => {
                            const val = e.target.value === '' ? null : parseFloat(e.target.value);
                            setRuleSettings(prev => prev.map(r => r.rule_code === rule.rule_code ? { ...r, tolerance: val } : r));
                          }}
                          className="w-20 px-2 py-1 text-xs border border-slate-300 rounded bg-white text-slate-800 font-mono"
                        />
                      </div>
                    )}

                    {/* Severity Select */}
                    <div className="flex items-center gap-1.5">
                      <label htmlFor={`sev-${rule.rule_code}`} className="text-slate-500 font-semibold">Mức độ:</label>
                      <select
                        id={`sev-${rule.rule_code}`}
                        value={rule.severity}
                        onChange={(e) => {
                          const val = e.target.value as any;
                          setRuleSettings(prev => prev.map(r => r.rule_code === rule.rule_code ? { ...r, severity: val } : r));
                        }}
                        className="px-2 py-1 text-xs border border-slate-300 rounded bg-white text-slate-800 font-semibold"
                      >
                        <option value="ERROR">ERROR</option>
                        <option value="WARNING">WARNING</option>
                      </select>
                    </div>

                    {/* Enabled Toggle */}
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        onChange={(e) => {
                          const val = e.target.checked;
                          setRuleSettings(prev => prev.map(r => r.rule_code === rule.rule_code ? { ...r, enabled: val } : r));
                        }}
                        className="rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="font-semibold text-slate-700">{rule.enabled ? 'Đang bật' : 'Tắt'}</span>
                    </label>

                    {/* Save Button */}
                    <button
                      onClick={() => handleUpdateRule(rule)}
                      disabled={isSaving}
                      className="px-3 py-1 text-xs font-semibold rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      {isSaving ? 'Đang lưu...' : 'Lưu'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}



      {/* APPROVAL MODAL */}
      {isApprovalModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6 space-y-4 text-xs animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <h3 className="text-sm font-bold text-slate-900">Phê Duyệt Hồ Sơ Lô Hàng</h3>
              </div>
              <button onClick={() => setIsApprovalModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-slate-600 leading-relaxed">
              Lô hàng <strong className="text-slate-900">{selectedShipment?.shipment_code}</strong> đã vượt qua toàn bộ quy tắc đối soát bắt buộc và không còn lỗi nghiêm trọng.
            </p>

            <div className="space-y-1">
              <label htmlFor="app-name-input" className="font-bold text-slate-700 block">Cán bộ phê duyệt:</label>
              <input
                id="app-name-input"
                type="text"
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="app-notes-input" className="font-bold text-slate-700 block">Ghi chú phê duyệt:</label>
              <textarea
                id="app-notes-input"
                rows={2}
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
              <button
                onClick={() => setIsApprovalModalOpen(false)}
                className="px-3.5 py-2 font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Hủy
              </button>
              <button
                onClick={handleSubmitApproval}
                disabled={isSubmittingApproval}
                className="px-4 py-2 font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50 transition-colors shadow-sm"
              >
                {isSubmittingApproval ? 'Đang lưu...' : 'Xác Nhận Phê Duyệt & Mở Khóa WMS'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Staff Manual Edit Modal (HITL Field Editing) */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-xl w-full p-6 space-y-4 my-8 animate-in fade-in duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 bg-indigo-100 rounded-lg text-indigo-700">
                  <Edit3 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-slate-900">
                    Hiệu Chỉnh Thông Tin Vận Chuyển & Hồ Sơ (HITL)
                  </h3>
                  <p className="text-xs text-slate-500">
                    Lô hàng: <span className="font-mono font-bold text-slate-800">{selectedShipment?.shipment_code}</span>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsEditModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Invalidation warning banner */}
            <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl text-amber-900 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <span className="font-bold">Cảnh báo thu hồi phê duyệt:</span>
                <p className="text-amber-800 leading-relaxed text-[11px]">
                  Mọi thao tác chỉnh sửa thông tin thủ công sẽ <strong>tự động thu hồi trạng thái phê duyệt</strong> (nếu lô hàng đã được duyệt) và <strong>kích hoạt tái đối soát tự động</strong> để bảo đảm tính toàn vẹn dữ liệu xuất sang WMS.
                </p>
              </div>
            </div>

            {/* Edit Form */}
            <form onSubmit={(e) => { e.preventDefault(); handleSaveEdit(); }} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Ngày vào kho thực tế (Staff Input) <span className="text-rose-500">*</span>:
                  </label>
                  <input
                    type="date"
                    required
                    value={editFormData.entry_date}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, entry_date: e.target.value }))}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Số Tờ khai Hải quan:
                  </label>
                  <input
                    type="text"
                    value={editFormData.customs_declaration_no}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, customs_declaration_no: e.target.value }))}
                    placeholder="VD: 104567890120"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Chủ hàng / Người nhập khẩu / Bên thuê kho:
                </label>
                <input
                  type="text"
                  value={editFormData.partner_name}
                  onChange={(e) => setEditFormData(prev => ({ ...prev, partner_name: e.target.value }))}
                  placeholder="Tên doanh nghiệp..."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              {docs.length > 0 && (
                <div className="pt-2 border-t border-slate-200">
                  <label className="font-bold text-slate-700 block mb-1">
                    Đồng bộ sang chứng từ thành phần:
                  </label>
                  <select
                    value={editFormData.doc_id}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, doc_id: e.target.value }))}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500"
                  >
                    {docs.map(d => (
                      <option key={d.id} value={d.id}>
                        {d.original_filename} ({d.document_type})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Số Container (phân cách dấu phẩy):
                  </label>
                  <input
                    type="text"
                    value={editFormData.container_numbers}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, container_numbers: e.target.value }))}
                    placeholder="VD: TGHU1234567, EMCU7654321"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Số Chì Niêm Phong (Seal):
                  </label>
                  <input
                    type="text"
                    value={editFormData.seal_numbers}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, seal_numbers: e.target.value }))}
                    placeholder="VD: EMC123456"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Số kiện (Packages):
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={editFormData.total_packages}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, total_packages: e.target.value }))}
                    placeholder="VD: 12"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    ĐVT kiện:
                  </label>
                  <input
                    type="text"
                    value={editFormData.package_unit}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, package_unit: e.target.value }))}
                    placeholder="VD: CARTONS"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Gross Weight (kg):
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={editFormData.total_gross_weight_kg}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, total_gross_weight_kg: e.target.value }))}
                    placeholder="VD: 12.0"
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Thể tích CBM (m³):
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editFormData.measurement_cbm}
                  onChange={(e) => setEditFormData(prev => ({ ...prev, measurement_cbm: e.target.value }))}
                  placeholder="VD: 1.50"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Lý do hiệu chỉnh (Ghi nhận Audit Trail) <span className="text-rose-500">*</span>:
                </label>
                <input
                  type="text"
                  required
                  value={editFormData.reason}
                  onChange={(e) => setEditFormData(prev => ({ ...prev, reason: e.target.value }))}
                  placeholder="VD: Khớp theo bản gốc biên bản bàn giao và vận đơn"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  disabled={isSavingEdit}
                  className="px-3.5 py-2 font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isSavingEdit ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang lưu & đối soát lại...</span>
                    </>
                  ) : (
                    <span>Lưu Hiệu Chỉnh & Tái Đối Soát</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
