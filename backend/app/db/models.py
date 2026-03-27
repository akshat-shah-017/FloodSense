from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Ward(Base):
    __tablename__ = "wards"

    ward_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[str] = mapped_column(String(20), nullable=False)
    ward_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ward_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area_km2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Geometry columns are represented as strings in ORM models.
    boundary: Mapped[str] = mapped_column(String, nullable=False)
    centroid: Mapped[str] = mapped_column(String, nullable=False)


class WardFeature(Base):
    __tablename__ = "ward_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ward_id: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spi_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spi_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spi_7: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precip_realtime: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_status: Mapped[str] = mapped_column(String(20), nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ward_id: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    ci_lower: Mapped[float] = mapped_column(Float, nullable=False)
    ci_upper: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False)
    shap_feature_1: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shap_value_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shap_feature_2: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shap_value_2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shap_feature_3: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shap_value_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_status: Mapped[str] = mapped_column(String(20), nullable=False)
