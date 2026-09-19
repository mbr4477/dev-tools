from container_job_task import container_job
from hatchet_provider import hatchet
from remote_job_task import remote_job


def main():
    worker = hatchet.worker(
        name="container-worker",
        workflows=[container_job, remote_job],
    )
    worker.start()


if __name__ == "__main__":
    main()
