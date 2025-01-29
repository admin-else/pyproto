import asyncio
import inspect
import aioconsole

from pyproto.client import SpawningClient

class ConsoleClient(SpawningClient):
    """This is a console to interact with minecraft over a terminal commands include:
    leave: Leave the server.
    help: Provide usage.
    say: Chat in global chat.
    py: Execute python code.
    """
    ps1 = "~> "
    loggind_ids = []

    async def console(self):
        while not self.disconnected.is_set(): 
            try:
                command = await aioconsole.ainput(self.ps1)
            except EOFError:
                command = "leave"
            if not command:
                continue
            
            args = []
            command, *args = command.split()
            func = getattr(self, "command_"+command, None)
            if func:
                if inspect.iscoroutinefunction(func):
                    await func(args)
                else:
                    func(args)
            else:
                print(f"Command \"{command}\" not found.")
            
    async def command_leave(self, _):
        self.transport.close()
        await self.disconnected.wait()

    def command_help(self, args):
        """Command for displaying usage for command(s)."""
        if not args:
            print(ConsoleClient.__doc__)
        for cmd in args:
            func = getattr(self, "command_"+cmd, None)
            if func:
                print(f"""Docs for {cmd}: 
{func.__doc__}
""")
            else:
                print(f"No docs for command \"{cmd}\"")

    def command_py(self, args):
        """Execute python code."""
        try:
            print(exec(" ".join(args)))
        except Exception as e:
            print("Error while executing custom python code", e)


async def main():
    loop = asyncio.get_running_loop()
    client = ConsoleClient()
    await loop.create_connection(lambda: client, "127.0.0.1", 25565)
    await client.console()
    
if __name__ == "__main__":
    asyncio.run(main())
