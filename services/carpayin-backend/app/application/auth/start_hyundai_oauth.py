from dataclasses import dataclass
from secrets import token_urlsafe
from urllib.parse import urlencode


OAUTH_STATE_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class StartHyundaiOAuthCommand:
    session_id: str


@dataclass(frozen=True)
class StartHyundaiOAuthResult:
    redirect_url: str


class StartHyundaiOAuthService:
    def __init__(
        self,
        qr_session_store,
        oauth_state_store,
        public_base_url: str,
        hyundai_authorize_url: str,
        hyundai_client_id: str,
        oauth_state_generator=None,
    ):
        self.qr_session_store = qr_session_store
        self.oauth_state_store = oauth_state_store
        self.public_base_url = public_base_url.rstrip("/")
        self.hyundai_authorize_url = hyundai_authorize_url
        self.hyundai_client_id = hyundai_client_id
        self.oauth_state_generator = oauth_state_generator or self._generate_oauth_state

    def execute(self, command: StartHyundaiOAuthCommand) -> StartHyundaiOAuthResult:
        if not command.session_id:
            raise ValueError("session_id is required")

        qr_session = self.qr_session_store.get_session(command.session_id)
        if not qr_session:
            raise ValueError("qr_session_not_found")

        status = qr_session.get("status")
        if status == "expired":
            raise ValueError("qr_session_expired")

        if status != "pending":
            raise ValueError("qr_session_not_pending")

        oauth_state = self.oauth_state_generator()
        self.oauth_state_store.save_oauth_state(
            oauth_state=oauth_state,
            session_id=command.session_id,
            ttl_seconds=OAUTH_STATE_TTL_SECONDS,
        )

        return StartHyundaiOAuthResult(
            redirect_url=self._build_redirect_url(oauth_state),
        )

    def _build_redirect_url(self, oauth_state: str) -> str:
        params = urlencode(
            {
                "client_id": self.hyundai_client_id,
                "redirect_uri": f"{self.public_base_url}/auth/redirect",
                "response_type": "code",
                "scope": "openid profile",
                "state": oauth_state,
            }
        )
        separator = "&" if "?" in self.hyundai_authorize_url else "?"
        return f"{self.hyundai_authorize_url}{separator}{params}"

    @staticmethod
    def _generate_oauth_state() -> str:
        return token_urlsafe(32)
