"""Play midi via fluidsynth."""
from typing import Callable
from itertools import filterfalse
from pathlib import Path
from asyncio import create_subprocess_exec, ensure_future, Lock
from asyncio.subprocess import PIPE, Process
from pkg_resources import resource_filename, Requirement, cleanup_resources

# some state
_ERR_CB = print
_PROC_LOCK = Lock()
_PROC = None
_PMIDI_PORT = None
_JPMIDI_PORT = None

def set_err_cb(err_cb: Callable[[str], None]):
    """Give module a way to report errors."""
    global _ERR_CB  # pylint: disable=global-statement
    _ERR_CB = err_cb

def set_pmidi_port(port: str):
    """Set pmidi port string."""
    global _PMIDI_PORT  # pylint: disable=global-statement
    _PMIDI_PORT = port

def set_jpmidi_port(port: str):
    """Set jpmidi port string."""
    global _JPMIDI_PORT  # pylint: disable=global-statement
    _JPMIDI_PORT = port

async def list_ports(pmidi=True) -> str:
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
    if len(err) > 0 or result.returncode != 0:
        _ERR_CB(bytes.decode(err))
    if pmidi:
        return bytes.decode(output).split('\n')
    ports = []
    lines = filterfalse(
            lambda x: x.startswith('Jack:'),
            bytes.decode(output).split('\n'))
    for name, input_, midi in zip(*[lines]*3):
        if 'input' in input_ and 'midi' in midi:
            ports.append(name)
    return ports

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

async def _play_midi(
        port: str,
        midi: Path,
        on_midi_end: Callable[[], None],
        pmidi: bool=True,
        await_jack: bool=False) -> Process:
    """Start playing midi file."""
    if pmidi:
        proc = await create_subprocess_exec(
            'pmidi', '-p', port, '-d', '0', str(midi))
        ensure_future(_exec_on_midi_end(proc, on_midi_end, port))
        return proc
    proc = await create_subprocess_exec(
        'jpmidi', str(midi), stdin=PIPE, stdout=PIPE, stderr=PIPE)
    ensure_future(_read_stderr(proc.stderr, _ERR_CB))
    # select port
    await _read_stdout(proc.stdout)
    await _write_stdin(proc.stdin, 'connect')
    port_num = None
    for line in (await _read_stdout(proc.stdout)).split('\n'):
        if port in line:
            port_num = line[0:line.index(')')]
    if port_num is None:
        _ERR_CB("no port match found for {}".format(port))
        await _stop_midi()
        ensure_future(_exec_on_midi_end(proc, on_midi_end, port))
        return proc
    await _write_stdin(proc.stdin, 'connect {}'.format(port_num))

    # play if await_jack is False
    if not await_jack:
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'locate 0')
        await _read_stdout(proc.stdout)
        await _write_stdin(proc.stdin, 'play')

    ensure_future(_exec_on_midi_end(proc, on_midi_end, port))
    return proc

async def _stop_midi() -> None:
    """Stop midi playback."""
    if _PROC.stdout is None:
        _PROC.terminate()
    else:
        await _read_stdout(_PROC.stdout)
        await _write_stdin(_PROC.stdin, 'stop')
        await _read_stdout(_PROC.stdout)
        await _write_stdin(_PROC.stdin, 'exit')
        # consume any last output
        await _PROC.stdout.read()

async def play(
        midi: Path,
        on_midi_end: Callable[[], None],
        pmidi: bool=True,
        await_jack: bool=False) -> bool:
    """Start playback is possible. Return value is sucess."""
    global _PROC  # pylint: disable=global-statement
    if pmidi and _PMIDI_PORT is None:
        _ERR_CB((
            "No pmidi port found. Did you select the correct one? "
            "Is your synth running?"))
        return False
    if not pmidi and _JPMIDI_PORT is None:
        _ERR_CB("No jpmidi port setting found. Did you select one?")
        return False
    if _PROC_LOCK.locked():
        _ERR_CB("Playback was already started, cancelling task.")
        return False
    await _PROC_LOCK.acquire()
    _PROC = await _play_midi(
        _PMIDI_PORT if pmidi else _JPMIDI_PORT,
        midi,
        on_midi_end,
        pmidi,
        await_jack)
    return True

def is_playing():
    """Is there currently a MIDI file playing?"""
    return _PROC_LOCK.locked()

async def stop():
    """Stop playback no matter the circumstances."""
    if not _PROC_LOCK.locked():
        _ERR_CB("No active playback process, nothing to stop.")
        return
    if _PROC is None:
        _ERR_CB("Proc is locked, but value is None: bug.")
        _PROC_LOCK.release()
        return
    await _stop_midi()

async def play_or_stop(
        midi: Path,
        on_midi_end: Callable[[], None],
        pmidi: bool=True,
        await_jack: bool=False) -> bool:
    """Toggle playback state. Return True if now playing, else False."""
    if _PROC_LOCK.locked():
        await stop()
        return False
    else:
        return await play(midi, on_midi_end, pmidi, await_jack)


async def _exec_on_midi_end(proc: Process, func: Callable, port: str) -> int:
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
    _PROC_LOCK.release()
    await func()
    return return_code
