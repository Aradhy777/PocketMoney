"""
ExpenseTrack - SQLAlchemy 2.0 Declarative ORM Models
Maps all 5 relational tables (users, categories, uploaded_receipts, expenses, budgets)
with strict MariaDB & Microsoft SQL Server (LocalDB / Azure SQL) cross-compatibility:
- Numeric(10, 2) financial precision
- Dialect-native timestamp handling: MariaDB TIMESTAMP with server-side ON UPDATE CURRENT_TIMESTAMP,
  SQL Server DATETIME2 (avoids SQL Server binary rowversion TIMESTAMP confusion)
- Native MariaDB ENUM types with portable VARCHAR + CHECK constraint on SQL Server
- TINYINT on MariaDB for budgets.month, SMALLINT on SQL Server
- Exact foreign-key action parity (RESTRICT on categories, SET NULL on receipts)
- Uniqueness guarantees for both categorized and overall (NULL category) budgets
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Unicode,
    UnicodeText,
    func,
    text,
)
from sqlalchemy.dialects import mssql, mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

ALLOWED_OCR_STATUSES = ("pending", "success", "failed", "fallback")
ALLOWED_PAYMENT_METHODS = (
    "UPI",
    "Cash",
    "Credit Card",
    "Debit Card",
    "Net Banking",
    "Other",
)


def utc_now() -> datetime:
    """Return timezone-naive UTC datetime compatible with both TIMESTAMP and DATETIME2."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Cross-dialect types:
# MariaDB uses native TIMESTAMP / ENUM / TINYINT.
# SQL Server uses DATETIME2 / VARCHAR+CHECK / SMALLINT.
NativeTimestamp = DateTime().with_variant(mysql.TIMESTAMP(), "mysql").with_variant(mssql.DATETIME2(), "mssql")
LongUnicodeText = UnicodeText().with_variant(mysql.MEDIUMTEXT(), "mysql")

PaymentMethodType = String(30).with_variant(
    mysql.ENUM(*ALLOWED_PAYMENT_METHODS, name="payment_method_enum"), "mysql"
)

OcrStatusType = String(20).with_variant(
    mysql.ENUM(*ALLOWED_OCR_STATUSES, name="ocr_status_enum"), "mysql"
)

