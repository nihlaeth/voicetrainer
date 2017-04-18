# Sheet music
Sheet music for voicetrainer written in the lilypond format, and should be placed in files ending with `.ly` extension in the `~/.voicetrainer/exercises` and `~/.voicetrainer/songs` directories.

This can be plain lilypond code, but if you want any of the awesome features that voicetrainer offers, like transposing your music with one click of a button, changing the tempo, generating sheet music and midi with different rules, selecting instruments to include and exclude from your sheet music and midi and adjusting relative velocities for your instruments, you need to include some special syntax in your lilypond sheet.

## Transposition and tempo
key and tempo changes work by variable. you define a specially named variable, that you use in all the relevant places, and voice trainer changes it to the user-specified value.

```ly
voicetrainerTempo = 72
voicetrainerKey = b

global= {
  \tempo 4=\voicetrainerTempo \time 4/4 \key b \minor
}

voiceStaff= \transpose b \voicetrainerKey \relative c' {
  \global
}
```

The values of these variables are seen as the default for this composition.

You should take care to wrap every music expression in a transpose instruction like above.

## Different output rules for sheet music and midi
With specially formatted comments, you can specify sections which will be excluded when formatting sheet music or midi.

This example prevents the selected tempo from showing up in the sheet music.

```ly
% sheetonly start
global= {
  \time 4/4
}
% sheetonly end
% midionly start
global= {
  \tempo 4=\voicetrainerTempo \time 4/4
}
% midionly end
```

You can have as many exclusion blocks as you want, and there are no rules to prevent nesting, or mixing, though I would advise against it.

I would advise maintaining separate books for sheet and MIDI output, like the example below. You cannot maintain two different books with voicetrainer without using the exclusion blocks, or the resulting filenames won't match what voicetrainer expects.

```ly
% sheetonly start
\book {
  \score {
    <<
      \new ChordNames { \chordmode { \transpose c \voicetrainerKey { c }}}
      \new Staff = "voice" <<
        \global
        \exercise
        \addlyrics {
          \skip 1 Mi Na Nu Noe No
        }
      >>
    >>
    \layout {
      \context {
        \Staff \RemoveEmptyStaves
        \override VerticalAxisGroup #'remove-first = ##t
      }
    }
  }
  \paper{
    #(set-paper-size "a5landscape")
    indent=0\mm
    line-width=190\mm
    oddFooterMarkup=##f
    oddHeaderMarkup=##f
    bookTitleMarkup = ##f
    scoreTitleMarkup = ##f
  }
}
% sheetonly end
% midionly start
\book {
  \score {
    \unfoldRepeats \articulate <<
      \new Staff = "voice" <<
        \set Staff.midiInstrument = "acoustic grand"
        \global
        \exercise
      >>
    >>
    \midi { }
  }
}
% midionly end
```

## Songs
This syntax is exclusive to songs.

### Metadata
There is some information that we can't easily extract from the code. In order to jump to a measure, we need to know how many measures are in your sheet. Likewise it is useful to know what the number of pages in your sheet is, although this is not critical for the allover functioning of voicetrainer (just for the functioning of the last page button).

You do this by adding a comment. This format will likely change in future.

```ly
% voicetrainer: measures = 61
% voicetrainer: pages = 5
```

It is important that you give this comment its own line, in-line comments will not work.

### Instrument selection
You can change the instrument selection in sheet music and midi with voicetrainer. For this to work you need to tell voicetrainer where individual instruments start and stop. This works exactly like the exclusion blocks.

