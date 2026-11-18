# Báo cáo Day 09 — Hoàng Thuận Thiên, 2A202603270

## 1. Kết luận trước
Pipeline đưa ra kết luận **HOLD** (mã thoát: 10). Lô dữ liệu đầu vào gồm 224 ảnh thô tại `data/raw`, qua Bước 1 (Intake) máy loại bỏ 21 ảnh không đạt chuẩn (8 ảnh trùng byte `DUP_IMAGE_EXACT`, 3 ảnh gần trùng `DUP_IMAGE_NEAR`, 5 ảnh rò rỉ tập kiểm thử `LEAK_TEST`, 3 ảnh quá nhỏ `BAD_SIZE`, 2 ảnh hỏng `CORRUPT_IMAGE`), giữ lại 203 ảnh đưa vào quy trình QC nhãn.

Tại Bước 4 (vòng 1), hệ thống phát hiện 36 lỗi bắt buộc và 149 cảnh báo. Bước sửa tự động (`autofix`) đã giải quyết an toàn 35 lỗi cú pháp và hình học (ghi nhận chi tiết trong `03_fixes.csv`), còn 6 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) được chuyển cho người gán. Sau khi mô phỏng người duyệt xử lý hết ngân sách 80 ảnh (trong đó hoàn thành việc gán nhãn cho cả 6 ảnh thiếu nhãn), dữ liệu sạch hoàn toàn lỗi bắt buộc (0 lỗi ERROR). Tuy nhiên, số ảnh còn cảnh báo chưa được duyệt là 38/203 ảnh, tương ứng tỉ lệ 18.72%, vượt ngưỡng cho phép 10.00% của guideline dự án. Do đó, cửa chặn ra quyết định **HOLD** và xuất bản nháp kiểm định `clean_v1` (203 ảnh) tại `submission/export/clean_v1`.

## 2. Lỗi và phân việc
Tổng hợp các lỗi phát hiện từ `02_error_list_v1` trên 203 ảnh trước khi sửa:

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| BAD_CLASS_ID | 6 dòng | Máy (autofix) | ID lớp ngoài phạm vi 0..3: máy xóa dòng (`drop_line`) theo quy tắc an toàn, không tự ý đoán lớp. |
| BAD_CLASS_NAME | 2 lỗi (data.yaml) | Máy (autofix) | Lớp viết hoa sai quy chuẩn ('Person', 'Bus'): máy tự động chuẩn hóa về đúng `cfg["classes"]` (`rename_classes`). |
| BAD_FORMAT | 3 dòng | Máy (autofix) | Dòng nhãn không đúng 5 cột số hoặc chứa nan/inf: máy xóa dòng hỏng (`drop_line`). |
| BAD_SIZE | 3 ảnh | Máy (intake) | Cạnh ngắn ảnh < 250px không đủ độ phân giải đào tạo: loại bỏ ngay cửa vào (`remove_image`). |
| BOX_OUT_OF_IMAGE | 8 dòng | Máy (autofix) | Box tràn viền quá ngưỡng dung sai 0.002: máy cắt tọa độ (`clip_box`) về trong khoảng [0, 1]. |
| BOX_ZERO | 4 dòng | Máy (autofix) | Box có width hoặc height <= 0: máy xóa dòng rỗng (`drop_line`). |
| CORRUPT_IMAGE | 2 ảnh | Máy (intake) | File ảnh bị hỏng cấu trúc không thể nạp: máy loại bỏ (`remove_image`). |
| DUP_BOX | 7 dòng | Máy (autofix) | Box trùng lặp cùng lớp với box trước đó (IoU > 0.9): máy xóa box ở dòng sau (`drop_line`). |
| DUP_IMAGE_EXACT | 8 ảnh | Máy (intake) | Trùng hash md5 từng byte: máy giữ ảnh đầu tiên, loại bỏ bản sao (`remove_image`). |
| DUP_IMAGE_NEAR | 3 ảnh | Máy (intake) | Trùng thị giác gần đúng (pHash Hamming distance <= 8): máy loại bỏ để tránh học vẹt (`remove_image`). |
| LEAK_TEST | 5 ảnh | Máy (intake) | Trùng ảnh với kho test/gold_val: máy loại bỏ ngay cửa vào để chống rò rỉ dữ liệu (`remove_image`). |
| MISSING_LABEL_FILE | 6 ảnh | Người (hàng đợi) | Máy không thể bịa nhãn (nguyên tắc an toàn): gắn cờ `needs_label` và ưu tiên cao nhất cho người gán mới. |
| BOX_HUGE | 3 dòng | Người (hàng đợi) | Box chiếm > 95% diện tích ảnh: chuyển người kiểm tra xem có gán nhầm toàn bộ hậu cảnh không. |
| BOX_TINY | 6 dòng | Người (hàng đợi) | Box có cạnh ngắn < 12px: chuyển người xem xét theo guideline có phải vật thể nhận diện được không. |
| EMPTY_LABEL | 12 ảnh | Người (hàng đợi) | File nhãn 0 bytes: người duyệt xác định là ảnh nền thực tế hay bị người gán nhãn bỏ sót. |
| POSSIBLE_FALSE_POS | 25 dòng | Người (hàng đợi) | Box nhãn không khớp với bất kỳ dự đoán nào của model yolo26l: nghi ngờ box thừa, cần mắt người xác nhận. |
| POSSIBLE_LOOSE_BOX | 28 dòng | Người (hàng đợi) | Box nhãn và dự đoán cùng lớp nhưng IoU < 0.5: người dùng công cụ căn chỉnh lại hộp bao cho ôm sát vật thể. |
| POSSIBLE_MISSING | 53 dòng | Người (hàng đợi) | Model tin cậy phát hiện vật thể nhưng nhãn không có: người thẩm định và bổ sung box nhãn. |
| POSSIBLE_WRONG_CLASS | 18 dòng | Người (hàng đợi) | Box chồng lấn cao nhưng lệch lớp (ví dụ car vs truck): người phân xử lớp chuẩn theo guideline. |