BudgetMonthType = SmallInteger().with_variant(mysql.TINYINT(), "mysql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Unicode(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Unicode(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    expenses: Mapped[list[Expense]] = relationship(
        "Expense", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    budgets: Mapped[list[Budget]] = relationship(
        "Budget", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    receipts: Mapped[list[UploadedReceipt]] = relationship(
        "UploadedReceipt", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} email={self.email!r}>"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index("idx_categories_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Unicode(50), nullable=False, unique=True)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'tag'"))
    color: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'#10B981'"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    expenses: Mapped[list[Expense]] = relationship("Expense", back_populates="category")
    budgets: Mapped[list[Budget]] = relationship(
        "Budget", back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r} is_system={self.is_system}>"


class UploadedReceipt(Base):
    __tablename__ = "uploaded_receipts"
    __table_args__ = (
        Index("idx_receipts_user", "user_id", "created_at"),
        Index("idx_receipts_hash", "user_id", "file_hash"),
        CheckConstraint(
            "ocr_status IN ('pending', 'success', 'failed', 'fallback')",
            name="chk_receipt_ocr_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_receipts_user", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    azure_blob_url: Mapped[Optional[str]] = mapped_column(Unicode(500), nullable=True)
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(LongUnicodeText, nullable=True)
    ocr_status: Mapped[str] = mapped_column(
        OcrStatusType,
        nullable=False,
        server_default=text("'pending'"),
    )
    extracted_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    extracted_merchant: Mapped[Optional[str]] = mapped_column(Unicode(100), nullable=True)
    extracted_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    extracted_payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    user: Mapped[User] = relationship("User", back_populates="receipts")
    expenses: Mapped[list[Expense]] = relationship("Expense", back_populates="receipt")

    def __repr__(self) -> str:
        return f"<UploadedReceipt id={self.id} user_id={self.user_id} file_name={self.file_name!r} ocr_status={self.ocr_status!r}>"


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("idx_expenses_user_date", "user_id", "expense_date"),
        Index("idx_expenses_user_category", "user_id", "category_id"),
        Index("idx_expenses_merchant", "user_id", "merchant"),
        Index("fk_expenses_category", "category_id"),
        Index("fk_expenses_receipt", "receipt_id"),
        CheckConstraint("amount > 0.00", name="chk_expense_amount_positive"),
        CheckConstraint(
            "payment_method IN ('UPI', 'Cash', 'Credit Card', 'Debit Card', 'Net Banking', 'Other')",
            name="chk_expense_payment_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_expenses_user", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", name="fk_expenses_category", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    merchant: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(
        PaymentMethodType,
        nullable=False,
        server_default=text("'UPI'"),
    )
    notes: Mapped[Optional[str]] = mapped_column(UnicodeText, nullable=True)
    receipt_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(
            "uploaded_receipts.id",
            name="fk_expenses_receipt",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user: Mapped[User] = relationship("User", back_populates="expenses")
    category: Mapped[Category] = relationship("Category", back_populates="expenses")
    receipt: Mapped[Optional[UploadedReceipt]] = relationship("UploadedReceipt", back_populates="expenses")

    def __repr__(self) -> str:
        return (
            f"<Expense id={self.id} user_id={self.user_id} category_id={self.category_id} "
            f"amount={self.amount} date={self.expense_date}>"
        )


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        Index("idx_budgets_lookup", "user_id", "year", "month"),
        Index("fk_budgets_category", "category_id"),
        Index(
            "uk_user_category_month_year",
            "user_id",
            "category_id",
            "month",
            "year",
            unique=True,
        ),
        # On SQL Server, filtered index enforces overall budget uniqueness at DB level.
        Index(
            "uq_budgets_user_overall_period",
            "user_id",
            "month",
            "year",
            unique=True,
            mssql_where=text("category_id IS NULL"),
        ),
        CheckConstraint("month BETWEEN 1 AND 12", name="chk_budget_month"),
        CheckConstraint("year >= 2020", name="chk_budget_year"),
        CheckConstraint("amount > 0.00", name="chk_budget_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_budgets_user", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categories.id", name="fk_budgets_category", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
    )
    month: Mapped[int] = mapped_column(BudgetMonthType, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        NativeTimestamp,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user: Mapped[User] = relationship("User", back_populates="budgets")
    category: Mapped[Optional[Category]] = relationship("Category", back_populates="budgets")

    def __repr__(self) -> str:
        return (
            f"<Budget id={self.id} user_id={self.user_id} category_id={self.category_id} "
            f"period={self.year}-{self.month:02d} amount={self.amount}>"
        )


def delete_receipt_transactional(
    session: Session,
    receipt_id: int,
    user_id: int,
) -> Optional[str]:
    """
    Transactionally unlink any expense references for an owned receipt before deleting
    its UploadedReceipt record cleanly (compensates for ON DELETE NO ACTION on SQL Server).
    Returns the stored file_path if deleted, else None.
    """
    receipt = (
        session.query(UploadedReceipt)
        .filter(UploadedReceipt.id == receipt_id, UploadedReceipt.user_id == user_id)
        .first()
    )
    if receipt is None:
        return None

    stored_path = receipt.file_path
    from sqlalchemy import update
    session.execute(
        update(Expense)
        .where(Expense.receipt_id == receipt_id, Expense.user_id == user_id)
        .values(receipt_id=None)
    )
    session.delete(receipt)
    session.flush()
    return stored_path


def delete_user_transactional(session: Session, user_id: int) -> bool:
    """
    Safely delete a user and all child records across both MariaDB and SQL Server.
    Explicitly unlinks expense->receipt references before user deletion so SQL Server
    fk_expenses_receipt (ON DELETE NO ACTION) never blocks cascading user deletion.
    """
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        return False

    from sqlalchemy import update
    session.execute(
        update(Expense).where(Expense.user_id == user_id).values(receipt_id=None)
    )
    session.delete(user)
    session.flush()
    return True

