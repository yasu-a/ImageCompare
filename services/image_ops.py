"""テンプレートマッチングと合成プレビュー用の純粋画像処理。"""

from dataclasses import dataclass

import cv2
import numpy as np
from PyQt6.QtGui import QImage, QPixmap

MARGIN_PX = 50
DIFF_THRESHOLD = 30
DIFF_GROUP_RECT_PADDING_PX = 2
DIFF_GROUP_RADIUS_MIN = 1
DIFF_GROUP_RADIUS_MAX = 50

MATCH_ADJUST_USER_MESSAGE = (
    "画像の位置調整に失敗しました。基準画像に近いサイズの画像を貼ってください。"
)


@dataclass
class MatchResult:
    ok: bool
    best_xy: tuple[int, int] | None = None
    message: str = ""


def qimage_to_bgr(qimg: QImage) -> np.ndarray:
    qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = qimg.width(), qimg.height()
    bpl = qimg.bytesPerLine()
    buf = qimg.constBits().asstring(qimg.sizeInBytes())
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, bpl))
    rgb = arr[:, : w * 3].reshape((h, w, 3))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_equal(a: np.ndarray | None, b: np.ndarray | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a.shape == b.shape and bool(np.array_equal(a, b))


def bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def pad_base(base_bgr: np.ndarray, margin: int = MARGIN_PX) -> np.ndarray:
    return cv2.copyMakeBorder(
        base_bgr, margin, margin, margin, margin, cv2.BORDER_REPLICATE
    )


def match_template_full(
    base_bgr: np.ndarray, template_bgr: np.ndarray, margin: int = MARGIN_PX
) -> MatchResult:
    padded = pad_base(base_bgr, margin)
    th, tw = template_bgr.shape[:2]
    ph, pw = padded.shape[:2]
    if th > ph or tw > pw:
        return MatchResult(ok=False, message=MATCH_ADJUST_USER_MESSAGE)
    g1 = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < 0.0:
        return MatchResult(ok=False, message=MATCH_ADJUST_USER_MESSAGE)
    return MatchResult(ok=True, best_xy=(int(max_loc[0]), int(max_loc[1])))


def _paste_bgr(
    canvas: np.ndarray, patch: np.ndarray, x: int, y: int
) -> None:
    th, tw = patch.shape[:2]
    ch, cw = canvas.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(cw, x + tw), min(ch, y + th)
    if x0 >= x1 or y0 >= y1:
        return
    tx0, ty0 = x0 - x, y0 - y
    canvas[y0:y1, x0:x1] = patch[ty0 : ty0 + (y1 - y0), tx0 : tx0 + (x1 - x0)]


def build_variant_layer(
    canvas_shape: tuple[int, int, int], template_bgr: np.ndarray, x: int, y: int
) -> np.ndarray:
    layer = np.zeros(canvas_shape, dtype=np.uint8)
    _paste_bgr(layer, template_bgr, x, y)
    return layer


def diff_mask_bool(
    base_bgr: np.ndarray,
    template_bgr: np.ndarray,
    best_xy: tuple[int, int],
    offset_xy: tuple[int, int],
    margin: int = MARGIN_PX,
) -> tuple[np.ndarray, int, int, int, int]:
    """プレビューと同条件の差分マスク（パディング座標）と (bx, by, tw, th)。"""
    padded = pad_base(base_bgr, margin)
    bx = best_xy[0] + offset_xy[0]
    by = best_xy[1] + offset_xy[1]
    var_layer = build_variant_layer(padded.shape, template_bgr, bx, by)
    g1 = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(var_layer, cv2.COLOR_BGR2GRAY)
    mask = (cv2.absdiff(g1, g2) >= DIFF_THRESHOLD) & (var_layer.sum(axis=2) > 0)
    th, tw = template_bgr.shape[:2]
    return mask, bx, by, tw, th


def _clip_rect_xywh(
    x: int, y: int, w: int, h: int, cw: int, ch: int
) -> tuple[int, int, int, int] | None:
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(cw, x + w)
    y1 = min(ch, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def diff_group_rects_native(
    base_bgr: np.ndarray,
    template_bgr: np.ndarray,
    best_xy: tuple[int, int],
    offset_xy: tuple[int, int],
    radius_px: int,
    margin: int = MARGIN_PX,
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    """
    差分をモルフォロジーでつないだうえで連結成分ごとの外接矩形。
    基準画像座標・比較画像（テンプレート）座標の (x, y, w, h) を返す。
    矩形は最小外接より四辺 DIFF_GROUP_RECT_PADDING_PX 拡張（画像内にクリップ）。
    """
    mask, bx, by, tw, th = diff_mask_bool(
        base_bgr, template_bgr, best_xy, offset_xy, margin
    )
    bh, bw = base_bgr.shape[:2]
    padded_rects = _diff_group_rects_padded(mask, radius_px, DIFF_GROUP_RECT_PADDING_PX)
    base_rects: list[tuple[int, int, int, int]] = []
    variant_rects: list[tuple[int, int, int, int]] = []
    for px, py, pw, ph in padded_rects:
        b = _clip_rect_xywh(px - margin, py - margin, pw, ph, bw, bh)
        if b is not None:
            base_rects.append(b)
        vx0 = max(px, bx)
        vy0 = max(py, by)
        vx1 = min(px + pw, bx + tw)
        vy1 = min(py + ph, by + th)
        vw = vx1 - vx0
        vh = vy1 - vy0
        if vw > 0 and vh > 0:
            vr = _clip_rect_xywh(vx0 - bx, vy0 - by, vw, vh, tw, th)
            if vr is not None:
                variant_rects.append(vr)
    return base_rects, variant_rects


def _diff_group_rects_padded(
    mask: np.ndarray, radius_px: int, pad_px: int
) -> list[tuple[int, int, int, int]]:
    if mask.size == 0 or not bool(np.any(mask)):
        return []
    u8 = (mask.astype(np.uint8) * 255).reshape(mask.shape)
    r = int(max(DIFF_GROUP_RADIUS_MIN, min(DIFF_GROUP_RADIUS_MAX, radius_px)))
    k = max(3, r * 2 + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    # まず close で近傍差分を橋渡しし、元差分との OR で原差分ピクセルの完全保持を担保する。
    morphed = cv2.morphologyEx(u8, cv2.MORPH_CLOSE, kernel)
    merged = cv2.bitwise_or(u8, morphed)
    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        merged, connectivity=8
    )
    h, w = mask.shape[:2]
    out: list[tuple[int, int, int, int]] = []
    for i in range(1, num):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area <= 0:
            continue
        # グループ化は merged で行うが、矩形サイズは元の差分ピクセルだけから求める。
        ys, xs = np.nonzero((labels == i) & mask)
        if xs.size == 0 or ys.size == 0:
            continue
        x0 = max(0, int(xs.min()) - pad_px)
        y0 = max(0, int(ys.min()) - pad_px)
        x1 = min(w, int(xs.max()) + 1 + pad_px)
        y1 = min(h, int(ys.max()) + 1 + pad_px)
        out.append((x0, y0, x1 - x0, y1 - y0))
    return out


def render_preview(
    base_bgr: np.ndarray,
    template_bgr: np.ndarray,
    best_xy: tuple[int, int],
    offset_xy: tuple[int, int],
    margin: int = MARGIN_PX,
) -> tuple[np.ndarray, str]:
    """50/50 透かし合成し、差分を赤で強調する。"""
    padded = pad_base(base_bgr, margin)
    bx = best_xy[0] + offset_xy[0]
    by = best_xy[1] + offset_xy[1]
    var_layer = build_variant_layer(padded.shape, template_bgr, bx, by)

    blend = cv2.addWeighted(padded, 0.5, var_layer, 0.5, 0)
    g1 = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(var_layer, cv2.COLOR_BGR2GRAY)
    mask = (cv2.absdiff(g1, g2) >= DIFF_THRESHOLD) & (var_layer.sum(axis=2) > 0)
    out = blend.copy()
    out[mask] = (0, 0, 255)

    th, tw = template_bgr.shape[:2]
    cv2.rectangle(
        out,
        (bx, by),
        (bx + tw - 1, by + th - 1),
        (0, 255, 0),
        thickness=2,
    )

    return out, ""
