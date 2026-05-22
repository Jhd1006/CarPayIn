from app.application.parking.handle_entry_webhook import HandleEntryWebhookService
from app.application.parking.register_pre_notify import RegisterPreNotifyService


class NotConfiguredDependency:
    def __getattr__(self, name):
        raise RuntimeError("dependency_not_configured")


def get_register_pre_notify_service() -> RegisterPreNotifyService:
    placeholder = NotConfiguredDependency()
    return RegisterPreNotifyService(
        token_validator=placeholder,
        vehicle_repository=placeholder,
        billing_key_repository=placeholder,
        pre_notify_store=placeholder,
        pms_client=placeholder,
        plate_normalizer=placeholder,
    )


def get_handle_entry_webhook_service() -> HandleEntryWebhookService:
    placeholder = NotConfiguredDependency()
    return HandleEntryWebhookService(
        pms_auth_validator=placeholder,
        pre_notify_store=placeholder,
        parking_session_repository=placeholder,
        notification_publisher=placeholder,
    )
