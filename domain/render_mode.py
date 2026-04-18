from enum import Enum


class RenderMode(Enum):
    OVERLAY_50_50 = "overlay_50_50"
    SUBTRACT = "subtract"
    OVERLAY_DIFF = "overlay_diff"

    @classmethod
    def default(cls):
        return cls.OVERLAY_50_50

    def label_ja(self) -> str:
        return {
            RenderMode.OVERLAY_50_50: "50/50 透かし",
            RenderMode.SUBTRACT: "Subtract",
            RenderMode.OVERLAY_DIFF: "透かし + 差分(赤)",
        }[self]
