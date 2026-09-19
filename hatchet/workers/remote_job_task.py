import io
import traceback

import fabric
from hatchet_provider import hatchet
from hatchet_sdk import Context
from pydantic import BaseModel

REMOTE_JOB_EVENT_KEY = "remote-job"


class RemoteJobInput(BaseModel):
    git_repo_url: str
    git_branch_name: str
    host: str
    user: str
    workdir: str
    script: list[str]
    before_script: list[str] | None = None
    shell: str | None = None
    env: dict[str, str] = {}
    port: int = 22


class RemoteJobOutput(BaseModel):
    success: bool
    logs: list[str]


@hatchet.task(
    name="remote-job",
    on_events=[REMOTE_JOB_EVENT_KEY],
    input_validator=RemoteJobInput,
)
def remote_job(job: RemoteJobInput, ctx: Context) -> RemoteJobOutput:
    success = False
    clone_script = [
        f"git clone -b {job.git_branch_name} {job.git_repo_url} {job.workdir}/code",
        f"cd {job.workdir}/code",
    ]
    script = (
        clone_script
        + (job.before_script or [])
        + job.script
        + [f"rm -rf {job.workdir}/code"]
    )

    logs = []
    try:
        with fabric.Connection(
            job.host, job.user, job.port, forward_agent=True
        ) as conn:
            out_stream = io.StringIO()
            _ = conn.run(
                " && ".join(script),
                shell=job.shell or "/bin/bash",
                warn=True,
                out_stream=out_stream,
                err_stream=out_stream,
                env=job.env,
            )
            logs = out_stream.getvalue().split("\n")
        success = True
    except Exception as e:  # noqa: BLE001
        traceback.print_tb(e.__traceback__)
        print(str(e))
    return RemoteJobOutput(success=success, logs=logs)
