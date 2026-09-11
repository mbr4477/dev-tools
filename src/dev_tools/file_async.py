import asyncio


async def read_file_async(path: str) -> str:
    def read_file_sync(path: str) -> str:
        with open(path, "r") as file:
            return file.read()

    return await asyncio.get_running_loop().run_in_executor(None, read_file_sync, path)


async def write_file_async(path: str, content: str) -> None:
    def write_file_sync(path: str, content: str) -> None:
        with open(path, "w") as file:
            file.write(content)

    await asyncio.get_running_loop().run_in_executor(
        None, write_file_sync, path, content
    )
