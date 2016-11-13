"""Play midi via fluidsynth."""
from typing import Callable
from os.path import dirname, join, realpath
from shlex import quote
from asyncio import create_subprocess_exec, create_subprocess_shell, sleep, get_event_loop
from asyncio.subprocess import PIPE, Process

async def get_qsynth_port() -> str:
    """Check on wich midi port qsynth is running, retry every 5 seconds."""
    while True:
        result = await create_subprocess_exec(
            'pmidi', '-l', stdout=PIPE, stderr=PIPE)
        output, err = await result.communicate()
        if result.returncode != 0:
            raise OSError('pmidi not functioning {}'.format(err))
        output = bytes.decode(output).split('\n')
        for line in output:
            match = ['Qsynth', 'qsynth', 'FLUID']
            if any([word in line for word in match]):
                # extract port
                return line.strip().split(' ')[0]
        await sleep(5)

async def play_midi(port: str, midi: str) -> Process:
    """Start playing midi file."""
    # return await create_subprocess_exec(
    #     'pmidi', '-p', port, midi.encode('ascii'))
    return await create_subprocess_shell(
        "pmidi -p {} {}".format(
            quote(port),
            quote(midi)))

async def stop_midi(proc: Process) -> None:
    """Stop midi playback."""
    proc.terminate()

async def exec_on_midi_end(proc: Process, func: Callable) -> int:
    """Exec func when midi stops playing."""
    return_code = await proc.wait()
    await func()
    return return_code

if __name__ == "__main__":
    # pylint: disable=invalid-name
    loop = get_event_loop()
    port_ = loop.run_until_complete(get_qsynth_port())
    proc_ = loop.run_until_complete(play_midi(
        port_,
        join(
            dirname(realpath(__file__)),
            "../exercises/control-140bmp-d.midi")))
    loop.run_until_complete(exec_on_midi_end(proc_, lambda: print('finis')))
    loop.close()