```ly
% sheetonly start
\book {
  \score {
    <<
      \new ChordNames { \myChords }
      \new FretBoards { \myChords }
      % instrument start voice
      \new Staff = "voice" <<
        \set Staff.instrumentName = \markup { "Voice" }
        \set Staff.shortInstrumentName = \markup { "V." }
        \voiceStaff
        \addlyrics {
        }
      >>
      % instrument end voice
      % instrument start cello
      \new Staff = "cello" <<
        \set Staff.instrumentName = \markup { "ViolonCello" }
        \set Staff.shortInstrumentName = \markup { "C." }
        \cello
      >>
      % instrument end cello
      % instrument start piano
      \new PianoStaff = "piano" <<
        \new Staff {
          \set Staff.midiInstrument = "acoustic grand"
          \removeWithTag midi \upperStaff
        }
        \new Dynamics \pianoDynamics
        \new Staff {
          \set Staff.midiInstrument = "acoustic grand"
          \removeWithTag midi \lowerStaff
        }
        \new Dynamics \pianoPedal
      >>
      % instrument end piano
    >>
    \layout {
      \context {
        \Staff \RemoveEmptyStaves
        \override VerticalAxisGroup #'remove-first = ##t
      }
      \context {
        \PianoStaff
        \accepts Dynamics
      }
    }
  }
}
% sheetonly end
% midionly start
\book {
  \score {
    \unfoldRepeats \articulate <<
      % instrument start voice
      \new Staff = "voice" <<
        \set Staff.instrumentName = \markup { "Voice" }
        \set Staff.shortInstrumentName = \markup { "V." }
        \set Staff.midiInstrument = "choir aahs"
        \voiceStaff
      >>
      % instrument end voice
      % instrument start cello
      \new Staff = "cello" <<
        \set Staff.instrumentName = \markup { "ViolonCello" }
        \set Staff.shortInstrumentName = \markup { "C." }
        \set Staff.midiInstrument = "cello"
        \cello
      >>
      % instrument end cello
      % instrument start piano
      \new PianoStaff = "piano" <<
        \new Staff = "piano:1" {
          \set Staff.midiInstrument = "acoustic grand"
          \new Voice <<
            \new Dynamics \pianoDynamics
            \upperStaff
            \new Dynamics \pianoPedal
          >>
        }
        \new Staff = "piano:2" {
          \set Staff.midiInstrument = "acoustic grand"
          \new Voice <<
            \new Dynamics \pianoDynamics
            \lowerStaff
            \new Dynamics \pianoPedal
          >>
        }
      >>
      % instrument end piano
      % instrument start metronome
      \new DrumStaff = "metronome" {
        \drummode {
          \global
          \repeat unfold 61 {
            hiwoodblock4 lowoodblock wbl wbl
          }
        }
      }
      % instrument end metronome
    >>
    \midi {
      \context {
        \type "Performer_group"
        \name Dynamics
        \consists "Dynamic_performer"
        \consists "Piano_pedal_performer"
      }
      \context {
        \Voice
        \accepts Dynamics
      }
    }
  }
}
% midionly end
```

You can see several neat tricks in the example above, like a metronome tracks that only shows up in midi. And a separate dynamics track for piano so they can be shared between staffs, and only show up once in the sheet music (but still work with MIDI). For that to work you need to mark dynamics in temporary polyphonic sections with a midi tag.

### Relative velocity
First thing to note is that velocity in midi has nothing to do with tempo, but rather the dynamics (whether a note is played in piano or fortissimo, etc.). You should set dynamics in the sheet music like you always would.

Voicetrainer allows you to change the relative velocity of the entire song (also exercises) without any special syntax. But it also allows you to tune the balance between different instruments, and for this it needs you to name your staffs, so it can match MIDI tracks to the instruments you specified in your sheet music.

For this you need to limit your instrument names to only contain the following characters: a-z, A-Z, 0-9, -, _

If an instrument consists of more than one staff (for example a piano, or if you ordered an orchestra section into a single instrument), you should add a postfix of a colon and a number after the instrument name, like this: `piano:1`.

If this feature is not working like you expect, or you're getting errors about not finding named traks for your instruments, it might be time to inspect your midi. We provided command line tool for this purpose.

```
$ midi_introspection my_midi_file.midi | less
```

Look for `SEQUENCE_TRACK_NAME` events. Don't worry about the semicolon that lilypond adds to the staff name, voicetrainer compensates for that.

It's possible to configure lily ponds to create a MIDI track per voice instead of per staff. I assume that naming a voice will also result in a `SEQUENCE_TRACK_NAME` event, but this behaviour is untested.

Note: lilypond adding a `SEQUENCE_TRACK_NAME` event to MIDI with the staff name is undocumented behaviour and thus subject to change in the future. It might also not be backwards compatible. I simply don't know. It works with version 2.19 and probably with 2.18. No guarantees.

## Exercises
This syntax is exclusive to exercises.

### Sound selection
I do my voice exercises with different vocals so I made it so you can select them in the user interface as well. This feature needs a lot of work, as it isn't customisable at all right now, but if you'd like to use the standard vocals, add the following to your sheet music.

```ly
voicetrainerSound = "Mi"

...
\addlyrics {
  \skip 1 \voicetrainerSound \voicetrainerSound \voicetrainerSound
}
...
```
