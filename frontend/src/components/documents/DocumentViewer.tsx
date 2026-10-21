import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, AlertTriangle, MapPin } from 'lucide-react';
import { api } from '../../services/api';
import { DocumentItem, ExcelSheet, ParsedDocument, PdfBlock } from '../../types';

function colLetter(i: number): string {
  let s = '';
  let n = i;
  while (n >= 0) {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  }
  return s;
}

/** Excel address of rows[r][c] (sheet always starts at A1). */
const cellAddress = (r: number, c: number): string => `${colLetter(c)}${r + 1}`;

interface CellSel {
  r: number;
  c: number;
}

const SheetGrid: React.FC<{ sheet: ExcelSheet; selected: CellSel | null; onSelect: (s: CellSel) => void }> = ({
  sheet,
  selected,
  onSelect,
}) => {
  const selRef = useRef<HTMLTableCellElement>(null);
  useEffect(() => {
    selRef.current?.scrollIntoView({ block: 'center', inline: 'center' });
  }, [selected]);

  return (
    <div className="overflow-auto max-h-[70vh] border border-slate-200 rounded">
      <table className="text-xs border-collapse">
        <thead className="sticky top-0 bg-slate-100">
          <tr>
            <th className="border border-slate-200 px-2 py-1 w-10" />
            {Array.from({ length: sheet.col_count }, (_, i) => (
              <th key={i} className="border border-slate-200 px-2 py-1 text-slate-500 font-medium">{colLetter(i)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sheet.rows.map((row, r) => (
            <tr key={r}>
              <td className="border border-slate-200 px-2 py-1 bg-slate-50 text-slate-400 text-right">{r + 1}</td>
              {Array.from({ length: sheet.col_count }, (_, c) => {
                const isSel = selected?.r === r && selected?.c === c;
                return (
                  <td
                    key={c}
                    ref={isSel ? selRef : undefined}
                    onClick={() => onSelect({ r, c })}
                    className={`border px-2 py-1 whitespace-pre font-mono cursor-pointer ${
                      isSel ? 'bg-amber-200 border-amber-500 ring-2 ring-amber-500' : 'border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    {row[c] === null || row[c] === undefined ? '' : String(row[c])}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

interface Props {
  document: DocumentItem;
  onDocumentChanged?: (doc: DocumentItem) => void;
}

export const DocumentViewer: React.FC<Props> = ({ document: doc }) => {
  const [parsed, setParsed] = useState<ParsedDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sheetName, setSheetName] = useState<string>('');
  const [selBlock, setSelBlock] = useState<PdfBlock | null>(null);
  const [selCell, setSelCell] = useState<CellSel | null>(null);
  const isPdf = doc.original_filename.toLowerCase().endsWith('.pdf');

  useEffect(() => {
    let cancelled = false;
    setParsed(null);
    setError(null);
    setPage(1);
    setSelBlock(null);
    setSelCell(null);
    setLoading(true);
    // Parsed from the real file; never fabricates values.
    api.parseDocument(doc.id)
      .then((res) => {
        if (cancelled) return;
        setParsed(res);
        const names = res.parsed_content.sheet_names;
        setSheetName(names && names.length ? names[0] : '');
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [doc.id]);

  const content = parsed?.parsed_content;
  const pageCount = content?.page_count ?? doc.page_count ?? 1;
  const pdfPage = content?.pages?.find((p) => p.page_number === page);
  const sheet = content?.sheets && sheetName ? content.sheets[sheetName] : undefined;

  const goPage = (p: number) => {
    setPage(p);
    setSelBlock(null);
  };
  const pickSheet = (n: string) => {
    setSheetName(n);
    setSelCell(null);
  };

  const sourceLabel = isPdf
    ? selBlock
      ? `${doc.original_filename} · Trang ${page}`
      : null
    : selCell
      ? `${doc.original_filename} · Sheet "${sheetName}" · Ô ${cellAddress(selCell.r, selCell.c)}`
      : null;

  return (
    <div className="space-y-3">
      {sourceLabel && (
        <div className="flex items-center gap-2 text-sm rounded border p-2 bg-amber-50 border-amber-300 text-amber-900">
          <MapPin className="w-4 h-4 shrink-0" />
          <span>Nguồn dữ liệu: {sourceLabel}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* LEFT: original document */}
        <section className="bg-white border border-slate-200 rounded-lg p-3">

          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold text-slate-800">Tài liệu gốc</h3>
            <a className="text-xs text-indigo-600 hover:underline" href={api.getDocumentDownloadUrl(doc.id)}>Tải tệp gốc</a>
          </div>
          {isPdf ? (
            <>
              <div className="flex items-center gap-2 mb-2 text-sm">
                <button className="p-1 border rounded disabled:opacity-40" disabled={page <= 1} onClick={() => goPage(page - 1)}>
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span>Trang {page} / {pageCount}</span>
                <button className="p-1 border rounded disabled:opacity-40" disabled={page >= pageCount} onClick={() => goPage(page + 1)}>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
              <div className="overflow-auto max-h-[70vh] border border-slate-200 rounded bg-slate-100">
                <div className="relative inline-block">
                  <img
                    src={api.getPageImageUrl(doc.id, page)}
                    alt={`Trang ${page}`}
                    className="block max-w-none"
                    style={pdfPage ? { width: `${pdfPage.width * 1.5}px` } : undefined}
                  />
                  {pdfPage && (
                    <>
                      {pdfPage.blocks.map((b) => {
                        const isSel = selBlock?.block_no === b.block_no;
                        return (
                          <button
                            key={b.block_no}
                            title={b.text.slice(0, 80)}
                            onClick={() => setSelBlock(b)}
                            className={`absolute border ${isSel ? 'border-amber-500 bg-amber-300/40 ring-2 ring-amber-500' : 'border-indigo-300/60 hover:bg-indigo-200/30'}`}
                            style={{
                              left: `${(b.bbox[0] / pdfPage.width) * 100}%`,
                              top: `${(b.bbox[1] / pdfPage.height) * 100}%`,
                              width: `${((b.bbox[2] - b.bbox[0]) / pdfPage.width) * 100}%`,
                              height: `${((b.bbox[3] - b.bbox[1]) / pdfPage.height) * 100}%`,
                            }}
                          />
                        );
                      })}
                    </>
                  )}
                </div>
              </div>
            </>
          ) : (
            <>
              {content?.sheet_names && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {content.sheet_names.map((n) => (
                    <button
                      key={n}
                      onClick={() => pickSheet(n)}
                      className={`px-3 py-1 text-xs rounded border ${n === sheetName ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-slate-700 border-slate-300'}`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              )}
              {sheet ? (
                <SheetGrid sheet={sheet} selected={selCell} onSelect={setSelCell} />
              ) : (
                <p className="text-sm text-slate-500">Đang tải bảng tính…</p>
              )}
            </>
          )}
        </section>

        {/* RIGHT: parsed data */}
        <section className="bg-white border border-slate-200 rounded-lg p-3">
          <h3 className="text-sm font-bold text-slate-800 mb-2">Dữ liệu phân tích từ tệp</h3>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /> Đang phân tích…</div>
          )}
          {error && (
            <div className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-2">
              <AlertTriangle className="w-4 h-4 mt-0.5" /> {error}
            </div>
          )}
          {isPdf && pdfPage && (
            <div className="space-y-2 max-h-[70vh] overflow-auto">
              <p className="text-xs text-slate-500">Trang {pdfPage.page_number} · {pdfPage.blocks.length} khối dữ liệu</p>
              {pdfPage.blocks.length === 0 && <p className="text-sm text-amber-700">Trang này không có văn bản (có thể là bản scan).</p>}
              {pdfPage.blocks.map((b) => (
                <button
                  key={b.block_no}
                  onClick={() => setSelBlock(b)}
                  className={`block w-full text-left border rounded-lg px-3 py-2.5 transition-colors cursor-pointer ${selBlock?.block_no === b.block_no ? 'border-amber-500 bg-amber-50' : 'border-slate-200 hover:bg-slate-50'}`}
                >
                  <p className="text-sm text-slate-800 whitespace-pre-wrap">{b.text || '(trống)'}</p>
                </button>
              ))}
            </div>
          )}
          {!isPdf && sheet && (
            <div className="overflow-auto max-h-[70vh]">
              <p className="text-xs text-slate-500 mb-2">{sheet.row_count} dòng × {sheet.col_count} cột · bấm vào ô để định vị trong bảng gốc</p>
              <table className="text-xs border-collapse w-full">
                <thead>
                  <tr>
                    {Array.from({ length: sheet.col_count }, (_, c) => (
                      <th key={c} className="border border-slate-200 bg-slate-100 px-2 py-1 text-left">
                        {sheet.rows[0]?.[c] ?? colLetter(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sheet.rows.slice(1).map((row, i) => {
                    const r = i + 1;
                    return (
                      <tr key={r}>
                        {Array.from({ length: sheet.col_count }, (_, c) => {
                          const isSel = selCell?.r === r && selCell?.c === c;
                          return (
                            <td
                              key={c}
                              title={`${sheetName}!${cellAddress(r, c)}`}
                              onClick={() => setSelCell({ r, c })}
                              className={`border px-2 py-1 font-mono cursor-pointer ${isSel ? 'bg-amber-200 border-amber-500' : 'border-slate-200 hover:bg-slate-50'}`}
                            >
                              {row[c] ?? ''}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

