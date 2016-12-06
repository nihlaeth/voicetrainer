\include "color-pitch.ly"
\include "articulate.ly"
\version "2.19.50"
% voicetrainer: tempo = 84
% voicetrainer: measures = 6
\header {
  title = "Test song"
}

global= {
  \tempo 4=${tempo} \time 4/4
}

exercise = {
  \override NoteHead #'color = #color-notehead
  \transpose c ${pitch} \relative c' {
    \key c \major
    < c e g >2\sustainOn
    \repeat unfold 2 {
      \breathe c4->( d e f
      g2)
    }
    \breathe c,4->( d e f
    g f e d
    c2 \sustainOff ) \bar "||" \break
  }
}

${sheeton}
\book {
  \score {
    <<
      \new ChordNames { \chordmode { ${pitch_noheight} }}
      \new Staff = "voice" <<
        \global
        \exercise
        \addlyrics {

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
}
${sheetoff}
${midion}
\book {
  \score {
    \unfoldRepeats \articulate <<
      \new Staff = "voice" <<
        \set Staff.midiInstrument = "acoustic grand"
        \global
        \exercise
      >>
    >>
    \midi {
    }
  }
}
${midioff}
