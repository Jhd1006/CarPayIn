from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.pms.calculate_fee import CalculateFeeService
from app.application.pms.handle_lpr_entry import HandleLprEntryService
from app.application.pms.record_payment_complete import RecordPaymentCompleteService
from app.application.pms.register_pre_notify import RegisterPreNotifyService
from app.infra.db.session import get_db_session
from app.infra.repositories.payment_request_repository import (
    SqlAlchemyPaymentRequestRepository,
)
from app.infra.repositories.pre_registration_repository import (
    SqlAlchemyPreRegistrationRepository,
)
from app.infra.repositories.pms_session_repository import (
    SqlAlchemyPmsSessionRepository,
)


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_register_pre_notify_service(
    session: Session = Depends(get_db_session),
) -> RegisterPreNotifyService:
    return RegisterPreNotifyService(
        pre_registration_repository=SqlAlchemyPreRegistrationRepository(session),
    )


def get_handle_lpr_entry_service(
    session: Session = Depends(get_db_session),
) -> HandleLprEntryService:
    placeholder = NotConfiguredDependency()
    return HandleLprEntryService(
        pre_registration_repository=SqlAlchemyPreRegistrationRepository(session),
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        carpayin_webhook_client=placeholder,
    )


def get_calculate_fee_service(
    session: Session = Depends(get_db_session),
) -> CalculateFeeService:
    placeholder = NotConfiguredDependency()
    return CalculateFeeService(
        pms_session_repository=SqlAlchemyPmsSessionRepository(session),
        fee_calculator=placeholder,
    )


def get_record_payment_complete_service(
    session: Session = Depends(get_db_session),
) -> RecordPaymentCompleteService:
    return RecordPaymentCompleteService(
        payment_request_repository=SqlAlchemyPaymentRequestRepository(session),
    )
