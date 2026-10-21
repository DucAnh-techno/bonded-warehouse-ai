import React, { useRef, useState } from 'react';
import { 
  X, 
  Upload, 
  FileText, 
  FileSpreadsheet, 
  Loader2, 
  AlertCircle, 
  Trash2, 
  FolderPlus, 
  Plus,
  Ship,
  Truck
} from 'lucide-react';
import { api } from '../../services/api';
import { DocumentType, InboundSource, Shipment } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (newShipment: Shipment) => void;
}

interface DocSlot {
  id: string;
  type: DocumentType;
  title: string;
  subtitle: string;
  required: boolean;
  files: File[];
  isCustom?: boolean;
}

const DOMESTIC_SLOTS: Omit<DocSlot, 'files'>[] = [
  { id: 'PACKING_LIST', type: 'PACKING_LIST', title: 'Phiếu đóng gói (PL)', subtitle: 'Chủ hàng, số PO, tên hàng, số kiện, trọng lượng, số khối', required: true },
  { id: 'CUSTOMS_DECLARATION', type: 'CUSTOMS_DECLARATION', title: 'Tờ khai hải quan', subtitle: 'Chủ hàng/XK, người nhận (U&I), tên hàng, số kiện, trọng lượng', required: true },
  { id: 'COMMERCIAL_INVOICE', type: 'COMMERCIAL_INVOICE', title: 'Hóa đơn thương mại (INV)', subtitle: 'Chủ hàng, người nhận (U&I), số Invoice, số PO, tên hàng, đơn giá', required: true },
  { id: 'SALE_CONTRACT', type: 'SALE_CONTRACT', title: 'Hợp đồng mua bán (SC - Tùy chọn)', subtitle: 'Người bán (XK trên TK), Người mua (Chủ hàng), Người nhận (U&I)', required: false },
  { id: 'WAREHOUSE_CONTRACT', type: 'WAREHOUSE_CONTRACT', title: 'Hợp đồng thuê kho (Tùy chọn nội địa)', subtitle: 'Số hợp đồng, bên thuê kho, bên cho thuê (U&I), thời hạn', required: false },
];

const FOREIGN_SLOTS: Omit<DocSlot, 'files'>[] = [
  { id: 'BILL_OF_LADING', type: 'BILL_OF_LADING', title: 'Vận đơn (BL)', subtitle: '', required: true },
  { id: 'ARRIVAL_NOTICE', type: 'ARRIVAL_NOTICE', title: 'Giấy báo hàng đến (AN)', subtitle: '', required: true },
  { id: 'COMMERCIAL_INVOICE', type: 'COMMERCIAL_INVOICE', title: 'Hóa đơn thương mại (INV)', subtitle: '', required: true },
  { id: 'PACKING_LIST', type: 'PACKING_LIST', title: 'Phiếu đóng gói (PL)', subtitle: '', required: true },
  { id: 'CUSTOMS_DECLARATION', type: 'CUSTOMS_DECLARATION', title: 'Tờ khai hải quan', subtitle: '', required: true },
  { id: 'WAREHOUSE_CONTRACT', type: 'WAREHOUSE_CONTRACT', title: 'Hợp đồng thuê kho', subtitle: '', required: true },
  { id: 'SALE_CONTRACT', type: 'SALE_CONTRACT', title: 'Hợp đồng ngoại thương (SC - Tùy chọn)', subtitle: '', required: false },
];

function buildSlots(source: InboundSource, existingSlots: DocSlot[] = []): DocSlot[] {
  const template = source === 'DOMESTIC' ? DOMESTIC_SLOTS : FOREIGN_SLOTS;
  const existingMap = new Map<string, File[]>();
  for (const s of existingSlots) {
    if (s.files.length > 0) {
      existingMap.set(s.type, [...(existingMap.get(s.type) || []), ...s.files]);
    }
  }

  const standardSlots: DocSlot[] = template.map(t => ({
    ...t,
    files: existingMap.get(t.type) || [],
  }));

  const customSlots = existingSlots.filter(s => s.isCustom);
  return [...standardSlots, ...customSlots];
}