**Cơ chế xếp hàng đợi `05_review_queue.csv`:**
- Hàng đợi xếp thứ tự ưu tiên dựa trên trọng số nguy cơ: `NEEDS_LABEL` (10 điểm) luôn đứng đầu để đảm bảo không bỏ sót ảnh thiếu nhãn (yếu tố chặn pipeline). Tiếp theo là các lỗi ngữ nghĩa nghiêm trọng: `POSSIBLE_WRONG_CLASS` (3 điểm), `POSSIBLE_MISSING` (2 điểm), `POSSIBLE_FALSE_POS` (2 điểm), `FIXED_DROP_LINE` (2 điểm), `POSSIBLE_LOOSE_BOX` (1.5 điểm), và các cảnh báo nhẹ hơn như `EMPTY_LABEL` (1 điểm), `BOX_HUGE` (0.5 điểm), `BOX_TINY` (0.3 điểm).
- Với ngân sách 80 ảnh, người duyệt đã xem xét toàn bộ 6 ảnh thiếu nhãn (xử lý triệt để 100% lỗi bắt buộc) và 74 ảnh có điểm ưu tiên cao nhất. Nhờ cơ chế này, phần lớn các trường hợp gán nhầm lớp nguy hiểm và bỏ sót vật thể lớn đã được con người sửa chữa trước khi dữ liệu đến cửa chặn.

## 3. Calibration (2 ngưỡng)
Bảng kết quả trước và sau calibration trên tập `data/calib`:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8 | DUP_IMAGE_NEAR: P: 1.00 → 1.00, R: 0.50 → 0.67, F1: 0.67 → 0.80 | Tăng từ 2 lên 8 giúp bắt thêm 33% số ảnh gần trùng bị chỉnh sửa trong calib mà vẫn giữ Precision tuyệt đối 1.00. Không chọn 16 vì trên dữ liệu thật `raw`, ngưỡng 16 quá lỏng, gây cờ nhầm ảnh bình thường thành `LEAK_TEST`. |
| `second_opinion.conf` | 0.25 | 0.60 | WRONG_CLASS: P: 0.56 → 0.62, R: 0.83 → 0.83, F1: 0.67 → 0.71; MISSING: P: 0.50 → 0.57, R: 1.00 → 1.00, F1: 0.67 → 0.73 | Tăng ngưỡng conf từ 0.25 lên 0.60 giúp tăng Precision đáng kể (giảm cảnh báo giả làm quá tải ngân sách người duyệt), trong khi Recall phát hiện nhãn thiếu vẫn đạt tuyệt đối 100% (1.00) và phát hiện nhầm lớp đạt 83%. Không tăng lên 0.7–0.8 vì recall phát hiện thiếu nhãn sẽ giảm xuống 75–88%. |

