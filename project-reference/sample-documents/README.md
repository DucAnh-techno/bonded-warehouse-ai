# Bộ Chứng Từ Mẫu Hải Quan Kho Ngoại Quan (Sample Customs Documents)

Mỗi lô hàng nhập hoặc xuất kho ngoại quan (*Bonded Warehouse Consignment*) theo quy định của Tổng cục Hải quan Việt Nam đòi hỏi một bộ chứng từ đối ứng chặt chẽ:

| STT | Loại Chứng Từ | Thư Mục | Ý Nghĩa Kiểm Soát Hải Quan |
|:---:|:---|:---|:---|
| 1 | **Packing List (PL)** | `packing-list/` | Kiểm soát quy cách đóng gói, số kiện, phân bổ SKU theo kiện/pallet, tỷ trọng Gross/Net Weight, thể tích CBM. |
| 2 | **Commercial Invoice (CI)** | `commercial-invoice/` | Xác định trị giá hải quan, điều kiện Incoterms (CIF, FOB, CFR, DDP), đơn giá, thành tiền và dòng tiền thanh toán quốc tế. |
| 3 | **Bill of Lading (B/L / AWB)** | `bill-of-lading/` | Xác định phương thức vận chuyển quốc tế, số vận đơn, tên tàu/số chuyến, số container, số niêm chì, cảng đi/đến. |
| 4 | **Tờ khai hải quan điện tử** | `customs-declaration/` | Văn bản pháp lý cao nhất (Form HQ/2015/NK trên VNACCS) ghi nhận thông quan hàng hóa vào kho ngoại quan (Mã loại hình C11). |
| 5 | **Hợp đồng ngoại thương / Thuê kho** | `contract/` | Căn cứ pháp lý về quyền sở hữu hàng hóa, hợp đồng thuê kho ngoại quan ký giữa chủ hàng và doanh nghiệp kinh doanh kho. |

---

## Nguyên Tắc Đối Soát Giữa Các Chứng Từ
- **Tam giác số lượng**: $\sum Qty(PL) == \sum Qty(CI) == Qty(\text{Tờ khai})$.
- **Số container & số chì**: B/L $==$ Packing List $==$ Tờ khai hải quan.
- **Mã số HS**: Mã HS 8 chữ số trên Tờ khai phải khớp với mô tả hàng hóa trên Commercial Invoice và Hợp đồng.
