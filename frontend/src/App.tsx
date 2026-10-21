import { useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { WMSGatewayPage } from './pages/WMSGatewayPage';
import { Building2, LayoutDashboard, FileText, Layers, Send } from 'lucide-react';

type Section = 'dashboard' | 'documents' | 'reconciliation' | 'wms';
export default function App() {
  const [activeTab,setActiveTab]=useState<Section>('dashboard');
  const [selectedShipmentId,setSelectedShipmentId]=useState<string>();
  const go=(section:Section,id?:string)=>{if(id)setSelectedShipmentId(id);setActiveTab(section);};
  const menus=[{id:'dashboard',label:'Lô hàng',icon:LayoutDashboard},{id:'documents',label:'Chứng từ & trích xuất',icon:FileText},{id:'reconciliation',label:'Đối soát & xử lý lỗi',icon:Layers},{id:'wms',label:'Excel & WMS giả lập',icon:Send}] as const;
  return <div className="min-h-screen bg-slate-50 text-slate-800 md:flex">
    <aside className="bg-slate-900 text-white md:w-64 md:shrink-0 md:min-h-screen">
      <div className="p-5 border-b border-slate-700"><Building2 className="mb-3 text-emerald-400"/><h1 className="font-bold text-lg">Bonded Warehouse AI</h1><p className="mt-1 text-xs text-slate-400">Xử lý hồ sơ nhập kho</p></div>
      <nav aria-label="Chức năng chính" className="flex gap-1 p-3 overflow-x-auto md:flex-col">{menus.map(({id,label,icon:Icon})=><button key={id} onClick={()=>go(id)} aria-current={activeTab===id?'page':undefined} className={`flex items-center gap-3 rounded-lg px-3 py-3 text-left text-sm whitespace-nowrap ${activeTab===id?'bg-emerald-700':'hover:bg-slate-800'}`}><Icon size={18}/>{label}</button>)}</nav>
    </aside>
    <div className="min-w-0 flex-1">
      <main className="p-4 lg:p-6">
        {activeTab==='dashboard' && <DashboardPage onSelectShipment={setSelectedShipmentId} onNavigateDocuments={id=>go('documents',id)}/>}
        {activeTab==='documents' && <DocumentsPage initialShipmentId={selectedShipmentId} onNavigateReconciliation={id=>go('reconciliation',id)}/>}
        {activeTab==='reconciliation' && <ReconciliationPage initialShipmentId={selectedShipmentId} onNavigateDocuments={id=>go('documents',id)} onNavigateWMS={id=>go('wms',id)}/>}
        {activeTab==='wms' && <WMSGatewayPage initialShipmentId={selectedShipmentId} onSelectShipment={setSelectedShipmentId} onNavigateReconciliation={id=>go('reconciliation',id)}/>}
      </main>
    </div>
  </div>;
}
