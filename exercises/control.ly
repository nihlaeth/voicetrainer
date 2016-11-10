\include "color-pitch.ly"
\version "2.19.50"

\header {
}

global= {
  \time 4/4
}

exercise = {
  \override NoteHead #'color = #color-notehead
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
    <<
      \new ChordNames { \chordmode { ${pitch_noheight}:m }}
      \new Staff = "voice" <<
        \global
        \exercise
        \addlyrics {
          \skip 1 ${sound} ${sound} ${sound}

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
