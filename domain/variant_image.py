from dataclasses import dataclass

import numpy as np


@dataclass
class VariantImage:
    variant_id: str
    display_name: str
    image_bgr: np.ndarray | None = None

    def clear_image(self) -> None:
        self.image_bgr = None

    def has_image(self) -> bool:
        return self.image_bgr is not None
