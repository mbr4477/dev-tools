import dataclasses


class Session:
    def add_tool_output(self, call_id: str, output: str): ...
    def add_user_content(self, content: str): ...


@dataclasses.dataclass
class ToolCall:
    call_id: str
    name: str
    args: dict[str, object]


@dataclasses.dataclass
class Response:
    session: Session
    output: str | None = None
    structured_output: object | None = None
    tool_calls: list[ToolCall] = dataclasses.field(default_factory=list)


class AgentBackend:
    def create_session(self, instructions: str | None = None) -> Session: ...
    async def create_response(
        self, session: Session, json_schema: dict[str, object] | None = None
    ) -> Response: ...


class InvalidSession(Exception):
    pass
