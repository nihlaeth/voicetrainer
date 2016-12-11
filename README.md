# voicetrainer
MIDI voice exercises made convenient

## About
I'm a singer and I have a disability that prevents me from using a keyboard (musical or otherwise). Since speech recognition and making music are a really bad combination, I could pretty much only do voice exercises during my singing lessons, which frustrated me to no end.

So I started thinking about a solution. What I want from this is an exercise that I can easily change into a different tempo or key. It should be trivial to pause, repeat, or change the parameters. Everything has to be operable by mouse alone. And it should be quality MIDI, because I can't stand the sinus tone that most MIDI sequencers emit. Also, I want sheet music. Beautiful sheet music, preferably with lots of notes (the textual kind). And it shouldn't be hard to add new exercises, or at least not a lot of dictation work.

It says something about me that I'd rather dictate code one letter at a time for four days straight than click pause and play a few times in a big MIDI file, but here it is, so you won't have to repeat the feat. Enjoy!

## Examples
See https://github.com/nihlaeth/voicetrainerdata for exercise and song examples.

## Dependencies
* python >= 3.5.2
* pillow
* tk/tcl
* lilypond (I used the dev version)
* pmidi
* fluidsynth or other alsamidi synth

## Installation
```
pip install .
```

## Usage
```
voicetrainer
```

## Todo
* document song feature and lily settings
* document jpmidi and jack transport use
* refactor export to be in MainWindow and file menu
* make release and publish
* have scroll wheel scroll scrollbars
* set sane defaults for pylint
* display natural tempo and key
* make measure selector scale
* exercise next should look at enabled features
* make repeat_once exercise specific
* refactor: make sure method do not rely on currently active tab

## Problems
* jpmidi: sustain weirdness
* play/stop buttons don't reflect play status after tab switch

## Planned features
* add command line script to compile / edit midi
* compile exercise before it's started
* midi mixer settings
* solfege tab
* click in for songs
