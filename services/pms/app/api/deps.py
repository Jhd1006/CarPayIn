from app.application.pms.calculate_fee import CalculateFeeService
from app.application.pms.handle_lpr_entry import HandleLprEntryService
from app.application.pms.record_payment_complete import RecordPaymentCompleteService
from app.application.pms.register_pre_notify import RegisterPreNotifyService


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_register_pre_notify_service() -> RegisterPreNotifyService:
    return RegisterPreNotifyService(pre_registration_repository=NotConfiguredDependency())


def get_handle_lpr_entry_service() -> HandleLprEntryService:
    placeholder = NotConfiguredDependency()
    return HandleLprEntryService(
        pms_session_repository=placeholder,
        carpayin_webhook_client=placeholder,
    )


def get_calculate_fee_service() -> CalculateFeeService:
    placeholder = NotConfiguredDependency()
    return CalculateFeeService(
        pms_session_repository=placeholder,
        fee_calculator=placeholder,
    )


def get_record_payment_complete_service() -> RecordPaymentCompleteService:
    return RecordPaymentCompleteService(
        payment_request_repository=NotConfiguredDependency(),
    )
