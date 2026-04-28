from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.models.base import Base


class ChaoxingQrSession(Base):
    __tablename__ = "chaoxing_qr_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True)
    session_token = Column(String(80), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="pending", comment="pending/scannable/scanned/confirmed/expired/failed")
    login_url = Column(Text, nullable=True)
    qr_page_url = Column(Text, nullable=True)
    qr_image_url = Column(Text, nullable=True)
    qr_image_data = Column(Text, nullable=True, comment="base64 data url")
    page_title = Column(String(255), nullable=True)
    browser_meta_json = Column(JSON, default=dict)
    cookies_json = Column(JSON, default=list)
    last_error = Column(Text, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("owner_username", "session_token", name="uq_chaoxing_qr_session_owner_token"),
    )

    def to_dict(self, include_cookies: bool = False):
        data = {
            "id": self.id,
            "owner_username": self.owner_username,
            "session_token": self.session_token,
            "status": self.status,
            "login_url": self.login_url,
            "qr_page_url": self.qr_page_url,
            "qr_image_url": self.qr_image_url,
            "qr_image_data": self.qr_image_data,
            "page_title": self.page_title,
            "browser_meta": self.browser_meta_json or {},
            "cookies": self.cookies_json or [],
            "last_error": self.last_error,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if not include_cookies:
            data.pop("cookies", None)
        return data
