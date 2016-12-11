"""Play midi via fluidsynth."""
from typing import Callable
from pathlib import Path
from asyncio import create_subprocess_exec, ensure_future
from asyncio.subprocess import PIPE, Process
from pkg_resources import resource_filename, Requirement, cleanup_resources

# pylint: disable=too-many-branches
async def list_ports(pmidi=True, err_cb=lambda err: print(err)) -> str:
    """List pmidi ports."""
    if pmidi:
        cmd = 'pmidi'
        options = '-l'
    else:
        cmd = 'jack_lsp'
        options = '-tp'
    result = await create_subprocess_exec(
        cmd, options, stdout=PIPE, stderr=PIPE)
    output, err = await result.communicate()
    if len(err) > 0:
        err_cb(bytes.decode(err))
    if result.returncode != 0:
        raise OSError('{} not functioning {}'.format(cmd, err))
    if pmidi:
        return bytes.decode(output).split('\n')
    else:
        ports = []
        i = 0
        discard = False
        name = ''
        for line in bytes.decode(output).split('\n'):
            if line.startswith('Jack:'):
                # jack debug message
                continue
            if i == 0:
                name = line
                i = 1
            elif i == 1:
                if 'input' not in line:
                    discard = True
                i = 2
            elif i == 2:
                if 'midi' not in line:
                    discard = True
                if not discard:
                    ports.append(name)
                i = 0
                discard = False
        return ports

# pylint: disable=too-few-public-methods
class PortFinder:

    """Find correct pmidi port."""

    port = None

    def __init__(self, match=None, executable='pmidi'):
        self.executable = executable
        self.match = match

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
        output = await list_ports(
            True if self.executable == 'pmidi' else False)
        default_match = 'FLUID'
        for line in output:
            use_match = self.match if self.match is not None and \
                self.match != '' else default_match
            if use_match in line:
                # extract ports
                return line.strip().split(' ')[0]

async def _read_stderr(stderr, err_cb):
    while not stderr.at_eof():
        err = bytes.decode(await stderr.readline())
        if 'jpmidi:out is not connected to anything!' not in err and \
                'jack_client_new: deprecated' not in err and \
                err != '\n' and len(err) > 0:
            err_cb(err)

async def _read_stdout(stdout):
    return bytes.decode(await stdout.readuntil(str.encode('jpmidi> ')))

async def _write_stdin(stdin, msg):
    stdin.write(str.encode('{}\n'.format(msg)))
    await stdin.drain()

async def play_midi(
        port: str,
        midi: Path,
        on_midi_end,
        error_cb=lambda err: print(err),
        pmidi=True,
        await_jack=False) -> Process:
    """Start playing midi file."""
    if pmidi:
        proc = await create_subprocess_exec(
            'pmidi', '-p', port, '-d', '0', str(midi))
        ensure_future(exec_on_midi_end(proc, on_midi_end, port))
        return proc
    proc = await create_subprocess_exec(
        'jpmidi', str(midi), stdin=PIPE, stdout=PIPE, stderr=PIPE)
    ensure_future(_read_stderr(proc.stderr, error_cb))
    # select port
    await _read_stdout(proc.stdout)
    await _write_stdin(proc.stdin, 'connect')
    port_num = None
    for line in (await _read_stdout(proc.stdout)).split('\n'):
        if port in line:
            port_num = line[0:line.index(')')]
    if port_num is None:
        error_cb("no port match found for {}".format(port))
        await stop_midi(proc)
        ensure_future(exec_on_midi_end(proc, on_midi_end, port))
        return proc
    await _write_stdin(proc.stdin, 'connect {}'.format(port_num))

    # play if await_jack is False
    if not await_jack:
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'locate 0')
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'play')

    ensure_future(exec_on_midi_end(proc, on_midi_end, port))
    return proc

async def stop_midi(proc: Process) -> None:
    """Stop midi playback."""
    if proc.stdout is None:
        proc.terminate()
    else:
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'stop')
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'exit')
        # consume any last output
        await proc.stdout.read()

async def exec_on_midi_end(proc: Process, func: Callable, port: str) -> int:
    """Exec func when midi stops playing."""
    return_code = await proc.wait()

    if proc.stdout is None:
        reset_proc = await create_subprocess_exec(
            'pmidi',
            '-p',
            port,
            '-d',
            '0',
            resource_filename(
                Requirement.parse("voicetrainer"),
                'voicetrainer/reset.midi'))
        await reset_proc.wait()
        cleanup_resources()
    await func()
    return return_code
