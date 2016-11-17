\include "color-pitch.ly"
\include "articulate.ly"
\version "2.19.50"

\header {
}
${sheeton}
global= {
  \time 4/4
}

exercise = {
  \override NoteHead #'color = #color-notehead
  \transpose c ${pitch} \relative c' {
    \key c \minor
    < c es g >1\sustainOn |
    c4( d es f g a b c
    bes as g f es d c)
    \bar "|."
  }
}

\book {
  \score {
    <<
      \new ChordNames { \chordmode { ${pitch_noheight}:m }}
      \new Staff = "voice" <<
        \global
        \exercise
        \addlyrics {
          \skip 1 ${sound} 

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
${sheetoff}
${midion}
global= {
  \tempo 4=${tempo} \time 4/4
}

exercise = {
  \transpose c ${pitch} \relative c' {
    \key c \minor
    < c es g >1\sustainOn |
    c4( d es f g a b c
    bes as g f es d c)
    \bar "|."
  }
}

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
