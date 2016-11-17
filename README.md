# voicetrainer
MIDI voice exercises made convenient

## About
I'm a singer and I have a disability that prevents me from using a keyboard (musical or otherwise). Since speech recognition and making music are a really bad combination, I could pretty much only do voice exercises during my singing lessons, which frustrated me to no end.

So I started thinking about a solution. What I want from this is an exercise that I can easily change into a different tempo or key. It should be trivial to pause, repeat, or change the paramaters. Everything has to be operable by mouse alone. And it should be quality MIDI, because I can't stand the sinus tone that most MIDI sequencers emit. Also, I want sheet music. Beautiful sheet music, preferably with lots of notes (the textual kind). And it shouldn't be hard to add new exercises, or at least not a lot of dictation work.

It says something about me that I'd rather dictate code one letter at a time for four days straight than click pause and play a few times in a big MIDI file, but here it is, so you won't have to repeat the feat. Enjoy, and feel free to make pull requests with your own exercises.

## Exercise definitions
Exercises are defined in the exercises folder, and exist of two LilyPond files each ([name].ly and [name]-midi.ly). As you can probably guess, the first one is used to generate the sheet, and the second one to generate the MIDI. They are both written and LilyPond, though with a little customization of my own. Namely, they accept variables to make it easy to change the exercise without having to write 200 exercise definitions for all the possibilities.

The parameters are:
* ${pitch} - pitch with octave attached (ex: c', usage: \transpose c ${pitch} { c e g | }): both midi and png
* ${pitch_noheight} - just the pitch, for use in chordmode (ex: c, usage: \chordmode { ${pitch_noheight}:m }): only png
* ${sound} - vocal, for use in lyricsmode (ex: Mi, usage: \lyricsmode { ${sound} }): only png
* ${tempo} - bpm, for midi tempo (ex: 140, usage: \tempo ${temp}=4): only midi

These parameters are not optional, though you might ignore a few by placing them in a hidden part of the sheet.

## Dependencies
* python3.5 (no third party modules required)
* tk/tcl 8.6
* lilypond (I used the dev version)
* pmidi
* fluidsynth (qsynth recommended)
* color-pitch.ly (https://github.com/nihlaeth/sheetmusic/blob/master/color-pitch.ly)

## Installation
pip install .

## Usage
Make sure fluidsynth is running, then start by executing: voicetrainer

## Problems
None known at this time

## Planned features
