from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.models import PaymentRequest


class SqlAlchemyPaymentRequestRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_payment_request(
        self,
        *,
        idempotency_key: str,
        pms_session_id: str,
        carpay_session_id: str,
        tx_id: str,
        amount: int,
        currency: str,
        approval_no: str,
    ) -> dict:
        existing = self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        payment_request = PaymentRequest(
            pms_session_id=pms_session_id,
            carpay_parking_session_id=carpay_session_id,
            carpay_tx_id=tx_id,
            amount=amount,
            currency=currency,
            status="success",
            idempotency_key=idempotency_key,
            approval_no=approval_no,
            completed_at=datetime.now(timezone.utc),
        )
        self.session.add(payment_request)
        self.session.commit()
        return self._to_dict(payment_request)

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        statement = select(PaymentRequest).where(
            PaymentRequest.idempotency_key == idempotency_key
        )
        payment_request = self.session.scalar(statement)
        return self._to_dict(payment_request) if payment_request is not None else None

    @staticmethod
    def _to_dict(payment_request: PaymentRequest) -> dict:
        return {
            "payment_request_id": str(payment_request.payment_request_id),
            "pms_session_id": payment_request.pms_session_id,
            "carpay_session_id": payment_request.carpay_parking_session_id,
            "tx_id": payment_request.carpay_tx_id,
            "amount": payment_request.amount,
            "currency": payment_request.currency,
            "status": payment_request.status,
            "idempotency_key": payment_request.idempotency_key,
            "approval_no": payment_request.approval_no,
        }
