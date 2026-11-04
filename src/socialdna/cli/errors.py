from socialdna.core.exceptions import SocialDNAError
from socialdna.domain.results import Issue, ResultEnvelope


def error_result(command: str, error: SocialDNAError) -> ResultEnvelope:
    return ResultEnvelope(
        command=command,
        status="error",
        errors=[Issue(code=error.code, message=str(error))],
        next_actions=[error.next_action] if error.next_action else [],
    )
