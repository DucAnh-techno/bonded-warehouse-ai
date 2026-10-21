# Kết quả kiểm thử Bonded Warehouse AI

Ngày kiểm thử: 11/10/2026. Dự án: `C:\Users\ĐAlap\OneDrive\Documents\HKDN\bonded-warehouse-ai`.

## Phạm vi đã thực hiện

- Giữ luồng tạo lô → tải Invoice, PL, hợp đồng thuê kho → Gemini trích xuất → đối soát PO/SKU → sửa dữ liệu và lưu lịch sử → duyệt → Excel/WMS giả lập.
- Bổ sung ngày nhập kho, thông tin hợp đồng, kiểm tra bên thuê và thời hạn hợp đồng.
- Bỏ chatbot giải thích lỗi, chức năng benchmark và trang giới thiệu/kiến trúc/lộ trình trên giao diện.
- Thêm bộ chứng từ giả lập tải ngay trên giao diện, gồm mẫu đúng, PL sai số lượng và hợp đồng hết hạn.
- Chuẩn bị cấu hình triển khai demo công khai dùng tệp mẫu. Chưa triển khai Internet.

## Lỗi tái hiện được và cách sửa

| Trường hợp tái hiện | Vấn đề trước sửa | Kết quả sau sửa |
|---|---|---|
| Tải ba chứng từ đã chốt | Thiếu loại hợp đồng, vẫn yêu cầu bộ bốn chứng từ cũ | Bắt buộc Invoice, PL, hợp đồng trước duyệt |
| SKU giống nhau xuất hiện nhiều dòng và nhiều PO | Dòng sau ghi đè dòng trước | Cộng số lượng theo cặp PO/SKU; PO-001 tổng 5, PO-002 tổng 7 trong bộ mẫu |
| Hợp đồng hết hạn hoặc bên thuê khác chủ hàng | Chưa có quy tắc tương ứng | Báo lỗi, chặn duyệt và xuất |
| Duyệt lô chưa đủ dữ liệu hoặc gửi trạng thái APPROVED trực tiếp | Có khả năng vượt kiểm tra | Kiểm tra lại dữ liệu thực ở đầu vào duyệt/xuất/gửi; từ chối sửa trạng thái tùy ý |
| Sửa dữ liệu sau duyệt | Phê duyệt cũ có thể còn hiệu lực | Thu hồi phê duyệt, lưu lịch sử và kiểm tra lại |
| Đọc trang đối soát sau khi gửi WMS | Thay đổi trạng thái đã truyền và ghi thêm lịch sử | Đọc kết quả không hạ trạng thái TRANSMITTED |
| Xuất lô có nhiều Invoice | Chỉ lấy dòng hàng chứng từ đầu tiên | Lấy các Invoice hiện hành; giữ số 0 đầu mã SKU |
| Giá trị chuỗi bắt đầu bằng dấu bằng trong Excel | Có thể bị coi là công thức | Xuất dưới dạng văn bản |
| Tải Excel để Gemini trích xuất | Gửi nhị phân bảng tính không phù hợp | Đọc ô thật rồi gửi nội dung bảng cho Gemini |
| AI không tìm thấy số lượng | Có nguy cơ ép giá trị hoặc không chấp nhận trống | Lưu null, hiển thị thiếu và chặn duyệt |
| Gemini lỗi khi xử lý một tệp hoặc cả hồ sơ | Lỗi không được lưu đầy đủ | Lưu FAILED và thông báo; kết quả cũ không mở khóa xuất |
| Gemini quá tải | Cả SDK và ứng dụng thử lại, gây chờ rất lâu | Một lần thử lại do ứng dụng quản lý; SDK không tự nhân thêm lần gọi; timeout mỗi lời gọi 60 giây |
| AI tự kết luận hồ sơ hợp lệ | Kết luận AI có thể ảnh hưởng phê duyệt | Quy tắc tính toán xác định quyết định tính hợp lệ |

## Bằng chứng kiểm tra

- **92/92 kiểm thử API/nghiệp vụ đạt**, bao gồm kiểm tra upload, hợp đồng, sửa dữ liệu, lịch sử, khóa duyệt, Excel, WMS lỗi 503/thử lại/gửi trùng và giới hạn demo. Có cảnh báo thư viện về các API sẽ thay đổi ở phiên bản tương lai, không có kiểm thử thất bại.
- Bản đóng gói frontend đã hoàn thành thành công.
- Đã gọi Gemini thật với các tệp giả lập Invoice PDF, PL PDF, hợp đồng PDF và Invoice XLSX: cả bốn có kết quả thành công. PL/XLSX có lần gặp 503 rồi thử lại thành công.
- Với kết quả Gemini thật trong cơ sở dữ liệu kiểm thử riêng: đối soát hợp lệ, duyệt, Excel HTTP 200 và WMS giả lập HTTP 200. Tệp kết quả: `review-artifacts/live-smoke-export.xlsx` trong thư mục công việc Codex.
- Trên trình duyệt localhost: tạo lô `SHP-20261011-5788`, tải ba PDF, mở xem chứng từ gốc, gọi trích xuất cả hồ sơ. Gemini có lần trả 503/504; giao diện hiện thông báo và cho phép thử lại. Không coi lỗi nhà cung cấp là một lần trích xuất thành công.
- Lần thử lại sau sửa dừng sau hai lỗi 504 và lưu ba chứng từ FAILED. Trên giao diện WMS, Excel/gửi WMS bị khóa; bấm duyệt bị từ chối đúng. Bằng chứng: `review-artifacts/local-test-result.jpg` trong thư mục công việc Codex.
- Máy chủ trả HTTP 200 tại `/health` và trang giao diện đã đóng gói tại cổng 8000.
- Đã đối chiếu sáu chứng từ có trước cập nhật: hàng dữ liệu về đường dẫn/mã kiểm tra và nội dung file giữ nguyên. Có sao lưu mã nguồn và SQLite trước mỗi lần đồng bộ.

## Giới hạn cần biết

1. Excel hiện là bảng dữ liệu demo **21 cột**. Mẫu `BS-01 PhieuNhapKho_Gop.xls` có bố cục biểu mẫu **12 cột**, chưa được ánh xạ và kiểm chứng tương thích. WMS đang là API giả lập, chưa kết nối WMS thật.
2. Gemini có thể quá tải 503/504; chế độ xử lý cả hồ sơ chưa thể xem là ổn định chỉ dựa vào các lần gọi thành công từng tệp.
3. Xem file gốc và khối văn bản đã hoạt động. Tọa độ AI trả về có thể trống; chưa đảm bảo đánh dấu chính xác từng trường trên mọi bố cục.
4. Khi sửa dữ liệu, hiện chạy lại bộ quy tắc của lô. Chưa tối ưu chỉ chạy tập quy tắc liên quan như yêu cầu ban đầu.
5. Dockerfile/cấu hình đã chuẩn bị nhưng chưa dựng container hay kiểm thử restart với volume trên nhà cung cấp thật. Trước công khai cần hoàn tất kiểm tra triển khai trong `docs/DEPLOYMENT_DEMO.md`.
6. Demo công khai dùng dữ liệu chung, một instance và một worker. Chế độ `DEMO_ONLY=true` chỉ nhận bộ tệp mẫu đóng gói, giới hạn yêu cầu AI; cần quota riêng ở Gemini trước khi công khai.

Các giới hạn trên không được ghi nhận là chức năng đã đạt đầy đủ. Bản hiện tại phù hợp tiếp tục thử nghiệm local và chuẩn bị demo, chưa được chứng nhận dùng cho nghiệp vụ kho thật.
