"""software/ui/compare_components.py
Công cụ so sánh định lượng độ tương đồng giữa ảnh thành phần tham chiếu (Saleae Logic 2)
và ảnh render thực tế từ ứng dụng Logic Analyzer:
- SSIM (Structural Similarity Index): Cấu trúc hình học, vị trí icon, đường viền (40%)
- Color Histogram Correlation: Độ tương đồng bảng màu RGB thực tế (40%)
- Checklist kiểm tra tính năng thị giác (Visual Feature Checklist) (20%)
"""

import os
import sys
import numpy as np
from PIL import Image


def compute_histogram_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Tính độ tương đồng biểu đồ màu RGB (Cosine correlation)."""
    # Resize về cùng kích thước để so sánh màu
    target_size = (max(img1.width, img2.width), max(img1.height, img2.height))
    i1 = img1.convert("RGB").resize(target_size)
    i2 = img2.convert("RGB").resize(target_size)

    hist1 = np.array(i1.histogram(), dtype=np.float64)
    hist2 = np.array(i2.histogram(), dtype=np.float64)

    # Chuẩn hóa
    norm1 = np.linalg.norm(hist1)
    norm2 = np.linalg.norm(hist2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    cos_sim = np.dot(hist1, hist2) / (norm1 * norm2)
    return float(max(0.0, min(1.0, cos_sim)))


def compute_ssim(img1: Image.Image, img2: Image.Image, block_size: int = 11) -> float:
    """Tính chỉ số tương đồng cấu trúc SSIM chuẩn khối trượt 11x11 (Wang et al. 2004)."""
    target_size = (img1.width, img1.height)
    i1 = np.array(img1.convert("L").resize(target_size), dtype=np.float64)
    i2 = np.array(img2.convert("L").resize(target_size), dtype=np.float64)

    h, w = i1.shape
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    # Trượt khối block_size
    ssim_list = []
    step = block_size
    for y in range(0, h - block_size + 1, step):
        for x in range(0, w - block_size + 1, step):
            b1 = i1[y:y + block_size, x:x + block_size]
            b2 = i2[y:y + block_size, x:x + block_size]

            mu1 = np.mean(b1)
            mu2 = np.mean(b2)
            var1 = np.var(b1)
            var2 = np.var(b2)
            cov12 = np.mean((b1 - mu1) * (b2 - mu2))

            s = ((2 * mu1 * mu2 + c1) * (2 * cov12 + c2)) / ((mu1**2 + mu2**2 + c1) * (var1 + var2 + c2))
            ssim_list.append(s)

    if not ssim_list:
        return 0.0
    return float(max(0.0, min(1.0, np.mean(ssim_list))))


def evaluate_component(ref_path: str, gen_path: str, checklist_score: float = 1.0) -> dict:
    """
    Đánh giá độ tương đồng tổng hợp giữa ảnh tham chiếu và ảnh render:
    Tổng điểm (%) = Histogram * 40 + SSIM * 40 + Checklist * 20
    """
    if not os.path.exists(ref_path):
        return {"error": f"Không tìm thấy file tham chiếu: {ref_path}"}
    if not os.path.exists(gen_path):
        return {"error": f"Không tìm thấy file render: {gen_path}"}

    img_ref = Image.open(ref_path)
    img_gen = Image.open(gen_path)

    hist_score = compute_histogram_similarity(img_ref, img_gen)
    ssim_score = compute_ssim(img_ref, img_gen)
    checklist_clamped = max(0.0, min(1.0, checklist_score))

    total_score = (hist_score * 0.40 + ssim_score * 0.40 + checklist_clamped * 0.20) * 100.0

    return {
        "ref_size": img_ref.size,
        "gen_size": img_gen.size,
        "histogram_similarity": round(hist_score * 100, 2),
        "ssim_similarity": round(ssim_score * 100, 2),
        "checklist_score": round(checklist_clamped * 100, 2),
        "total_match_percent": round(total_score, 1)
    }


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ref_file = sys.argv[1]
        gen_file = sys.argv[2]
        chk = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        res = evaluate_component(ref_file, gen_file, chk)
        print("Kết quả đánh giá:", res)
    else:
        print("Sử dụng: python3 compare_components.py <ref_img> <gen_img> [checklist_score 0..1]")
