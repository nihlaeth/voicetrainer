"""Play midi via fluidsynth."""
from typing import Callable
from pathlib import Path
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE, Process

async def list_ports() -> str:
    """List pmidi ports."""
    result = await create_subprocess_exec(
        'pmidi', '-l', stdout=PIPE, stderr=PIPE)
    output, err = await result.communicate()
    if result.returncode != 0:
        raise OSError('pmidi not functioning {}'.format(err))
    return bytes.decode(output).split('\n')

# pylint: disable=too-few-public-methods
class PortFinder:

    """Find correct pmidi port."""

    match = None
    port = None

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self.port is None:
            self.port = await self.fetch_data()
            return self.port
        else:
            raise StopAsyncIteration

    async def fetch_data(self):
        """Match ports."""
        output = await list_ports()
        default_match = 'FLUID'
        for line in output:
            use_match = self.match if self.match is not None and \
                self.match != '' else default_match
            if use_match in line:
                # extract ports
                return line.strip().split(' ')[0]

async def play_midi(port: str, midi: Path) -> Process:
    """Start playing midi file."""
    return await create_subprocess_exec(
        'pmidi', '-p', port, str(midi))

async def stop_midi(proc: Process) -> None:
    """Stop midi playback."""
    proc.terminate()

async def exec_on_midi_end(proc: Process, func: Callable) -> int:
    """Exec func when midi stops playing."""
    return_code = await proc.wait()
    await func()
    return return_code
