import json
import shutil
from pathlib import Path
import cv2
import numpy as np

from domain.session import Session
from domain.variant_image import VariantImage


class SessionRepository:
    """ホーム配下 `~/.imagecompare/sessions/<id>/` にセッションを保存する。"""

    def __init__(self, root: Path | None = None) -> None:
        home = Path.home()
        self._root = root if root is not None else home / ".imagecompare"
        self._sessions_dir = self._root / "sessions"

    def sessions_dir(self) -> Path:
        return self._sessions_dir

    def ensure_layout(self) -> None:
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def list_session_ids(self) -> list[str]:
        self.ensure_layout()
        ids: list[str] = []
        for p in sorted(self._sessions_dir.iterdir()):
            if p.is_dir() and (p / "session.json").is_file():
                ids.append(p.name)
        return ids

    def session_path(self, session_id: str) -> Path:
        return self._sessions_dir / session_id

    def load_session(self, session_id: str) -> Session | None:
        sp = self.session_path(session_id)
        meta = sp / "session.json"
        if not meta.is_file():
            return None
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        display_name = data.get("display_name") or session_id
        sess = Session(session_id=session_id, display_name=display_name)
        base_png = sp / "base.png"
        if base_png.is_file():
            arr = cv2.imdecode(np.fromfile(str(base_png), dtype=np.uint8), cv2.IMREAD_COLOR)
            if arr is not None:
                sess.base_image_bgr = arr
        variants_dir = sp / "variants"
        for v in data.get("variants") or []:
            vid = v.get("variant_id")
            vname = v.get("display_name") or "variant"
            fname = v.get("filename")
            if not vid or not fname:
                continue
            fp = sp / fname
            im: np.ndarray | None = None
            if fp.is_file():
                im = cv2.imdecode(np.fromfile(str(fp), dtype=np.uint8), cv2.IMREAD_COLOR)
            sess.add_variant(
                VariantImage(variant_id=str(vid), display_name=str(vname), image_bgr=im)
            )
        return sess

    def save_session(self, session: Session) -> None:
        self.ensure_layout()
        sp = self.session_path(session.session_id)
        if sp.exists():
            shutil.rmtree(sp)
        sp.mkdir(parents=True)
        variants_dir = sp / "variants"
        variants_dir.mkdir(exist_ok=True)
        variant_entries = []
        for i, v in enumerate(session.variants, start=1):
            fname = f"variants/variant_{i:03d}.png"
            fp = sp / fname
            if v.image_bgr is not None:
                ok, buf = cv2.imencode(".png", v.image_bgr)
                if ok:
                    buf.tofile(str(fp))
            variant_entries.append(
                {
                    "variant_id": v.variant_id,
                    "display_name": v.display_name,
                    "filename": fname.replace("\\", "/"),
                }
            )
        if session.base_image_bgr is not None:
            bp = sp / "base.png"
            ok, buf = cv2.imencode(".png", session.base_image_bgr)
            if ok:
                buf.tofile(str(bp))
        meta = {
            "session_id": session.session_id,
            "display_name": session.display_name,
            "variants": variant_entries,
        }
        (sp / "session.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def delete_session_folder(self, session_id: str) -> None:
        sp = self.session_path(session_id)
        if sp.exists():
            shutil.rmtree(sp)
