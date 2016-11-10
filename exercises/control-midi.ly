\include "articulate.ly"
\version "2.19.50"

\header {
}

global= {
  \tempo 4=${tempo} \time 4/4
}

exercise = {
  \transpose c ${pitch} \relative c' {
    \key c \major
    < c e g >2\sustainOn
    \repeat unfold 2 {
      c4->( d e f
      g2)
    }
    c,4->( d e f
    g f e d
    c2 \sustainOff ) \bar "||" \break
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

