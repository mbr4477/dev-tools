import json
import os

from anthropic import AsyncAnthropic, Omit

from dev_tools.backends._backend import (
    AgentBackend,
    InvalidSession,
    Response,
    Session,
    ToolCall,
)
from dev_tools.tools import Tool


class AnthropicSession(Session):
    def __init__(self, model: str, system: str | None = None, max_tokens: int = 1024):
        super().__init__()
        self._model = model
        self._system = system
        self._max_tokens = max_tokens
        self._messages = []

    def add_tool_output(self, call_id: str, output: str):
        self._messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": output,
                    }
                ],
            }
        )

    def add_user_content(self, content: str):
        self._messages.append({"role": "user", "content": content})

    def add_assistant_content(self, content: str | object | list):
        self._messages.append({"role": "assistant", "content": content})

    def messages(self) -> list[object]:
        return self._messages

    def system(self) -> str | None:
        return self._system

    def model(self) -> str:
        return self._model

    def max_tokens(self) -> int:
        return self._max_tokens

    def __repr__(self) -> str:
        return json.dumps({"system": self._system, "messages": self._messages})


class AnthropicBackend(AgentBackend):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        super().__init__()
        self._errors = []
        if base_url is None and "ANTHROPIC_BASE_URL" not in os.environ:
            self._errors.append("Missing ANTHROPIC_BASE_URL")

        self._client = AsyncAnthropic(api_key=api_key, base_url=base_url)

    def errors(self) -> list[str]:
        return self._errors

    def create_session(self, model: str, instructions: str | None = None) -> Session:
        return AnthropicSession(model, instructions)

    async def create_response(
        self,
        session: Session,
        tools: list[Tool] | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Response:
        if not isinstance(session, AnthropicSession):
            raise InvalidSession()

        anthropic_tools = (
            [
                {
                    "name": x.name,
                    "description": x.description,
                    "input_schema": x.param_schema,
                }
                for x in tools
            ]
            if tools
            else Omit()
        )

        output_config = Omit()
        if json_schema is not None:
            output_config = {
                "format": {
                    "type": "json_schema",
                    "schema": json_schema,
                }
            }

        response = await self._client.messages.create(
            model=session.model(),
            max_tokens=session.max_tokens(),
            tools=anthropic_tools,
            system=session.system() or Omit(),
            messages=session.messages(),
            output_config=output_config,
        )

        session.add_assistant_content(response.content)

        tool_calls = [
            ToolCall(x.id, x.name, x.input)
            for x in response.content
            if x.type == "tool_use"
        ]

        output_text = (
            next(block for block in response.content if block.type == "text").text
            if response.stop_reason != "tool_use"
            else None
        )

        return Response(
            session,
            output=output_text if json_schema is None else None,
            structured_output=(
                json.loads(output_text)
                if json_schema is not None and output_text is not None
                else None
            ),
            tool_calls=tool_calls,
        )
