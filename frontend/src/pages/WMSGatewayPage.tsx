import React, { useState, useEffect, useMemo } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  FileSpreadsheet, 
  Send, 
  ShieldCheck, 
  Lock, 
  Unlock, 
  RefreshCw, 
  Clock, 
  ArrowRight, 
  Layers, 
  Eye, 
  Server, 
  Database,
  Check,
  AlertCircle
} from 'lucide-react';
import { api } from '../services/api';
import { WMSGatewaySkeleton } from '../components/common/Skeletons';
import { 
  Shipment, 
  WMSEligibilityResponse, 
  WMSInboundReceiptPayload, 
  WMSReceipt, 
  WMSTransmissionRecord 
} from '../types';

interface WMSGatewayPageProps {
  initialShipmentId?: string;
  onSelectShipment?: (id: string) => void;
  onNavigateReconciliation?: (shipmentId?: string) => void;
}

export const WMSGatewayPage: React.FC<WMSGatewayPageProps> = ({
  initialShipmentId,
  onSelectShipment,
  onNavigateReconciliation
}) => {
  // Shipments state
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>(initialShipmentId || '');
  const [isLoadingShipments, setIsLoadingShipments] = useState(false);

  // WMS status and transmission state
  const [eligibility, setEligibility] = useState<WMSEligibilityResponse | null>(null);
  const [payloadPreview, setPayloadPreview] = useState<WMSInboundReceiptPayload | null>(null);
  const [transmissions, setTransmissions] = useState<WMSTransmissionRecord[]>([]);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);

  // Approval form state
  const [approverName, setApproverName] = useState('Nguyễn Văn Quản Trị');
  const [approvalNotes, setApprovalNotes] = useState('Hồ sơ đầy đủ, đối soát khớp 100%, đồng ý nhập kho ngoại quan.');
  const [isApproving, setIsApproving] = useState(false);

  // Transmission state
  const [isTransmitting, setIsTransmitting] = useState(false);
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [transmissionSuccessMsg, setTransmissionSuccessMsg] = useState<string | null>(null);
  const [transmissionErrorMsg, setTransmissionErrorMsg] = useState<string | null>(null);

  // Excel state
  const [isExportingExcel, setIsExportingExcel] = useState(false);

  // Sub-tabs: 'transmission' | 'ledger'
  const [activeSubTab, setActiveSubTab] = useState<'transmission' | 'ledger'>('transmission');

  // Mock WMS Receipts Ledger state
  const [mockReceipts, setMockReceipts] = useState<WMSReceipt[]>([]);
  const [selectedReceipt, setSelectedReceipt] = useState<WMSReceipt | null>(null);
  const [isLoadingReceipts, setIsLoadingReceipts] = useState(false);

  // Fetch shipments on mount
  useEffect(() => {
    fetchShipments();
  }, []);

  // Update selectedShipmentId if prop changes
  useEffect(() => {
    if (initialShipmentId) {
      setSelectedShipmentId(initialShipmentId);
    }
  }, [initialShipmentId]);

  // Fetch status, payload preview and transmissions when selected shipment changes
  useEffect(() => {
    if (selectedShipmentId) {
      fetchShipmentWMSData(selectedShipmentId);
    }
  }, [selectedShipmentId]);

  // Fetch receipts when switching to ledger tab
  useEffect(() => {
    if (activeSubTab === 'ledger') {
      fetchMockReceipts();
    }
  }, [activeSubTab]);

  const fetchShipments = async () => {
    setIsLoadingShipments(true);
    try {
      const data = await api.getShipments();
      setShipments(data);
      if (data.length > 0 && !selectedShipmentId) {
        setSelectedShipmentId(data[0].id);
      }
    } catch (err) {
      console.error('Lỗi tải danh sách lô hàng:', err);
    } finally {
      setIsLoadingShipments(false);
    }
  };

  const fetchShipmentWMSData = async (shipmentId: string) => {
    setIsLoadingStatus(true);
    setTransmissionSuccessMsg(null);
    setTransmissionErrorMsg(null);
    try {
      const [statusRes, previewRes, transRes] = await Promise.allSettled([
        api.checkWMSStatus(shipmentId),
        api.previewWMSPayload(shipmentId),
        api.getShipmentTransmissions(shipmentId)
      ]);

      if (statusRes.status === 'fulfilled') {
        setEligibility(statusRes.value);
      }
      if (previewRes.status === 'fulfilled') {
        setPayloadPreview(previewRes.value);
      } else {
        setPayloadPreview(null);
      }
      if (transRes.status === 'fulfilled') {
        setTransmissions(transRes.value);
      }
    } catch (err) {
      console.error('Lỗi tải thông tin WMS:', err);
    } finally {
      setIsLoadingStatus(false);
    }
  };

  const fetchMockReceipts = async () => {
    setIsLoadingReceipts(true);
    try {
      const data = await api.getMockWMSReceipts();
      setMockReceipts(data);
    } catch (err) {
      console.error('Lỗi tải danh sách phiếu nhập kho Mock WMS:', err);
    } finally {
      setIsLoadingReceipts(false);
    }
  };

  const currentShipment = useMemo(() => {
    return shipments.find(s => s.id === selectedShipmentId);
  }, [shipments, selectedShipmentId]);

  const handleApprove = async () => {
    if (!selectedShipmentId || !approverName.trim()) return;
    setIsApproving(true);
    setTransmissionSuccessMsg(null);
    setTransmissionErrorMsg(null);
    try {
      await api.approveShipmentForWMS(selectedShipmentId, approverName.trim(), approvalNotes);
      setTransmissionSuccessMsg('Ký phê duyệt lô hàng thành công! Đã mở khóa quyền xuất Excel và truyền WMS.');
      // Refresh shipment status and WMS eligibility
      await fetchShipmentWMSData(selectedShipmentId);
      await fetchShipments();
    } catch (err: any) {
      setTransmissionErrorMsg(err.message || 'Lỗi khi phê duyệt hồ sơ.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleTransmit = async () => {
    if (!selectedShipmentId) return;
    setIsTransmitting(true);
    setTransmissionSuccessMsg(null);
    setTransmissionErrorMsg(null);
    try {
      const result = await api.transmitToWMS(selectedShipmentId, approverName.trim(), {
        simulate_failure: simulateFailure,
        notes: approvalNotes
      });

      if (result.status === 'TRANSMITTED') {
        setTransmissionSuccessMsg('Truyền dữ liệu vào WMS thành công! Phiếu nhập kho đã được ghi nhận vào Sổ cái WMS.');
      } else {
        setTransmissionErrorMsg(`Truyền dữ liệu thất bại: ${result.blocking_reason || 'Không rõ nguyên nhân'}`);
      }

      await fetchShipmentWMSData(selectedShipmentId);
      await fetchShipments();
      if (activeSubTab === 'ledger') {
        await fetchMockReceipts();
      }
    } catch (err: any) {
      setTransmissionErrorMsg(err.message || 'Lỗi khi truyền dữ liệu vào WMS.');
      await fetchShipmentWMSData(selectedShipmentId);
    } finally {
      setIsTransmitting(false);
    }
  };

  const handleDownloadExcel = async () => {
    if (!selectedShipmentId || !currentShipment) return;
    setIsExportingExcel(true);
    try {
      const filename = `WMS_Inbound_${currentShipment.shipment_code || selectedShipmentId.slice(0, 8)}.xlsx`;
      await api.downloadWMSExcel(selectedShipmentId, filename);
    } catch (err: any) {
      alert(`Không thể tải Excel: ${err.message}`);
    } finally {
      setIsExportingExcel(false);
    }
  };

  const isEligible = eligibility?.eligible === true;
  const isApproved = currentShipment?.approval_status === 'APPROVED';

  if (isLoadingShipments && shipments.length === 0) {
    return <WMSGatewaySkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-5">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-blue-50 text-blue-700 rounded-xl border border-blue-100 shadow-sm">
              <Server className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-slate-900">Cổng Kiểm Soát & Phê Duyệt Truyền WMS</h1>
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800">Demo</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Chỉ hồ sơ đủ ba chứng từ, đối soát hợp lệ và đã duyệt mới được xuất Excel hoặc gửi WMS giả lập.
              </p>
            </div>
          </div>

          {/* Shipment selector */}
          <div className="flex items-center space-x-3">
            <label className="text-xs font-medium text-slate-600 whitespace-nowrap">Chọn Lô Hàng:</label>
            <select
              value={selectedShipmentId}
              onChange={(e) => {
                const newId = e.target.value;
                setSelectedShipmentId(newId);
                if (onSelectShipment) onSelectShipment(newId);
              }}
              className="bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium min-w-[240px]"
              disabled={isLoadingShipments}
            >
              {shipments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.shipment_code} ({s.status} - {s.approval_status})
                </option>
              ))}
            </select>

            <button
              onClick={() => {
                if (selectedShipmentId) fetchShipmentWMSData(selectedShipmentId);
                fetchShipments();
              }}
              className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              title="Làm mới trạng thái"
            >
              <RefreshCw className={`w-4 h-4 ${isLoadingStatus ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Selected Shipment Status Matrix */}
        {currentShipment && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-4 pt-1">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Mã Lô Hàng</span>
              <span className="text-xs font-bold text-slate-800 font-mono">{currentShipment.shipment_code}</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Số Tờ Khai HQ</span>
              <span className="text-xs font-bold text-slate-800 font-mono">
                {currentShipment.customs_declaration_no || 'Chưa cập nhật'}
              </span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Loại Kho</span>
              <span className="text-xs font-bold text-slate-800">Kho Ngoại Quan (BONDED)</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Trạng Thái Hồ Sơ</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold mt-0.5 ${
                currentShipment.status === 'VALIDATED' ? 'bg-emerald-100 text-emerald-800' :
                currentShipment.status === 'TRANSMITTED' ? 'bg-blue-100 text-blue-800' :
                currentShipment.status === 'DISCREPANT' ? 'bg-rose-100 text-rose-800' :
                'bg-amber-100 text-amber-800'
              }`}>
                {currentShipment.status}
              </span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Phê Duyệt Giám Sát</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold mt-0.5 ${
                currentShipment.approval_status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' :
                currentShipment.approval_status === 'REJECTED' ? 'bg-rose-100 text-rose-800' :
                'bg-amber-100 text-amber-800'
              }`}>
                {currentShipment.approval_status === 'APPROVED' ? 'ĐÃ PHÊ DUYỆT' : 'CHỜ DUYỆT'}
              </span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <span className="text-[11px] text-slate-500 block">Cổng WMS</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold mt-0.5 ${
                isEligible ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
              }`}>
                {isEligible ? (
                  <>
                    <Unlock className="w-3 h-3 mr-1" /> MỞ KHÓA
                  </>
                ) : (
                  <>
                    <Lock className="w-3 h-3 mr-1" /> KHÓA CỨNG
                  </>
                )}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Navigation tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        <button
          onClick={() => setActiveSubTab('transmission')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeSubTab === 'transmission'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Server className="w-4 h-4" />
          <span>Kiểm Soát Gatekeeper & Truyền Dữ Liệu</span>
        </button>

        <button
          onClick={() => setActiveSubTab('ledger')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
            activeSubTab === 'ledger'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Sổ Cái Phiếu Nhập Mock WMS ({mockReceipts.length})</span>
        </button>
      </div>

      {/* Main Tab Content */}
      {activeSubTab === 'transmission' ? (
        <div className="space-y-6">
          {/* Notifications */}
          {transmissionSuccessMsg && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm flex items-start gap-3 shadow-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Thao tác thành công!</p>
                <p className="text-xs text-emerald-700 mt-0.5">{transmissionSuccessMsg}</p>
              </div>
            </div>
          )}

          {transmissionErrorMsg && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm flex items-start gap-3 shadow-sm">
              <XCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Phát hiện lỗi / Chặn thao tác:</p>
                <p className="text-xs text-rose-700 mt-0.5">{transmissionErrorMsg}</p>
              </div>
            </div>
          )}

          {/* Gatekeeper Banner */}
          <div className={`p-5 rounded-xl border shadow-sm ${
            isEligible 
              ? 'bg-emerald-50/70 border-emerald-200' 
              : 'bg-rose-50/70 border-rose-200'
          }`}>
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className={`p-2.5 rounded-xl ${isEligible ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'}`}>
                  {isEligible ? <ShieldCheck className="w-6 h-6" /> : <Lock className="w-6 h-6" />}
                </div>
                <div>
                  <h3 className={`text-base font-bold ${isEligible ? 'text-emerald-950' : 'text-rose-950'}`}>
                    {isEligible 
                      ? 'Điều Kiện Gatekeeper: ĐẠT TIÊU CHUẨN TRUYỀN WMS' 
                      : 'Điều Kiện Gatekeeper: KHÓA CHUYỂN TIẾP WMS'}
                  </h3>
                  <p className={`text-xs mt-1 leading-relaxed ${isEligible ? 'text-emerald-800' : 'text-rose-800'}`}>
                    {eligibility?.reason || 'Đang thẩm định điều kiện truyền WMS...'}
                  </p>
                </div>
              </div>

              {!isEligible && (
                <button
                  onClick={() => onNavigateReconciliation && onNavigateReconciliation(selectedShipmentId)}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors whitespace-nowrap shadow-sm"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Chuyển Sang Đối Soát & Xử Lý Lỗi</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Action Panels: Approval & Export/Transmit */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Panel 1: Supervisor Approval Step */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-indigo-600" />
                  <h3 className="font-bold text-sm text-slate-800">1. Ký Phê Duyệt Của Cán Bộ Giám Sát</h3>
                </div>
                {isApproved && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 flex items-center gap-1">
                    <Check className="w-3 h-3" /> Đã Phê Duyệt
                  </span>
                )}
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Họ Tên Cán Bộ Giám Sát Kho / Hải Quan:
                  </label>
                  <input
                    type="text"
                    value={approverName}
                    onChange={(e) => setApproverName(e.target.value)}
                    placeholder="VD: Nguyễn Văn Quản Trị"
                    disabled={isApproved}
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50 disabled:bg-slate-100 disabled:text-slate-500"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Ghi Chú Ký Phê Duyệt:
                  </label>
                  <textarea
                    rows={2}
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Ghi chú xác nhận hồ sơ hợp lệ..."
                    disabled={isApproved}
                    className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50 disabled:bg-slate-100 disabled:text-slate-500 resize-none"
                  />
                </div>

                <div className="pt-2">
                  <button
                    onClick={handleApprove}
                    disabled={isApproved || isApproving || !approverName.trim()}
                    className={`w-full py-2.5 px-4 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all shadow-sm ${
                      isApproved 
                        ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                    }`}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{isApproving ? 'Đang Xử Lý Phê Duyệt...' : isApproved ? 'Hồ Sơ Đã Được Phê Duyệt' : 'Ký Phê Duyệt Hồ Sơ Lô Hàng'}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Panel 2: Excel Export & WMS Transmission */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Send className="w-5 h-5 text-blue-600" />
                  <h3 className="font-bold text-sm text-slate-800">2. Xuất Excel & Truyền Cổng WMS</h3>
                </div>
                <div className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    id="sim-failure"
                    checked={simulateFailure}
                    onChange={(e) => setSimulateFailure(e.target.checked)}
                    className="rounded text-rose-600 focus:ring-rose-500 w-3.5 h-3.5"
                  />
                  <label htmlFor="sim-failure" className="text-[11px] font-semibold text-rose-700 cursor-pointer">
                    Mô phỏng lỗi 503
                  </label>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs text-slate-600 leading-relaxed">
                  Xuất bảng dữ liệu demo 21 cột hoặc gửi WMS giả lập. Bố cục này khác phiếu BS-01 trong tài liệu tham chiếu.
                </p>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  {/* Excel export button */}
                  <button
                    onClick={handleDownloadExcel}
                    disabled={!isEligible || isExportingExcel}
                    className={`py-3 px-3 rounded-lg text-xs font-bold flex flex-col items-center justify-center gap-1.5 transition-all shadow-sm border ${
                      isEligible 
                        ? 'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-700' 
                        : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    }`}
                  >
                    <FileSpreadsheet className="w-5 h-5" />
                    <span>{isExportingExcel ? 'Đang Xuất...' : 'Xuất Excel WMS (21 Cột)'}</span>
                  </button>

                  {/* Transmit button */}
                  <button
                    onClick={handleTransmit}
                    disabled={!isEligible || isTransmitting}
                    className={`py-3 px-3 rounded-lg text-xs font-bold flex flex-col items-center justify-center gap-1.5 transition-all shadow-sm border ${
                      isEligible 
                        ? simulateFailure 
                          ? 'bg-rose-600 hover:bg-rose-700 text-white border-rose-700'
                          : 'bg-blue-600 hover:bg-blue-700 text-white border-blue-700' 
                        : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                    }`}
                  >
                    <Send className="w-5 h-5" />
                    <span>
                      {isTransmitting 
                        ? 'Đang Truyền WMS...' 
                        : simulateFailure 
                          ? 'Truyền (Thử Thất Bại 503)' 
                          : 'Truyền Dữ Liệu WMS'}
                    </span>
                  </button>
                </div>

                {!isEligible && (
                  <p className="text-[11px] text-rose-600 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    Nút thao tác bị khóa vì hồ sơ chưa vượt qua kiểm định Gatekeeper.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* 21-Column WMS Data Preview Table */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-sm text-slate-800">
                  Xem trước dữ liệu WMS giả lập
                </h3>
                <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">
                  {payloadPreview?.line_items?.length || 0} Dòng Hàng
                </span>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">
                Mẫu: Inbound_Bonded_Receipt (21 Columns)
              </span>
            </div>

            {payloadPreview && payloadPreview.line_items && payloadPreview.line_items.length > 0 ? (
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs border-collapse whitespace-nowrap">
                  <thead>
                    <tr className="bg-slate-800 text-white">
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-center">STT</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700">Mã SKU</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700">Mã Phụ Tùng</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 min-w-[200px]">Tên Hàng Hóa</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-center">Mã HS (8 Số)</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-center">ĐVT</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-right">SL Thực Nhập</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-right">Đơn Giá</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-right">Thành Tiền</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-center">Số PO</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-center">Số Tờ Khai HQ</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-right">Net Wgt (kg)</th>
                      <th className="py-2.5 px-3 font-semibold border-b border-slate-700 text-right">Gross Wgt (kg)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {payloadPreview.line_items.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2 px-3 text-center text-slate-500 font-mono">{item.line_number}</td>
                        <td className="py-2 px-3 font-mono font-bold text-blue-700">{item.sku}</td>
                        <td className="py-2 px-3 font-mono text-slate-600">{item.part_number || '-'}</td>
                        <td className="py-2 px-3 font-medium text-slate-800">{item.item_description}</td>
                        <td className="py-2 px-3 text-center font-mono text-slate-700">{item.hs_code || '-'}</td>
                        <td className="py-2 px-3 text-center font-semibold text-slate-600">{item.uom}</td>
                        <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                          {Number(item.quantity).toLocaleString('vi-VN')}
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-slate-700">
                          {item.unit_price != null ? `$${Number(item.unit_price).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '-'}
                        </td>
                        <td className="py-2 px-3 text-right font-mono font-bold text-emerald-700">
                          {item.unit_price != null ? `$${(Number(item.unit_price) * Number(item.quantity)).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '-'}
                        </td>
                        <td className="py-2 px-3 text-center font-mono text-slate-700">{item.po_number || '-'}</td>
                        <td className="py-2 px-3 text-center font-mono text-slate-700">{item.customs_declaration_no || '-'}</td>
                        <td className="py-2 px-3 text-right font-mono text-slate-600">
                          {item.net_weight_kg != null ? Number(item.net_weight_kg).toLocaleString('vi-VN') : '-'}
                        </td>
                        <td className="py-2 px-3 text-right font-mono text-slate-600">
                          {item.gross_weight_kg != null ? Number(item.gross_weight_kg).toLocaleString('vi-VN') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center bg-slate-50 rounded-lg text-slate-500 text-xs">
                Chưa có dữ liệu trích xuất SKU cho lô hàng này. Hãy kích hoạt trích xuất ở tab "Tiếp Nhận Chứng Từ".
              </div>
            )}
          </div>

          {/* Transmission History for this Shipment */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-sm text-slate-800">
                  Lịch Sử Các Lượt Truyền WMS Của Lô Hàng
                </h3>
              </div>
              <span className="text-xs text-slate-500 font-mono">
                {transmissions.length} Lượt Thao Tác
              </span>
            </div>

            {transmissions.length > 0 ? (
              <div className="space-y-2">
                {transmissions.map((t) => (
                  <div key={t.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2.5">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                        t.status === 'TRANSMITTED' ? 'bg-emerald-100 text-emerald-800' :
                        t.status === 'FAILED' ? 'bg-rose-100 text-rose-800' :
                        'bg-amber-100 text-amber-800'
                      }`}>
                        {t.status}
                      </span>
                      <span className="font-mono text-slate-600">Mã Lượt: {t.id.slice(0, 8)}</span>
                      <span className="text-slate-500">|</span>
                      <span className="text-slate-700">Người ký: <strong>{t.approved_by || 'Hệ thống'}</strong></span>
                      <span className="text-slate-500">|</span>
                      <span className="text-slate-500 font-mono">HTTP {t.wms_response_code || '-'}</span>
                    </div>

                    <div className="text-slate-500 text-[11px] font-mono">
                      {new Date(t.created_at).toLocaleString('vi-VN')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded-lg text-center">
                Chưa có lượt truyền WMS nào được thực hiện cho lô hàng này.
              </p>
            )}
          </div>
        </div>
      ) : (
        /* Sub-tab B: Mock WMS Receipts Ledger */
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-800 flex items-center gap-2">
                  <Database className="w-5 h-5 text-blue-600" />
                  Sổ Cái Phiếu Nhập Kho WMS Ngoại Quan (Mock WMS Ledger)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Các phiếu nhập kho đã được tạo thành công trong hệ thống WMS với cơ chế kiểm soát Idempotency Key chống trùng lặp.
                </p>
              </div>

              <button
                onClick={fetchMockReceipts}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors self-start md:self-auto"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingReceipts ? 'animate-spin' : ''}`} />
                <span>Làm Mới Sổ Cái</span>
              </button>
            </div>

            {mockReceipts.length > 0 ? (
              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-800 text-white">
                      <th className="py-2.5 px-3 font-semibold">Số Phiếu Nhập</th>
                      <th className="py-2.5 px-3 font-semibold">Mã Lô Hàng</th>
                      <th className="py-2.5 px-3 font-semibold">Số Tờ Khai HQ</th>
                      <th className="py-2.5 px-3 font-semibold">Đơn Vị Nhận (Consignee)</th>
                      <th className="py-2.5 px-3 font-semibold text-center">Số Dòng SKU</th>
                      <th className="py-2.5 px-3 font-semibold text-right">Tổng Trọng Lượng</th>
                      <th className="py-2.5 px-3 font-semibold text-center">Trạng Thái</th>
                      <th className="py-2.5 px-3 font-semibold text-center">Idempotency Key</th>
                      <th className="py-2.5 px-3 font-semibold text-center">Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {mockReceipts.map((rcpt) => (
                      <tr key={rcpt.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-bold text-blue-700">
                          {rcpt.receipt_number}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-800 font-semibold">
                          {rcpt.shipment_code}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-700">
                          {rcpt.customs_declaration_no}
                        </td>
                        <td className="py-2.5 px-3 text-slate-700 max-w-[180px] truncate" title={rcpt.consignee || ''}>
                          {rcpt.consignee || 'Kho Ngoại Quan'}
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono font-bold text-slate-800">
                          {rcpt.total_line_items}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-slate-700">
                          {rcpt.total_gross_weight_kg ? `${Number(rcpt.total_gross_weight_kg).toLocaleString('vi-VN')} kg` : '-'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800">
                            {rcpt.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center font-mono text-[10px] text-slate-500 max-w-[150px] truncate" title={rcpt.idempotency_key}>
                          {rcpt.idempotency_key}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            onClick={() => setSelectedReceipt(rcpt)}
                            className="px-2.5 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-xs font-semibold flex items-center gap-1 mx-auto transition-colors"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>Chi Tiết</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center bg-slate-50 rounded-lg text-slate-500 text-xs">
                Chưa có phiếu nhập kho nào trong WMS. Hãy phê duyệt và truyền lô hàng từ Tab 1 để tạo phiếu.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal Detail for Receipt */}
      {selectedReceipt && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-600 text-white rounded-lg">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Chi Tiết Phiếu Nhập Kho: {selectedReceipt.receipt_number}
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    Idempotency Key: {selectedReceipt.idempotency_key}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedReceipt(null)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4 flex-1">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Lô Hàng</span>
                  <span className="text-xs font-bold text-slate-800 font-mono">{selectedReceipt.shipment_code}</span>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Số Tờ Khai HQ</span>
                  <span className="text-xs font-bold text-slate-800 font-mono">{selectedReceipt.customs_declaration_no}</span>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Ngày Nhập Kho</span>
                  <span className="text-xs font-bold text-slate-800 font-mono">{selectedReceipt.receipt_date}</span>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Tổng Dòng SKU</span>
                  <span className="text-xs font-bold text-slate-800 font-mono">{selectedReceipt.total_line_items}</span>
                </div>
              </div>

              {/* Items Table */}
              <div className="border border-slate-200 rounded-lg overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-800 text-white">
                      <th className="py-2 px-3 text-center">STT</th>
                      <th className="py-2 px-3">Mã SKU</th>
                      <th className="py-2 px-3">Mô Tả Hàng Hóa</th>
                      <th className="py-2 px-3 text-center">Mã HS</th>
                      <th className="py-2 px-3 text-right">Số Lượng</th>
                      <th className="py-2 px-3 text-center">ĐVT</th>
                      <th className="py-2 px-3 text-center">Vị Trí Kệ (Bin)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {selectedReceipt.items && selectedReceipt.items.length > 0 ? (
                      selectedReceipt.items.map((it) => (
                        <tr key={it.id} className="hover:bg-slate-50">
                          <td className="py-2 px-3 text-center font-mono text-slate-500">{it.line_number}</td>
                          <td className="py-2 px-3 font-mono font-bold text-blue-700">{it.sku}</td>
                          <td className="py-2 px-3 text-slate-800">{it.item_description}</td>
                          <td className="py-2 px-3 text-center font-mono text-slate-600">{it.hs_code || '-'}</td>
                          <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                            {Number(it.quantity).toLocaleString('vi-VN')}
                          </td>
                          <td className="py-2 px-3 text-center text-slate-600">{it.uom}</td>
                          <td className="py-2 px-3 text-center font-mono font-semibold text-emerald-700 bg-emerald-50/50">
                            {it.bin_location || '-'}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={7} className="py-4 text-center text-slate-400">Không có dòng hàng SKU nào.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedReceipt(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-lg text-xs font-bold transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
