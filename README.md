# voicetrainer
MIDI voice exercises made convenient

## About
I'm a singer and I have a disability that prevents me from using a keyboard (musical or otherwise). Since speech recognition and making music are a really bad combination, I could pretty much only do voice exercises during my singing lessons, which frustrated me to no end.

So I started thinking about a solution. What I want from this is an exercise that I can easily change into a different tempo or key. It should be trivial to pause, repeat, or change the parameters. Everything has to be operable by mouse alone. And it should be quality MIDI, because I can't stand the sinus tone that most MIDI sequencers emit. Also, I want sheet music. Beautiful sheet music, preferably with lots of notes (the textual kind). And it shouldn't be hard to add new exercises, or at least not a lot of dictation work.

It says something about me that I'd rather dictate code one letter at a time for four days straight than click pause and play a few times in a big MIDI file, but here it is, so you won't have to repeat the feat. Enjoy, and feel free to make pull requests with your own exercises.

## Exercise definitions
Exercises are defined in the voicetrainer/exercises folder. They are written in LilyPond, though with a little customization of my own. Namely, they accept variables to make it easy to change the exercise without having to write 200 exercise definitions for all the possibilities.

The parameters are:
* ${pitch} - pitch with octave attached (ex: c', usage: \transpose c ${pitch} { c e g | })
* ${pitch_noheight} - just the pitch, for use in chordmode (ex: c, usage: \chordmode { ${pitch_noheight}:m })
* ${sound} - vocal, for use in lyricsmode (ex: Mi, usage: \lyricsmode { ${sound} })
* ${tempo} - bpm, for midi tempo (ex: 140, usage: \tempo ${temp}=4)

Then there's the sheeton, sheetoff, midion and midioff variables which are used to differentiate between midi and visual output. See existing exercises for examples.

These parameters are not optional, though you might ignore a few by placing them in a comment.

## Dependencies
* python3.5
* music21
* pillow
* tk/tcl 8.6
* lilypond (I used the dev version)
* pmidi
* fluidsynth (qsynth recommended)

## Installation
```
pip install .
```

## Usage
Make sure fluidsynth is running, then start by executing:
```
voicetrainer
```

## Todo
* tweak pmidi settings (shorter sleep after midi end)
* add buttons for switching pages
* increment page on click
* switch page by scrolling

## Problems
* it's possible to play 2 midi streams at the same time with the right timing

## Planned features
* select dynamics
* allow selecting different midi synthesizers
* user-specific settings and exercises
* compile exercise before it's started
