from dataclasses import dataclass, field

import numpy as np

from domain.variant_image import VariantImage


@dataclass
class Session:
    session_id: str
    display_name: str
    base_image_bgr: np.ndarray | None = None
    variants: list[VariantImage] = field(default_factory=list)

    def clear_base(self) -> None:
        self.base_image_bgr = None

    def add_variant(self, variant: VariantImage) -> None:
        self.variants.append(variant)

    def remove_variant(self, variant_id: str) -> bool:
        n = len(self.variants)
        self.variants = [v for v in self.variants if v.variant_id != variant_id]
        return len(self.variants) != n

    def find_variant(self, variant_id: str) -> VariantImage | None:
        for v in self.variants:
            if v.variant_id == variant_id:
                return v
        return None
