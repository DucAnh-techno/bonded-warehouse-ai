import { 
  Shipment, 
  ShipmentStats,
  DocumentItem, 
  DocumentExtraction, 
  ExtractedLineItem,
  ParsedDocument,
  Discrepancy, 
  ReconciliationMatrix, 
  WMSEligibilityResponse, 
  BatchShipmentReconciliationResponse,
  ValidationRuleSetting,
  ShipmentApprovalResponse,
  ConsolidatedShipmentHeader,
  WMSReceipt,
  WMSInboundReceiptPayload,
  WMSTransmissionRecord
} from '../types';


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `Lỗi mạng hoặc máy chủ (${response.status})`;
    try {
      const errorJson = await response.json();
      errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail
        : Array.isArray(errorJson.detail) ? errorJson.detail.map((e: {loc?:string[];msg?:string}) => `${e.loc?.slice(1).join('.')}: ${e.msg}`).join('; ')
        : errorDetail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // --- Shipments ---
  getShipments: (params?: { search?: string; status?: string; direction?: string }): Promise<Shipment[]> => {
    const query = new URLSearchParams();
    if (params?.search) query.append('search', params.search);
    if (params?.status && params.status !== 'ALL') query.append('status', params.status);
    if (params?.direction && params.direction !== 'ALL') query.append('direction', params.direction);
    const qs = query.toString();
    return fetchJson<Shipment[]>(`/shipments/${qs ? `?${qs}` : ''}`);
  },
  updateShipment: (id: string, values: Record<string, unknown>): Promise<Shipment> => fetchJson<Shipment>(`/shipments/${id}`, {method:'PATCH', body:JSON.stringify(values)}),
  updateDocumentHeader: (id:string, values:Record<string, unknown>, reason:string): Promise<DocumentExtraction> => fetchJson<DocumentExtraction>(`/extractions/document/${id}/header`, {method:'PATCH',body:JSON.stringify({values,reason})}),
  getShipmentStats: (): Promise<ShipmentStats> => fetchJson<ShipmentStats>('/shipments/statistics/summary'),
  getShipment: (id: string): Promise<Shipment> => fetchJson<Shipment>(`/shipments/${id}`),
  createShipment: (data: Partial<Shipment>): Promise<Shipment> => 
    fetchJson<Shipment>('/shipments/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteShipment: (id: string): Promise<{ success: boolean; message: string }> =>
    fetchJson<{ success: boolean; message: string }>(`/shipments/${id}`, {
      method: 'DELETE',
    }),
  getConsolidatedShipmentHeader: (shipmentId: string): Promise<ConsolidatedShipmentHeader> =>
    fetchJson<ConsolidatedShipmentHeader>(`/shipments/${shipmentId}/consolidated-header`),

  // --- Documents ---

  getShipmentDocuments: (shipmentId: string): Promise<DocumentItem[]> =>
    fetchJson<DocumentItem[]>(`/documents/shipment/${shipmentId}`),

  uploadDocument: async (shipmentId: string, documentType: string, file: File): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('shipment_id', shipmentId);
    formData.append('document_type', documentType);
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Táº£i tá»‡p tháº¥t báº¡i' }));
      throw new Error(err.detail || 'Lá»—i táº£i lĂªn chá»©ng tá»«');
    }

    return response.json();
  },

  getDocumentDownloadUrl: (documentId: string): string =>
    `${API_BASE_URL}/documents/${documentId}/download`,

  getPageImageUrl: (documentId: string, page: number, scale = 1.5): string =>
    `${API_BASE_URL}/documents/${documentId}/pages/${page}/image?scale=${scale}`,

  getDocumentPreviewUrl: (documentId: string): string =>
    `${API_BASE_URL}/documents/${documentId}/preview`,

  overrideDocumentType: (documentId: string, documentType: string): Promise<DocumentItem> =>
    fetchJson<DocumentItem>(`/documents/${documentId}/type`, {
      method: 'PATCH',
      body: JSON.stringify({ document_type: documentType }),
    }),

  parseDocument: (documentId: string): Promise<ParsedDocument> =>
    fetchJson<ParsedDocument>(`/documents/${documentId}/parse`, { method: 'POST' }),

  getParsedDocument: (documentId: string): Promise<ParsedDocument> =>
    fetchJson<ParsedDocument>(`/documents/${documentId}/parsed`),

  // --- Extractions ---
  extractDocument: (documentId: string): Promise<DocumentExtraction> =>
    fetchJson<DocumentExtraction>(`/extractions/extract/${documentId}`, { method: 'POST' }),

  batchReconcileShipment: (shipmentId: string): Promise<BatchShipmentReconciliationResponse> =>
    fetchJson<BatchShipmentReconciliationResponse>(`/extractions/shipment/${shipmentId}/batch-reconcile`, { method: 'POST' }),

  getDocumentExtraction: (documentId: string): Promise<DocumentExtraction> =>

    fetchJson<DocumentExtraction>(`/extractions/document/${documentId}`),

  updateExtractedItem: (itemId: string, data: Partial<ExtractedLineItem> & { reason?: string }, userId = 'operator'): Promise<ExtractedLineItem> =>
    fetchJson<ExtractedLineItem>(`/extractions/items/${itemId}?user_id=${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  getItemAuditHistory: (itemId: string): Promise<any[]> =>
    fetchJson<any[]>(`/extractions/items/${itemId}/audit-history`),

  // --- Validations & Discrepancies ---
  getDiscrepancies: (shipmentId: string): Promise<Discrepancy[]> =>
    fetchJson<Discrepancy[]>(`/validations/discrepancies/${shipmentId}`),

  resolveDiscrepancy: (discrepancyId: string, data: { action: string; reason: string; override_value?: string; resolved_by?: string }): Promise<Discrepancy> =>
    fetchJson<Discrepancy>(`/validations/discrepancies/${discrepancyId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getReconciliationMatrix: (shipmentId: string): Promise<ReconciliationMatrix> =>
    fetchJson<ReconciliationMatrix>(`/validations/reconcile/${shipmentId}`),

  reconcileShipment: (shipmentId: string): Promise<ReconciliationMatrix> =>
    fetchJson<ReconciliationMatrix>(`/validations/reconcile/${shipmentId}`, { method: 'POST' }),

  getRuleConfigurations: (): Promise<ValidationRuleSetting[]> =>
    fetchJson<ValidationRuleSetting[]>('/validations/rules/config'),

  updateRuleConfiguration: (ruleCode: string, data: { enabled?: boolean; tolerance?: number | null; severity?: string }): Promise<ValidationRuleSetting> =>
    fetchJson<ValidationRuleSetting>(`/validations/rules/config/${ruleCode}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  approveShipmentValidation: (shipmentId: string, approvedBy: string, notes?: string): Promise<ShipmentApprovalResponse> =>
    fetchJson<ShipmentApprovalResponse>(`/validations/shipment/${shipmentId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy, notes }),
    }),

  // --- WMS Gateway ---
  checkWMSStatus: (shipmentId: string): Promise<WMSEligibilityResponse> =>
    fetchJson<WMSEligibilityResponse>(`/wms/status/${shipmentId}`),

  approveShipmentForWMS: (shipmentId: string, approvedBy: string, notes?: string): Promise<any> =>
    fetchJson(`/wms/approve/${shipmentId}`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy, approval_notes: notes }),
    }),

  transmitToWMS: (
    shipmentId: string, 
    approvedBy: string, 
    options?: { simulate_failure?: boolean; notes?: string }
  ): Promise<WMSTransmissionRecord> =>
    fetchJson<WMSTransmissionRecord>(`/wms/transmit/${shipmentId}`, {
      method: 'POST',
      body: JSON.stringify({ 
        approved_by: approvedBy,
        approval_notes: options?.notes,
        simulate_failure: options?.simulate_failure || false,
      }),
    }),

  previewWMSPayload: (shipmentId: string): Promise<WMSInboundReceiptPayload> =>
    fetchJson<WMSInboundReceiptPayload>(`/wms/payload-preview/${shipmentId}`),

  exportWMSExcelUrl: (shipmentId: string): string =>
    `${API_BASE_URL}/wms/export-excel/${shipmentId}`,

  downloadWMSExcel: async (shipmentId: string, fallbackFilename = 'WMS_Inbound.xlsx'): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/wms/export-excel/${shipmentId}`);
    if (!res.ok) {
      let err = `Lỗi tải file Excel (${res.status})`;
      try {
        const j = await res.json();
        err = j.detail || err;
      } catch {}
      throw new Error(err);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fallbackFilename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  getMockWMSReceipts: (skip = 0, limit = 50): Promise<WMSReceipt[]> =>
    fetchJson<WMSReceipt[]>(`/wms/mock/inbound-receipts?skip=${skip}&limit=${limit}`),

  getMockWMSReceipt: (receiptId: string): Promise<WMSReceipt> =>
    fetchJson<WMSReceipt>(`/wms/mock/inbound-receipts/${receiptId}`),

  getShipmentTransmissions: (shipmentId: string): Promise<WMSTransmissionRecord[]> =>
    fetchJson<WMSTransmissionRecord[]>(`/wms/transmissions/${shipmentId}`),
};



