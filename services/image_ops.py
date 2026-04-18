"""テンプレートマッチングと合成プレビュー用の純粋画像処理。"""

from dataclasses import dataclass

import cv2
import numpy as np
from PyQt6.QtGui import QImage, QPixmap

from domain.render_mode import RenderMode

MARGIN_PX = 50
DIFF_THRESHOLD = 30

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


def render_preview(
    base_bgr: np.ndarray,
    template_bgr: np.ndarray,
    best_xy: tuple[int, int],
    offset_xy: tuple[int, int],
    mode: RenderMode,
    margin: int = MARGIN_PX,
) -> tuple[np.ndarray, str]:
    padded = pad_base(base_bgr, margin)
    bx = best_xy[0] + offset_xy[0]
    by = best_xy[1] + offset_xy[1]
    var_layer = build_variant_layer(padded.shape, template_bgr, bx, by)

    msg = ""
    if mode is RenderMode.OVERLAY_50_50:
        out = cv2.addWeighted(padded, 0.5, var_layer, 0.5, 0)
    elif mode is RenderMode.SUBTRACT:
        out = cv2.subtract(padded, var_layer)
    elif mode is RenderMode.OVERLAY_DIFF:
        blend = cv2.addWeighted(padded, 0.5, var_layer, 0.5, 0)
        g1 = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(var_layer, cv2.COLOR_BGR2GRAY)
        mask = (cv2.absdiff(g1, g2) >= DIFF_THRESHOLD) & (var_layer.sum(axis=2) > 0)
        out = blend.copy()
        out[mask] = (0, 0, 255)
    else:
        out = padded.copy()
        msg = "不明な表示モード"

    th, tw = template_bgr.shape[:2]
    cv2.rectangle(
        out,
        (bx, by),
        (bx + tw - 1, by + th - 1),
        (0, 255, 0),
        thickness=2,
    )

    return out, msg
