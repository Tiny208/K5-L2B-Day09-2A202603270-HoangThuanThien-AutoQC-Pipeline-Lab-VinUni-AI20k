"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).
"""
from collections import defaultdict
from pathlib import Path
import yaml

from ..common import ERROR, parse_yolo_line

REMOVE_IMAGE_CODES = {
    "DUP_IMAGE_EXACT",
    "DUP_IMAGE_NEAR",
    "LEAK_TEST",
    "CORRUPT_IMAGE",
    "BAD_SIZE",
}

DROP_CODES = {
    "BAD_FORMAT",
    "BAD_CLASS_ID",
    "BOX_ZERO",
    "DUP_BOX",
}


def fix(ds, issues, cfg):
    fixes = []
    # Chỉ xử lý các lỗi bắt buộc (severity ERROR)
    err_issues = [i for i in issues if i.severity == ERROR]
    if not err_issues:
        return []

    # 1. BAD_CLASS_NAME: Cập nhật data.yaml
    has_class_name_error = any(
        i.code == "BAD_CLASS_NAME" or (i.image == "data.yaml" and "CLASS" in i.code)
        for i in err_issues
    )
    if has_class_name_error and ds.yaml_path.exists():
        try:
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        old_names = data.get("names", {})
        data["names"] = {i: name for i, name in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": str(old_names),
            "after": str(cfg["classes"]),
        })

    # 2. Xoá ảnh hỏng / trùng / rò rỉ: remove_image
    removed_images = set()
    for i in err_issues:
        if i.code in REMOVE_IMAGE_CODES or i.code.startswith("DUP_IMAGE_"):
            stem = i.image
            if stem not in removed_images:
                removed_images.add(stem)
                img_path = ds.image_path(stem)
                if img_path and img_path.exists():
                    img_path.unlink()
                lbl_path = ds.label_path(stem)
                if lbl_path and lbl_path.exists():
                    lbl_path.unlink()
                ds._size_cache.pop(stem, None)
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": "ảnh/nhãn tồn tại",
                    "after": "đã xoá khỏi dataset",
                })

    # 3. MISSING_LABEL_FILE: Chuyển người gán nhãn (needs_label)
    needs_label_stems = set()
    for i in err_issues:
        if i.code == "MISSING_LABEL_FILE":
            stem = i.image
            if stem not in removed_images and stem not in needs_label_stems:
                needs_label_stems.add(stem)
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })

    # 4. Sửa từng file nhãn: drop_line / clip_box
    # Gom lỗi theo image và line
    file_issues = defaultdict(lambda: defaultdict(list))
    for i in err_issues:
        if i.image in removed_images or i.image == "data.yaml" or i.code == "MISSING_LABEL_FILE":
            continue
        if i.code in REMOVE_IMAGE_CODES or i.code.startswith("DUP_IMAGE_"):
            continue
        if i.line is not None:
            file_issues[i.image][i.line].append(i)

    for stem, lines_map in file_issues.items():
        lbl_path = ds.label_path(stem)
        if not lbl_path.exists():
            continue

        raw_lines = lbl_path.read_text(encoding="utf-8", errors="replace").splitlines()
        dropped_lines = set()
        clipped_lines = {}
        file_fixes = []

        # Xử lý theo thứ tự dòng tăng dần
        for line_no in sorted(lines_map.keys()):
            if line_no < 1 or line_no > len(raw_lines):
                continue
            orig_text = raw_lines[line_no - 1]
            codes = {iss.code for iss in lines_map[line_no]}

            # Nếu có lỗi cần drop dòng (hoặc kết hợp drop + clip thì drop ưu tiên)
            if any(c in DROP_CODES for c in codes):
                dropped_lines.add(line_no)
                file_fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": orig_text,
                    "after": "",
                })
            elif "BOX_OUT_OF_IMAGE" in codes:
                # Cắt box về [0, 1]
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(orig_text)
                    left = cx - w / 2.0
                    right = cx + w / 2.0
                    top = cy - h / 2.0
                    bottom = cy + h / 2.0

                    cl = max(0.0, min(1.0, left))
                    cr = max(0.0, min(1.0, right))
                    ct = max(0.0, min(1.0, top))
                    cb = max(0.0, min(1.0, bottom))

                    new_w = cr - cl
                    new_h = cb - ct

                    if new_w <= 0 or new_h <= 0:
                        # Box nằm hoàn toàn ngoài ảnh -> xoá dòng
                        dropped_lines.add(line_no)
                        file_fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": orig_text,
                            "after": "",
                        })
                    else:
                        new_cx = (cl + cr) / 2.0
                        new_cy = (ct + cb) / 2.0
                        clipped_text = f"{cls_id} {round(new_cx, 6)} {round(new_cy, 6)} {round(new_w, 6)} {round(new_h, 6)}"
                        clipped_lines[line_no] = clipped_text
                        file_fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "clip_box",
                            "before": orig_text,
                            "after": clipped_text,
                        })
                except ValueError:
                    # Nếu không parse được thì drop_line
                    dropped_lines.add(line_no)
                    file_fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig_text,
                        "after": "",
                    })

        # Ghi lại nội dung file nhãn
        new_raw_lines = []
        for idx, ln in enumerate(raw_lines):
            l_num = idx + 1
            if l_num in dropped_lines:
                continue
            elif l_num in clipped_lines:
                new_raw_lines.append(clipped_lines[l_num])
            else:
                new_raw_lines.append(ln)

        new_content = "\n".join(new_raw_lines) + ("\n" if new_raw_lines else "")
        lbl_path.write_text(new_content, encoding="utf-8")
        fixes.extend(file_fixes)

    return fixes
