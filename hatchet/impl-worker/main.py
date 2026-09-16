from hatchet_sdk import Context, Hatchet
from pydantic import BaseModel

hatchet = Hatchet()


class ImplInput(BaseModel):
    spec: str


class ImplOutput(BaseModel):
    patch: str


@hatchet.task(name="impl-spec", input_validator=ImplInput)
def impl_spec(input_: ImplInput, ctx: Context) -> ImplOutput:
    return ImplOutput(patch=f"Patch for spec: {input_.spec}")


def main():
    worker = hatchet.worker(name="impl-worker", workflows=[impl_spec])
    worker.start()


if __name__ == "__main__":
    main()
