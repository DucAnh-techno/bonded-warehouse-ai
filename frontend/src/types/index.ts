export type ShipmentDirection = 'INBOUND' | 'OUTBOUND';
export type InboundSource = 'DOMESTIC' | 'FOREIGN';

export type ShipmentStatus = 
  | 'DRAFT' 
  | 'EXTRACTING' 
  | 'RECONCILING' 
  | 'DISCREPANT' 
  | 'VALIDATED' 
  | 'APPROVED' 
  | 'TRANSMITTED';

export type DocumentType = 
  | 'WAREHOUSE_CONTRACT'
  | 'CUSTOMS_DECLARATION'
  | 'COMMERCIAL_INVOICE'
  | 'PACKING_LIST'
  | 'BILL_OF_LADING'
  | 'ARRIVAL_NOTICE'
  | 'SALE_CONTRACT'
  | 'PURCHASE_ORDER'
  | 'CERT_OF_ORIGIN'
  | 'OTHER';

export interface Shipment {
  id: string;
  entry_date?: string;
  shipment_code: string;
  inbound_source?: InboundSource | null;
  requires_classification?: boolean;
  customs_declaration_no?: string;
  declaration_type?: string;
  warehouse_type: string;
  bonded_warehouse_name?: string;
  partner_name?: string;
  direction: ShipmentDirection;
  status: ShipmentStatus;
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  approved_by?: string;
  approved_at?: string;
  notes?: string;
  document_count?: number;
  discrepancy_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ShipmentStats {
  total_shipments: number;
  draft_count: number;
  reconciling_count: number;
  discrepant_count: number;
  validated_count: number;
  approved_count: number;
  transmitted_count: number;
  inbound_count: number;
  outbound_count: number;
}

export interface DocumentItem {
  id: string;
  shipment_id: string;
  document_type: DocumentType;
  original_filename: string;
  storage_path: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  page_count: number | null;
  uploaded_at: string;
  has_extraction: boolean;
  has_parsed_content: boolean;
  version: number;
}

export interface ExtractedLineItem {
  id: string;
  item_index: number;
  sku?: string;
  part_number?: string;
  description_vi: string;
  hs_code?: string;
  quantity: number | null;
  uom?: string;
  unit_price?: number;
  total_amount?: number;
  currency?: string;
  gross_weight_kg?: number;
  net_weight_kg?: number;
  po_reference?: string;
  page_number?: number;
  raw_line_text?: string;
  bounding_box_json?: string;
}

export interface ExtractedHeaderInfo {
  document_type_detected?: string;
  document_number?: string;
  issue_date?: string;
  shipper?: string;
  consignee?: string;
  warehouse_name?: string;
  vessel_voyage?: string;
  container_numbers?: string[];
  seal_numbers?: string[];
  total_gross_weight_kg?: number;
  total_net_weight_kg?: number;
  total_packages?: number;
  total_invoice_value?: number;
  currency?: string;
  incoterms?: string;
}

export interface DocumentExtraction {
  id: string;
  document_id: string;
  status: 'PENDING' | 'SUCCESS' | 'FAILED';
  model_name: string;
  confidence_score?: number;
  error_message?: string;
  extracted_header_json?: string;
  extracted_at: string;
  version: number;
  prompt_tokens?: number;
  candidate_tokens?: number;
  line_items: ExtractedLineItem[];
}

export interface Discrepancy {
  id: string;
  shipment_id: string;
  rule_code: string;
  severity: 'ERROR' | 'WARNING';
  category?: 'MISSING' | 'CONFLICT' | 'NOT_APPLICABLE' | 'NOT_VERIFIED' | string;
  field_name: string;
  description_vi: string;
  source_doc_a_name?: string;
  value_a?: string;
  source_doc_b_name?: string;
  value_b?: string;
  status: 'OPEN' | 'OVERRIDDEN' | 'ACCEPTED' | 'REJECTED';
  resolution_action?: string;
  resolution_reason?: string;
  resolved_by?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ValidationRuleSetting {
  rule_code: string;
  name_vi: string;
  description_vi: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  enabled: boolean;
  tolerance?: number | null;
  category: string;
  updated_at: string;
}

export interface ShipmentApprovalResponse {
  success: boolean;
  shipment_id: string;
  status: string;
  approval_status: string;
  is_blocked: boolean;
  blocking_reasons: string[];
  approved_by?: string;
  approved_at?: string;
  message_vi: string;
}


export interface ReconciledSkuComparison {
  po_reference?: string;
  sku: string;
  description_vi: string;
  hs_code_declaration?: string;
  hs_code_invoice?: string;
  qty_declaration?: number;
  qty_invoice?: number;
  qty_packing_list?: number;
  qty_po?: number;
  unit_price_invoice?: number;
  uom?: string;
  is_matched: boolean;
  discrepancies: string[];
}

export interface ReconciliationMatrix {
  shipment_id: string;
  entry_date?: string;
  shipment_code: string;
  total_skus: number;
  matched_skus: number;
  error_count: number;
  warning_count: number;
  validation_status: ShipmentStatus;
  sku_matrix: ReconciledSkuComparison[];
  discrepancies: Discrepancy[];
}

export interface WMSEligibilityResponse {
  eligible: boolean;
  reason: string;
}

export interface WMSTransmission {
  id: string;
  shipment_id: string;
  status: string;
  is_blocked: boolean;
  blocking_reason?: string;
  approved_by?: string;
  approved_at?: string;
  payload?: any;
  transmitted_at?: string;
}

export interface PdfBlock {
  block_no: number;
  source_ref: string;
  text: string;
  bbox: [number, number, number, number];
  block_type: 'text' | 'image';
}

export interface PdfPage {
  page_number: number;
  width: number;
  height: number;
  blocks: PdfBlock[];
  full_text: string;
}

export interface ExcelSheet {
  start_cell: string;
  row_count: number;
  col_count: number;
  rows: (string | number | boolean | null)[][];
}

export interface ParsedContent {
  format: 'pdf' | 'xlsx' | 'xls';
  page_count?: number;
  pages?: PdfPage[];
  sheet_names?: string[];
  sheets?: Record<string, ExcelSheet>;
}

export interface ParsedDocument {
  document_id: string;
  original_filename: string;
  format: string;
  parsed_content: ParsedContent;
}

export interface ReconciledDiscrepancyItem {
  rule_code: string;
  severity: 'ERROR' | 'WARNING';
  field_name: string;
  description_vi: string;
  source_doc_a?: string;
  value_a?: string;
  source_doc_b?: string;
  value_b?: string;
}

export interface PerDocumentExtractionResult {
  document_id?: string;
  document_type_detected: string;
  document_number?: string;
  issue_date?: string;
  shipper_exporter?: string;
  consignee_importer?: string;
  warehouse_name?: string;
  vessel_voyage?: string;
  container_numbers: string[];
  seal_numbers: string[];
  total_gross_weight_kg?: number;
  total_net_weight_kg?: number;
  total_packages?: number;
  total_invoice_value?: number;
  currency?: string;
  incoterms?: string;
  items: ExtractedLineItem[];
}

export interface BatchShipmentReconciliationResponse {
  shipment_code?: string;
  customs_declaration_no?: string;
  overall_validity: 'VALID' | 'INVALID' | 'WARNING';
  validity_reason: string;
  discrepancies: ReconciledDiscrepancyItem[];
  documents: PerDocumentExtractionResult[];
}

export interface FieldProvenance {
  value?: string | null;
  source_document_name?: string | null;
  source_document_type?: string | null;
  source_document_id?: string | null;
}

export interface CrossDocMatrixRow {
  field_key: string;
  label_vi: string;
  applicable_docs: string[];
  values_by_doc: Record<string, string>;
  status: 'MATCHED' | 'MISMATCHED' | 'WARNING' | 'SINGLE_SOURCE' | 'MISSING';
  note_vi?: string | null;
}

export interface ConsolidatedShipmentHeader {
  shipment_id: string;
  shipment_code: string;
  status: string;
  approval_status: string;
  inbound_source?: string | null;
  requires_classification?: boolean;
  entry_date?: string;
  eta?: FieldProvenance | null;
  supplier_name?: FieldProvenance | null;
  commodity_description?: FieldProvenance | null;
  package_unit?: FieldProvenance | null;
  measurement_cbm?: FieldProvenance | null;
  contract_no?: FieldProvenance | null;
  tenant_name?: FieldProvenance | null;
  lessor_name?: FieldProvenance | null;
  valid_from?: FieldProvenance | null;
  valid_until?: FieldProvenance | null;
  customs_declaration_no?: FieldProvenance | null;
  declaration_type?: FieldProvenance | null;
  declaration_date?: FieldProvenance | null;
  bill_of_lading_no?: FieldProvenance | null;
  commercial_invoice_no?: FieldProvenance | null;
  invoice_date?: FieldProvenance | null;
  packing_list_no?: FieldProvenance | null;
  po_numbers: string[];
  shipper?: FieldProvenance | null;
  consignee?: FieldProvenance | null;
  warehouse_name?: FieldProvenance | null;
  vessel_voyage?: FieldProvenance | null;
  port_of_discharge?: FieldProvenance | null;
  container_numbers: string[];
  seal_numbers: string[];
  total_packages?: FieldProvenance | null;
  total_gross_weight_kg?: FieldProvenance | null;
  total_net_weight_kg?: FieldProvenance | null;
  total_invoice_value?: FieldProvenance | null;
  currency?: FieldProvenance | null;
  incoterms?: FieldProvenance | null;
  document_values?: Record<string, Record<string, any>> | null;
  field_matrix?: CrossDocMatrixRow[];
  has_sale_contract?: boolean;
}

export interface WMSReceiptItem {
  id: string;
  line_number: number;
  sku: string;
  part_number?: string | null;
  item_description: string;
  hs_code?: string | null;
  quantity: number | null;
  uom: string;
  unit_price?: number | null;
  total_amount?: number | null;
  currency: string;
  po_number?: string | null;
  customs_declaration_no?: string | null;
  net_weight_kg?: number | null;
  gross_weight_kg?: number | null;
  bin_location?: string | null;
  notes?: string | null;
}

export interface WMSReceipt {
  id: string;
  receipt_number: string;
  idempotency_key: string;
  shipment_id?: string | null;
  entry_date?: string;
  shipment_code: string;
  customs_declaration_no: string;
  warehouse_type: string;
  warehouse_name?: string | null;
  status: string;
  receipt_date: string;
  shipper?: string | null;
  consignee?: string | null;
  carrier_vessel?: string | null;
  containers: string[];
  seals: string[];
  total_packages?: number | null;
  total_gross_weight_kg?: number | null;
  total_net_weight_kg?: number | null;
  total_line_items: number;
  total_value?: number | null;
  currency: string;
  created_at: string;
  items: WMSReceiptItem[];
}

export interface WMSMockReceiptResponse {
  receipt_id: string;
  status: string;
  is_duplicate: boolean;
  message: string;
  receipt_id_pk?: string;
  created_at?: string;
}

export interface WMSLineItemPayload {
  line_number: number;
  sku: string;
  part_number?: string | null;
  item_description: string;
  hs_code?: string | null;
  quantity: number | null;
  uom: string;
  po_number?: string | null;
  customs_declaration_no?: string | null;
  unit_price?: number | null;
  currency?: string | null;
  net_weight_kg?: number | null;
  gross_weight_kg?: number | null;
}

export interface WMSInboundReceiptPayload {
  receipt_id: string;
  entry_date?: string;
  shipment_code: string;
  customs_declaration_no: string;
  warehouse_type: string;
  receipt_date: string;
  shipper?: string | null;
  consignee?: string | null;
  carrier_vessel?: string | null;
  containers: string[];
  seals: string[];
  total_packages?: number | null;
  total_gross_weight_kg?: number | null;
  total_line_items: number;
  line_items: WMSLineItemPayload[];
}

export interface WMSTransmissionRecord {
  id: string;
  shipment_id: string;
  status: string;
  is_blocked: boolean;
  blocking_reason?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  payload_json?: string | null;
  payload?: any;
  wms_response_code?: number | null;
  wms_response_body?: string | null;
  transmitted_at?: string | null;
  created_at: string;
}



