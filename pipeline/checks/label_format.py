"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    cfg_lf = cfg.get("label_format", {})
    overflow_tol = cfg_lf.get("overflow_tol", 0.002)
    min_box_px = cfg_lf.get("min_box_px", 12)
    max_box_frac = cfg_lf.get("max_box_frac", 0.95)
    dup_box_iou = cfg_lf.get("dup_box_iou", 0.9)

    for p in ds.label_files():
        stem = p.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue

        seen_boxes = []
        for line_no, raw_line in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(raw_line)
            except ValueError:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    "dòng nhãn không đúng 5 cột số hoặc giá trị không hợp lệ", line=line_no))
                continue

            if not (0 <= cls_id < len(ds.classes)):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"id lớp {cls_id} không thuộc danh mục 0..{len(ds.classes)-1}", line=line_no))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    f"box rỗng (w={w}, h={h})", line=line_no))
                continue

            # Kiểm tra tràn ảnh
            left = cx - w / 2.0
            top = cy - h / 2.0
            right = cx + w / 2.0
            bottom = cy + h / 2.0
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn ảnh (mức tràn {overflow:.4f})",
                                    line=line_no, extra={"overflow": overflow}))

            # Kiểm tra trùng box
            for prev_c, prev_box in seen_boxes:
                if prev_c == cls_id and iou_xywh(prev_box, (cx, cy, w, h)) > dup_box_iou:
                    issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                        f"box trùng lặp với dòng trước đó (IoU > {dup_box_iou})",
                                        line=line_no))
                    break
            seen_boxes.append((cls_id, (cx, cy, w, h)))

            # Kiểm tra box nhỏ (BOX_TINY)
            img_size = ds.image_size(stem)
            if img_size is not None:
                img_w, img_h = img_size
                short_side_px = min(w * img_w, h * img_h)
                if short_side_px < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        f"cạnh ngắn của box ({short_side_px:.1f}px) < {min_box_px}px",
                                        line=line_no))

            # Kiểm tra box quá lớn (BOX_HUGE)
            if (w * h) > max_box_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    f"diện tích box ({w * h:.3f}) > {max_box_frac}",
                                    line=line_no))

    return issues
