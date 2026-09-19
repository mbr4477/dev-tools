from container_job_task import container_job
from hatchet_provider import hatchet


def main():
    worker = hatchet.worker(
        name="container-worker",
        workflows=[container_job],
    )
    worker.start()


if __name__ == "__main__":
    main()