export const CreateShipmentModal: React.FC<Props> = ({ isOpen, onClose, onCreated }) => {
  const [inboundSource, setInboundSource] = useState<InboundSource>('FOREIGN');
  const [entryDate, setEntryDate] = useState(new Date().toLocaleDateString('en-CA'));
  const [slots, setSlots] = useState<DocSlot[]>(() => buildSlots('FOREIGN'));
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

  if (!isOpen) return null;

  const handleSourceChange = (newSource: InboundSource) => {
    if (newSource === inboundSource) return;
    setInboundSource(newSource);
    setSlots(prev => buildSlots(newSource, prev));
  };

  const handleAddCustomSlot = () => {
    const newId = `custom-${Date.now()}`;
    setSlots(prev => [
      ...prev,
      {
        id: newId,
        type: 'OTHER',
        title: '',
        subtitle: 'Chứng từ bổ sung (C/O, Kiểm dịch, Phiếu cân...)',
        required: false,
        files: [],
        isCustom: true,
      }
    ]);
  };

  const handleUpdateSlotTitle = (id: string, newTitle: string) => {
    setSlots(prev => prev.map(s => s.id === id ? { ...s, title: newTitle } : s));
  };

  const handleDeleteSlot = (id: string) => {
    setSlots(prev => prev.filter(s => s.id !== id));
  };

  const handleFilesSelect = (id: string, selectedFiles: FileList | null) => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    const validFiles: File[] = [];
    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (!['.pdf', '.xlsx', '.xls', '.png', '.jpg', '.jpeg'].includes(ext)) {
        setError(`Tệp "${file.name}" không hợp lệ. Chỉ chấp nhận định dạng PDF, Excel (.xlsx, .xls) hoặc ảnh.`);
        return;
      }
      if (file.size > 25 * 1024 * 1024) {
        setError(`Tệp "${file.name}" vượt quá dung lượng tối đa 25MB.`);
        return;
      }
      validFiles.push(file);
    }

    setError(null);
    setSlots(prev => prev.map(s => {
      if (s.id === id) {
        return { ...s, files: [...s.files, ...validFiles] };
      }
      return s;
    }));
  };

  const handleRemoveSingleFile = (slotId: string, fileIndex: number) => {
    setSlots(prev => prev.map(s => {
      if (s.id === slotId) {
        const nextFiles = [...s.files];
        nextFiles.splice(fileIndex, 1);
        return { ...s, files: nextFiles };
      }
      return s;
    }));
  };

  const handleDrop = (e: React.DragEvent, id: string) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelect(id, e.dataTransfer.files);
    }
  };

  // Required slots that currently have no files
  const missingRequiredSlots = slots.filter(s => s.required && s.files.length === 0);
  const totalUploadedFilesCount = slots.reduce((acc, s) => acc + s.files.length, 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!entryDate) {
      setError('Vui lòng chọn ngày tiếp nhận lô hàng (Ngày dự kiến/thực tế vào kho).');
      return;
    }

    setLoading(true);
    setUploadProgress('Đang tạo hồ sơ lô hàng...');

    try {
      // 1. Tạo Shipment với nguồn hàng bắt buộc
      const newShipment = await api.createShipment({
        entry_date: entryDate,
        inbound_source: inboundSource,
        direction: 'INBOUND',
        warehouse_type: 'BONDED',
      });

      // 2. Upload các tệp đã chọn
      let currentFileIndex = 0;
      for (const slot of slots) {
        for (const file of slot.files) {
          currentFileIndex++;
          const displayTitle = slot.title || (slot.isCustom ? 'Chứng từ khác' : 'Chứng từ');
          setUploadProgress(`Đang tải lên (${currentFileIndex}/${totalUploadedFilesCount}): ${displayTitle} - ${file.name}...`);

          let fileToUpload = file;
          if (slot.isCustom && slot.title && slot.title.trim()) {
            const safeName = `[${slot.title.trim()}] ${file.name}`;
            fileToUpload = new File([file], safeName, { type: file.type });
          }
          await api.uploadDocument(newShipment.id, slot.type, fileToUpload);
        }
      }

      setUploadProgress('Tiếp nhận hồ sơ thành công!');
      onCreated(newShipment);
      onClose();
      // Reset modal
      setSlots(buildSlots(inboundSource));
    } catch (err: any) {
      setError(err.message || 'Lỗi khi khởi tạo lô hàng và tải chứng từ.');
    } finally {
      setLoading(false);
      setUploadProgress('');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl overflow-hidden my-6 animate-in fade-in duration-200 flex flex-col max-h-[94vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-emerald-600 rounded-lg text-white">
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base">Tiếp Nhận Lô Hàng Mới & Bộ Chứng Từ</h3>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-slate-400 hover:text-white rounded-lg p-1 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto flex-1 space-y-5">
          {error && (
            <div className="flex items-start space-x-2 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-sm">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {loading && uploadProgress && (
            <div className="flex items-center space-x-3 p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm animate-pulse">
              <Loader2 className="w-4 h-4 animate-spin shrink-0 text-emerald-600" />
              <span className="font-medium">{uploadProgress}</span>
            </div>
          )}

          {/* Source Selection & Entry Date */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-slate-50 border border-slate-200 rounded-xl">
            <div className="md:col-span-2 space-y-2">
              <label className="block text-xs font-bold text-slate-800 uppercase tracking-wider">
                Nguồn Hàng Nhập Kho 
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => handleSourceChange('DOMESTIC')}
                  className={`p-3 rounded-lg border text-left transition-all flex items-start space-x-3 ${
                    inboundSource === 'DOMESTIC'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-950 ring-2 ring-emerald-500/30'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  <Truck className={`w-5 h-5 mt-0.5 shrink-0 ${inboundSource === 'DOMESTIC' ? 'text-emerald-600' : 'text-slate-400'}`} />
                  <div>
                    <div className="text-xs font-bold">1. Nhập nội địa</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSourceChange('FOREIGN')}
                  className={`p-3 rounded-lg border text-left transition-all flex items-start space-x-3 ${
                    inboundSource === 'FOREIGN'
                      ? 'border-blue-600 bg-blue-50 text-blue-950 ring-2 ring-blue-500/30'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  <Ship className={`w-5 h-5 mt-0.5 shrink-0 ${inboundSource === 'FOREIGN' ? 'text-blue-600' : 'text-slate-400'}`} />
                  <div>
                    <div className="text-xs font-bold">2. Nhập nước ngoài</div>
                  </div>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-800 uppercase tracking-wider">
                Ngày Nhập Kho Dự Kiến / Thực Tế <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                value={entryDate}
                onChange={e => setEntryDate(e.target.value)}
                className="w-full text-xs font-medium text-slate-800 border border-slate-300 rounded-lg p-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>
          </div>

          {/* Document Upload Slots Header */}
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500 pt-1">
            <span>
              Danh mục chứng từ 
            </span>
            <button
              type="button"
              onClick={handleAddCustomSlot}
              className="inline-flex items-center space-x-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Thêm loại chứng từ khác</span>
            </button>
          </div>

          {/* Slots Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {slots.map((slot) => {
              const hasFiles = slot.files.length > 0;

              return (
                <div
                  key={slot.id}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => handleDrop(e, slot.id)}
                  className={`border-2 rounded-xl p-3.5 transition-all flex flex-col justify-between ${
                    hasFiles
                      ? 'border-emerald-500 bg-emerald-50/30 shadow-xs'
                      : slot.required
                      ? 'border-dashed border-amber-300 bg-amber-50/20 hover:border-amber-400'
                      : 'border-dashed border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {slot.isCustom ? (
                          <div className="space-y-1">
                            <input
                              type="text"
                              value={slot.title}
                              onChange={(e) => handleUpdateSlotTitle(slot.id, e.target.value)}
                              placeholder="Nhập tên loại chứng từ..."
                              className="text-xs font-bold text-slate-900 border border-slate-300 rounded px-2 py-1 focus:border-emerald-500 focus:outline-none w-full bg-white"
                            />
                            <p className="text-[11px] text-slate-500 leading-tight">
                              {slot.subtitle}
                            </p>
                          </div>
                        ) : (
                          <div>
                            <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                              <span className="text-xs font-bold text-slate-900">
                                {slot.title}
                              </span>
                              {slot.required && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${
                                  hasFiles
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}>
                                  {hasFiles ? 'Đã có' : 'Bắt buộc'}
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-500 mt-0.5 leading-tight">
                              {slot.subtitle}
                            </p>
                          </div>
                        )}
                      </div>

                      {slot.isCustom && (
                        <button
                          type="button"
                          onClick={() => handleDeleteSlot(slot.id)}
                          className="text-slate-400 hover:text-rose-600 p-1 transition-colors"
                          title="Xóa ô chứng từ tùy chỉnh này"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>

                    {/* File List for Slot */}
                    {hasFiles && (
                      <div className="mt-2.5 space-y-1.5">
                        {slot.files.map((file, idx) => {
                          const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
                          return (
                            <div
                              key={`${file.name}-${idx}`}
                              className="flex items-center justify-between bg-white border border-emerald-200 rounded-lg px-2.5 py-1.5 text-xs text-emerald-900 shadow-2xs"
                            >
                              <div className="flex items-center space-x-1.5 truncate">
                                {isExcel ? (
                                  <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                                ) : (
                                  <FileText className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                                )}
                                <span className="truncate font-medium">{file.name}</span>
                              </div>
                              <div className="flex items-center space-x-2 shrink-0 ml-2">
                                <span className="text-[10px] text-slate-400 font-mono">
                                  {(file.size / 1024).toFixed(0)} KB
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveSingleFile(slot.id, idx)}
                                  className="text-slate-400 hover:text-rose-600 transition-colors"
                                  title="Xóa tệp này"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Add / Choose File Input */}
                  <div className="mt-3">
                    <input
                      type="file"
                      multiple
                      ref={(el) => (fileInputRefs.current[slot.id] = el)}
                      accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg"
                      onChange={(e) => handleFilesSelect(slot.id, e.target.files)}
                      className="hidden"
                    />

                    <button
                      type="button"
                      onClick={() => fileInputRefs.current[slot.id]?.click()}
                      className={`w-full py-1.5 px-3 border text-xs font-medium rounded-lg flex items-center justify-center space-x-1.5 transition-colors ${
                        hasFiles
                          ? 'border-slate-300 hover:border-emerald-500 bg-white hover:bg-emerald-50 text-slate-700 hover:text-emerald-700'
                          : slot.required
                          ? 'border-amber-300 hover:border-amber-400 bg-white hover:bg-amber-50 text-amber-800'
                          : 'border-slate-300 hover:border-slate-400 bg-white hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <Upload className="w-3 h-3 text-slate-400" />
                      <span>{hasFiles ? '+ Thêm tệp cho loại này' : 'Chọn hoặc kéo thả tệp'}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Modal Footer */}
          <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
            <div className="text-xs text-slate-500">
              Đã chọn: <strong className="text-slate-800">{totalUploadedFilesCount}</strong> tệp
              {missingRequiredSlots.length > 0 && (
                <span className="ml-2 text-amber-600 font-medium">
                  (Còn thiếu {missingRequiredSlots.length} chứng từ bắt buộc)
                </span>
              )}
            </div>
            <div className="flex space-x-2.5">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-medium rounded-lg transition-colors cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                disabled={loading}
                className={`inline-flex items-center space-x-2 px-5 py-2 text-white text-xs font-medium rounded-lg shadow-xs transition-colors cursor-pointer ${
                  missingRequiredSlots.length > 0
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Đang xử lý tiếp nhận...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-3.5 h-3.5" />
                    <span>
                      {missingRequiredSlots.length > 0
                        ? 'Lưu Hồ Sơ Nháp (Bổ sung sau)'
                        : 'Tạo Lô Hàng & Tiếp Nhận Bộ Chứng Từ'}
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
