from dataclasses import dataclass


@dataclass(frozen=True)
class GetLoginSessionStatusCommand:
    session_id: str


@dataclass(frozen=True)
class GetLoginSessionStatusResult:
    status: str
    user_id: str | None = None
    name: str | None = None
    cars: list[dict] | None = None
    temp_access_token: str | None = None


class GetLoginSessionStatusService:
    def __init__(self, app_login_result_store, qr_session_store):
        self.app_login_result_store = app_login_result_store
        self.qr_session_store = qr_session_store

    def execute(
        self,
        command: GetLoginSessionStatusCommand,
    ) -> GetLoginSessionStatusResult:
        if not command.session_id:
            raise ValueError("session_id is required")

        app_login_result = self.app_login_result_store.get_result(
            command.session_id,
        )
        if app_login_result:
            status = app_login_result.get("status")
            if status == "complete":
                return GetLoginSessionStatusResult(
                    status="complete",
                    user_id=app_login_result.get("user_id"),
                    name=app_login_result.get("name"),
                    cars=app_login_result.get("cars"),
                    temp_access_token=app_login_result.get("temp_access_token"),
                )

            if status == "failed":
                raise ValueError("oauth_failed")

        qr_session = self.qr_session_store.get_session(command.session_id)
        if not qr_session:
            raise ValueError("session_not_found")

        status = qr_session.get("status")
        if status == "expired":
            raise ValueError("session_expired")

        if status == "failed":
            raise ValueError("oauth_failed")

        return GetLoginSessionStatusResult(status="pending")
