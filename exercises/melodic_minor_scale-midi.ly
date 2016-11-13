\include "articulate.ly"
\version "2.19.50"

\header {
}

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