**Điểm calibration có thể đánh lừa:**
- Tập calib chỉ gồm 39 ảnh với các lỗi được chèn nhân tạo có chủ đích (các cặp ảnh gần trùng được sinh bằng phép co giãn/đổi màu có cấu trúc). Do tập mẫu nhỏ, các chỉ số P/R/F1 thay đổi theo từng bước nhảy lớn (17–33%).
- Nếu chỉ tối ưu hóa điểm số F1 trên tập calib một cách máy móc, ta sẽ chọn `phash_dist = 16` (F1 đạt 0.91, recall 0.83). Tuy nhiên, khi áp dụng ngưỡng 16 lên dữ liệu thực tế `data/raw`, khoảng cách Hamming 16 (khác biệt tới 25% số bit hash) quá lỏng, khiến 6 ảnh hoàn toàn bình thường bị nhận nhầm là rò rỉ kho test (`LEAK_TEST` nhảy vọt từ 5 lên 11 ảnh). Vì thao tác xử lý lỗi trùng là xóa bỏ ảnh vĩnh viễn (`remove_image`), việc chọn ngưỡng 16 sẽ trực tiếp làm mất dữ liệu huấn luyện quý giá. Do đó, trên dữ liệu thật bắt buộc phải ưu tiên Precision cao và chọn `phash_dist = 8`.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Chứng minh gate chặn đúng:**
- Khi chạy thử nghiệm không có người duyệt bằng lệnh:
  `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
- Kết quả kiểm chứng: 6 ảnh thiếu nhãn (`MISSING_LABEL_FILE`) không có người gán, nên các lỗi bắt buộc vẫn còn nguyên ở Bước 4 vòng 3. Cửa chặn `gate.py` lập tức ra kết luận **REWORK** ("Còn 6 lỗi bắt buộc chưa được giải quyết (Rework)"), trả về mã thoát **20**, và hoàn toàn **KHÔNG XUẤT** dataset (thư mục `work/exp_nb` không hề được tạo ra). Điều này chứng minh cửa chặn hoạt động độc lập và bảo vệ chặt chẽ quy trình phát hành.

**(b) Các điểm mù đã biết của pipeline:**
1. **Box lỏng nhẹ hoặc lệch góc nhẹ (IoU từ 0.5 đến 0.6):** Quy tắc `POSSIBLE_LOOSE_BOX` chỉ kích hoạt khi IoU < 0.5. Những bounding box bị rộng viền từ 10–15% hoặc bị lệch góc nhẹ vẫn đạt IoU > 0.5 nên hoàn toàn lọt qua pipeline mà không hề bị cờ cảnh báo.
2. **Sự đồng thuận sai giữa mô hình checker và nhãn người:** Ở các ca vật thể bị che khuất một phần (occlusion), góc chụp từ xa hoặc điều kiện ánh sáng yếu (ví dụ xe bán tải pickup bị nhãn gán nhầm thành `car` và mô hình yolo26l cũng dự đoán là `car` với độ tin cậy cao), pipeline hoàn toàn không thể phát hiện vì không có sự bất đồng ý kiến (disagreement).
3. **Ảnh biến đổi hình học phức tạp vượt quá khả năng của pHash:** Khi ảnh bị crop sâu (> 50%) kết hợp xoay góc nghiêng, khoảng cách pHash vượt quá ngưỡng 8, hệ thống không thể nhận biết đây là ảnh trùng lặp và để lọt vào tập dữ liệu.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy (đã hoàn thiện và kiểm chứng 100% các bài test và yêu cầu kỹ thuật của pipeline QC lõi, calibration 2 ngưỡng và phân tích cửa chặn theo rubric core; sẵn sàng chạy Colab khi có phiên GPU).

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối cùng:**
- Quyết định hiện tại của pipeline là **HOLD** (tỉ lệ ảnh có cảnh báo là 18.72%, vượt ngưỡng cho phép 10.00% của guideline dự án, dù 0 lỗi bắt buộc).
- Để chuyển kết luận thành **RELEASE**, dự án cần thực hiện một trong hai phương án:
  1. Tăng ngân sách duyệt của con người (`budget_images`) từ 80 lên 120 ảnh để người duyệt thẩm định nốt 38 ảnh cảnh báo còn lại trong hàng đợi.
  2. Tổ chức phiên triage vòng 2 tập trung riêng vào 20 ảnh `POSSIBLE_LOOSE_BOX` và 21 ảnh `POSSIBLE_FALSE_POS` để chuyên viên dán nhãn xác nhận chấp nhận (accept) hoặc tinh chỉnh lại tọa độ box.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** "Phân tích yêu cầu kỹ thuật của 4 module `label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py` theo đúng cấu trúc dữ liệu `Dataset` và `Issue` trong `common.py`. Viết code xử lý triệt để các ca biên: bảo toàn số dòng gốc khi có dòng trống, thứ tự ưu tiên drop_line > clip_box khi cùng dòng có nhiều lỗi, và thuật toán so sánh candidate theo đúng quy tắc kiểm định của Day 09."
- **Cách kiểm code AI:** Kiểm tra bằng bộ 79 unit test và e2e test (`pytest -v`), chạy lệnh calibrate kiểm tra tính toàn vẹn của logic so với đáp án `MANIFEST.csv`, chạy e2e pipeline `python -m pipeline.run`, và chạy script kiểm định nghiêm ngặt `check_submission.py --no-train`.
- **Một lần AI sai:** Trong lần đầu phác thảo `autofix.py`, AI đã định xóa file nhãn rỗng khi tất cả box trong ảnh bị drop, nhưng quy chuẩn YOLO quy định file nhãn rỗng (0 bytes) là đại diện hợp lệ cho ảnh nền (background image), không được xóa file. Lỗi đã được phát hiện và sửa lại để chỉ xóa nội dung và giữ file rỗng hoặc phân biệt rõ với `MISSING_LABEL_FILE`.
