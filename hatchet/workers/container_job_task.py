import os
import tempfile

import docker
import docker.errors
from docker.types import Mount
from hatchet_provider import hatchet
from hatchet_sdk import Context
from pydantic import BaseModel

CONTAINER_JOB_EVENT_KEY = "container-job"


class ContainerJobInput(BaseModel):
    git_repo_url: str
    git_branch_name: str
    image: str
    script: list[str]
    before_script: list[str] | None = None
    entrypoint: list[str] | None = None
    env: dict[str, str] = {}
    user: str | None = None


class ContainerJobOutput(BaseModel):
    success: bool
    logs: list[str]


@hatchet.task(
    name="container-job",
    on_events=[CONTAINER_JOB_EVENT_KEY],
    input_validator=ContainerJobInput,
)
def container_job(job: ContainerJobInput, ctx: Context) -> ContainerJobOutput:
    client = docker.from_env()
    success = False
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as tmpdir:
        try:
            clone_script = [
                "#!/bin/sh",
                f"git clone -b {job.git_branch_name} {job.git_repo_url} /code",
                "cd /code",
            ]
            script = clone_script + (job.before_script or []) + job.script
            script_path = os.path.join(tmpdir, "script.sh")
            with open(script_path, "w") as script_file:
                script_file.write("\n".join(script))
                script_file.write("\n")

            mounts = [
                Mount("/tmp/script.sh", script_path, type="bind", read_only=True),
                Mount(
                    "/root/.ssh",
                    os.path.join(os.path.expanduser("~"), ".ssh"),
                    type="bind",
                    read_only=True,
                ),
            ]
            logs = (
                client.containers.run(
                    job.image,
                    command=["/tmp/script.sh"],
                    stdout=True,
                    stderr=True,
                    entrypoint=job.entrypoint,
                    auto_remove=True,
                    mounts=mounts,
                    environment=job.env,
                    user=job.user,
                )
                .decode()
                .split("\n")
            )
            success = True
        except docker.errors.ContainerError as e:
            logs = e.container.logs().decode().split("\n")
    return ContainerJobOutput(success=success, logs=logs)
