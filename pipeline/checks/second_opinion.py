"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    so_cfg = cfg.get("second_opinion", {})
    conf_thresh = so_cfg.get("conf", 0.25)
    min_area_px = so_cfg.get("min_area_px", 600)
    fp_conf = so_cfg.get("fp_conf", 0.1)
    iou_missing = so_cfg.get("iou_missing", 0.3)
    iou_match = so_cfg.get("iou_match", 0.5)
    iou_loose = so_cfg.get("iou_loose", 0.5)

    issues = []

    for img_path in ds.image_files():
        stem = img_path.stem
        # Bỏ qua ảnh không có trong preds hoặc không có file nhãn
        if stem not in preds or not ds.label_path(stem).exists():
            continue

        raw_preds = preds[stem]
        img_size = ds.image_size(stem)
        img_w, img_h = img_size if img_size is not None else (1, 1)

        # Lấy các dòng nhãn hợp lệ cùng số dòng gốc
        valid_labels = []
        for line_no, raw_line in ds.read_label_lines(stem) or []:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(raw_line)
                if 0 <= cls_id < len(ds.classes) and w > 0 and h > 0:
                    valid_labels.append((line_no, cls_id, (cx, cy, w, h)))
            except ValueError:
                continue

        # 1. Lọc các dự đoán P: conf >= conf_thresh VÀ area_px >= min_area_px
        filtered_preds = []
        for p in raw_preds:
            cls_id = int(p[0])
            conf = float(p[1])
            box = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
            area_px = (box[2] * img_w) * (box[3] * img_h)
            if conf >= conf_thresh and area_px >= min_area_px:
                filtered_preds.append((cls_id, conf, box))

        # Kiểm tra từng dự đoán trong P
        for pred_cls, pred_conf, pred_box in filtered_preds:
            # Tìm các candidate nhãn có IoU >= iou_missing
            cands = []
            for line_no, lbl_cls, lbl_box in valid_labels:
                iou = iou_xywh(pred_box, lbl_box)
                if iou >= iou_missing:
                    cands.append((iou, lbl_cls, line_no, lbl_box))

            if not cands:
                # Không có candidate nào -> POSSIBLE_MISSING
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    f"model dự đoán lớp {ds.classes[pred_cls]} (conf={pred_conf:.2f}) nhưng không có box nhãn tương ứng",
                    line=None, extra={"conf": pred_conf}
                ))
            else:
                same_cands = [c for c in cands if c[1] == pred_cls]
                if same_cands:
                    best_same_iou = max(c[0] for c in same_cands)
                    if best_same_iou < iou_loose:
                        # Cùng lớp nhưng IoU < iou_loose -> POSSIBLE_LOOSE_BOX
                        issues.append(Issue(
                            "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                            f"box nhãn cùng lớp {ds.classes[pred_cls]} nhưng lệch/lỏng (IoU={best_same_iou:.2f} < {iou_loose})",
                            line=None, extra={"conf": pred_conf, "iou": best_same_iou}
                        ))
                    # Ngược lại best_same_iou >= iou_loose -> nhãn đúng lớp đã phủ vật, KHÔNG cờ
                else:
                    diff_cands = [c for c in cands if c[1] != pred_cls]
                    if diff_cands:
                        best_diff_iou = max(c[0] for c in diff_cands)
                        if best_diff_iou >= iou_match:
                            # Khác lớp và IoU >= iou_match -> POSSIBLE_WRONG_CLASS
                            issues.append(Issue(
                                "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                f"nghi gán nhầm lớp: model dự đoán {ds.classes[pred_cls]} (conf={pred_conf:.2f}), nhãn có IoU={best_diff_iou:.2f}",
                                line=None, extra={"conf": pred_conf, "iou": best_diff_iou}
                            ))
                        # Nếu iou_missing <= best_diff_iou < iou_match -> mơ hồ, không cờ gì

        # 2. Kiểm tra POSSIBLE_FALSE_POS cho từng dòng nhãn hợp lệ
        # Dự đoán dùng cho false positive: conf >= fp_conf, không lọc diện tích
        fp_preds = [
            (int(p[0]), float(p[1]), (float(p[2]), float(p[3]), float(p[4]), float(p[5])))
            for p in raw_preds if float(p[1]) >= fp_conf
        ]

        for line_no, lbl_cls, lbl_box in valid_labels:
            matched = False
            for _, _, pred_box in fp_preds:
                if iou_xywh(lbl_box, pred_box) >= iou_missing:
                    matched = True
                    break
            if not matched:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    f"dòng {line_no}: box nhãn không khớp với bất kỳ dự đoán nào của model (conf >= {fp_conf})",
                    line=line_no
                ))

    return issues
