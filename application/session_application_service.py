import uuid

import numpy as np

from domain.session import Session
from domain.variant_image import VariantImage
from repositories.session_repository import SessionRepository


class SessionApplicationService:
    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository
        self._sessions: dict[str, Session] = {}
        self._current_id: str | None = None

    def reload_from_disk(self) -> None:
        self._sessions.clear()
        for sid in self._repo.list_session_ids():
            s = self._repo.load_session(sid)
            if s is not None:
                self._sessions[sid] = s

    @property
    def current_session_id(self) -> str | None:
        return self._current_id

    def current_session(self) -> Session | None:
        if self._current_id is None:
            return None
        return self._sessions.get(self._current_id)

    def all_sessions_ordered(self) -> list[Session]:
        return [self._sessions[sid] for sid in self._repo.list_session_ids() if sid in self._sessions]

    def set_current(self, session_id: str | None) -> None:
        if session_id is not None and session_id not in self._sessions:
            return
        self._save_if_needed()
        self._current_id = session_id

    def _save_if_needed(self) -> None:
        s = self.current_session()
        if s is not None:
            self._repo.save_session(s)

    def create_session(self) -> str:
        self._save_if_needed()
        sid = uuid.uuid4().hex
        n = len(self._sessions) + 1
        sess = Session(session_id=sid, display_name=f"セッション {n}")
        self._sessions[sid] = sess
        self._current_id = sid
        self._repo.save_session(sess)
        return sid

    def delete_current_session(self) -> bool:
        s = self.current_session()
        if s is None:
            return False
        sid = s.session_id
        self._repo.delete_session_folder(sid)
        del self._sessions[sid]
        self._current_id = None
        return True

    def rename_session(self, session_id: str, new_name: str) -> None:
        s = self._sessions.get(session_id)
        if s is None:
            return
        s.display_name = new_name.strip() or s.display_name
        self._repo.save_session(s)

    def persist_current(self) -> None:
        s = self.current_session()
        if s is not None:
            self._repo.save_session(s)

    def add_variant_slot(self) -> str | None:
        s = self.current_session()
        if s is None:
            return None
        vid = uuid.uuid4().hex
        idx = len(s.variants) + 1
        v = VariantImage(variant_id=vid, display_name=f"比較 {idx}")
        s.add_variant(v)
        self._repo.save_session(s)
        return vid

    def remove_variant(self, variant_id: str) -> None:
        s = self.current_session()
        if s is None:
            return
        s.remove_variant(variant_id)
        self._repo.save_session(s)

    def rename_variant(self, variant_id: str, new_name: str) -> None:
        s = self.current_session()
        if s is None:
            return
        v = s.find_variant(variant_id)
        if v is None:
            return
        v.display_name = new_name.strip() or v.display_name
        self._repo.save_session(s)

    def set_base_bgr(self, bgr: np.ndarray | None) -> None:
        s = self.current_session()
        if s is None:
            return
        s.base_image_bgr = bgr
        self.persist_current()

    def clear_base(self) -> None:
        s = self.current_session()
        if s is None:
            return
        s.clear_base()
        self.persist_current()

    def set_variant_bgr(self, variant_id: str, bgr: np.ndarray | None) -> None:
        s = self.current_session()
        if s is None:
            return
        v = s.find_variant(variant_id)
        if v is None:
            return
        v.image_bgr = bgr
        self.persist_current()

    def clear_variant_image(self, variant_id: str) -> None:
        s = self.current_session()
        if s is None:
            return
        v = s.find_variant(variant_id)
        if v is None:
            return
        v.clear_image()
        self.persist_current()
