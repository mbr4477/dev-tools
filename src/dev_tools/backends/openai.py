import json
import os

from openai import AsyncOpenAI
from openai.types.responses import ResponseOutputItem

from dev_tools.backends._backend import (
    AgentBackend,
    InvalidSession,
    Response,
    Session,
    ToolCall,
)
from dev_tools.tools import ToolSchema


class OpenAISession(Session):
    def __init__(self, model: str, instructions: str | None = None):
        super().__init__()
        self._model = model
        self._input_list = []
        self._instructions = instructions

    def extend(self, outputs: list[ResponseOutputItem]):
        self._input_list += outputs

    def add_tool_output(self, call_id: str, output: str):
        self._input_list.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )

    def add_user_content(self, content: str):
        self._input_list.append({"role": "user", "content": content})

    def input_list(self) -> list[object]:
        return self._input_list

    def instructions(self) -> str | None:
        return self._instructions

    def model(self) -> str:
        return self._model

    def __repr__(self) -> str:
        return json.dumps(
            {"instructions": self._instructions, "input_list": self._input_list}
        )


class OpenAIBackend(AgentBackend):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        super().__init__()
        self._config_errors = []
        if base_url is None and "OPENAI_BASE_URL" not in os.environ:
            self._config_errors.append("Missing OPENAI_BASE_URL")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def config_errors(self) -> list[str]:
        return self._config_errors

    def create_session(self, model: str, instructions: str | None = None) -> Session:
        return OpenAISession(model, instructions)

    async def create_response(
        self,
        session: Session,
        tools: list[ToolSchema] | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Response:
        if not isinstance(session, OpenAISession):
            raise InvalidSession()

        openai_tools = (
            [
                {
                    "type": "function",
                    "name": x.name,
                    "description": x.description,
                    "parameters": x.param_schema,
                }
                for x in tools
            ]
            if tools
            else None
        )

        text = None
        if json_schema is not None:
            text = {
                "format": {
                    "type": "json_schema",
                    "name": json_schema.get("name", "output"),
                    "strict": True,
                    "schema": json_schema,
                }
            }

        response = await self._client.responses.create(
            model=session.model(),
            tools=openai_tools,
            instructions=session.instructions(),
            input=session.input_list(),
            text=text,
        )

        session.extend(response.output)

        tool_calls = [
            ToolCall(x.call_id, x.name, json.loads(x.arguments))
            for x in response.output
            if x.type == "function_call"
        ]

        return Response(
            session,
            output=(
                response.output_text
                if response.output_text and json_schema is None
                else None
            ),
            structured_output=(
                json.loads(response.output_text)
                if response.output_text and json_schema is not None
                else None
            ),
            tool_calls=tool_calls,
        )
