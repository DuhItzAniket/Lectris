# The rules

Every text rule, what it changes, the evidence it needs, and what it deliberately leaves alone.
Each rule records each edit under its id, so a report says which rule made which change.
`lectris rules` lists the rules each profile runs, in order; the order is explained in
`lectris/profiles.py`.

A rule sees one block (a paragraph): its lines joined by `\n`. Examples show Python string
literals.

## Normalisation

### `whitespace.line_breaks` — conservative, standard, aggressive
Makes every line break `\n`: `\r\n`, a lone `\r`, and the Unicode line separator (U+2028). The
paragraph separator (U+2029) becomes a paragraph break, `\n\n`.
Left alone: U+0085, which usually comes from text decoded with the wrong encoding, form feeds and
vertical tabs.

### `unicode.invisible` — conservative, standard, aggressive
Removes invisible characters that OCR and PDF text layers leave inside words: zero width space,
word joiner, byte order mark, and soft hyphens inside a line. Zero width (non-)joiners are
removed between Latin letters.
A soft hyphen at a line end, with text on the next line, marks a hyphenation point: it is kept for
`hyphenation.join`, which always rejoins the word there.
Left alone: joiners next to non-Latin letters or emoji (Persian, Indic and emoji sequences need
them), and bidirectional controls.
Example: `"co\u200boperate"` → `"cooperate"`.

### `unicode.ligatures` — conservative, standard, aggressive
Replaces the Latin typographic ligatures U+FB00 to U+FB06 by their letters.
Left alone: `æ`, `œ`, `Æ`, `Œ`, `ĳ` and `Ĳ`, which are letters in the languages that use them.
Example: `"ﬁne"` → `"fine"`.

### `unicode.compatibility` — conservative, standard, aggressive
Replaces fullwidth ASCII forms (U+FF01 to U+FF5E) and Unicode spaces (no-break, thin, ideographic
and the other space separators) by their ASCII equivalents.
It is not full NFKC: superscripts, fractions, `ª`, `™` and the ellipsis keep their meaning and
are left alone.
Example: `"10\u00a0km"` → `"10 km"`.

### `unicode.nfc` — conservative, standard, aggressive
Normalises to Unicode NFC, with one edit per character sequence that changes.
Example: `"cafe\u0301"` → `"café"`.

### `whitespace.collapse` — conservative, standard, aggressive
Replaces each run of two or more spaces or tabs between two words by one space.
Left alone: a single tab, which may separate table columns, and line breaks.
Example: `"a  b"` → `"a b"`.

### `whitespace.trim` — conservative, standard, aggressive
Removes spaces and tabs at the start and end of each line, and blank lines at the start and end of
the block.

## Lines

### `noise.drop_lines` — standard, aggressive
Deletes lines that are OCR noise rather than text (scanner specks, ruled lines, pictures read as
characters), judged by `lectris.quality.score`: the shares of symbols, lone lowercase letters and
marks, and thin glyphs; runs of a repeated letter; vowels and case switches. Only a line of
symbols or a run of repeated letters is noise on its own evidence. The scores and their
thresholds are documented in `lectris/quality.py`.
Left alone: a section break of three or more asterisks (`* * *`), short lines of real text
(`Chapter 3`, `Table 2.`, `- 12 -`), formulas (`V = I R`, `x = y + z`), abbreviations
(`R & D`), table rows (`| a | b |`), rows of capitals (`A B C D`), interjections (`Mmmm`,
`Ahhhh`), numbers and amounts, and dot leaders in tables of contents.
Example: `"Text.\n~~~ ,,, ' ' |||\nMore."` → `"Text.\nMore."`.

### `hyphenation.join` — conservative, standard, aggressive
Joins a word hyphenated across a line break and moves the break after the word, so the block
keeps its number of lines. The line-end mark may be `-`, a soft hyphen, `‐`, `‑`, or the `¬` and
`⸗` some engines and Fraktur use; it is dropped from the joined word.
Evidence: a soft hyphen at the line end always joins. Otherwise the next line must start with a
lowercase letter, and then:
- with a lexicon, the joined word must be known and the hyphenated form not (or be the more
  frequent of the two); both parts being words and the joined form not keeps the hyphen;
- without a lexicon, the first part must have at least two letters and neither part a capital
  letter inside it.

Left alone: a suspended hyphen before a conjunction (`pre-\nand post-war`, `Ein-\nund Ausgang`),
a compound whose next part has its own hyphen (`mother-\nin-law`, `c'est-\nà-dire`), a French
clitic (`fait-\nil`, `peut-\nêtre`, `qu'est-\nce`), `Franco-\nGerman`, `NATO-\nled`,
`e-\nmail`, `state-of-the-\nart`, fragments with digits, and anything across a blank line. A
lexicon that knows the joined word overrides the conjunction and clitic lists.
Limits: without a lexicon, a compound broken at its own hyphen (`long-\nterm`) is joined, and a
word whose last syllable is a clitic (`ner-\nvous`) is not. Pass a lexicon for text with many
compounds.
Example: `"the infor-\nmation is here"` → `"the information\nis here"`.

### `unwrap.join_lines` — standard, aggressive
Joins a paragraph's lines into one line: each line break and the spaces around it become one
space. A hyphen or dash left at a line end after de-hyphenation belongs to a compound, so the
next line follows it without a space (`self-\naware` → `self-aware`), except before a
conjunction (`pre- and post-war`); a `¬` or `⸗` left there is written as `-`. In the pipeline,
de-hyphenation has already joined the split words, so the hyphens this rule sees are the ones it
kept.
Left alone: the break before a list item (`- `, `• `, `1. `, `a) `, `(iv) `), the breaks around a
section break (`* * *`), and the breaks next to blank lines.
Example: `"first line\nsecond line"` → `"first line second line"`.

## Characters

### `confusables.in_numbers` — standard, aggressive
Turns letters that look like digits into digits inside a number: `O`/`o` → `0`, `l`/`I` → `1`.
Evidence: the token starts with a real digit, or with an `O` read for the zero before a decimal
separator (`O.5` → `0.5`); it ends with a digit or `O`; and it has at least two real digits, or
one after a leading `O.`. All letters of the token change, or none.
Left alone: `S` and `B`, which codes use (`12B34`, `10S20`); `l23`, `A4`, `10B`, `1980S`,
`COVID-19`, `O5`, `O.K.`, hexadecimal, and `|`, which may be a table rule.
Example: `"1O5 species"` → `"105 species"`.

### `numbers.separators` — standard, aggressive
Removes the space OCR puts before a decimal point or a thousands separator.
Evidence: a `.` with a space before it and none after; a `,` with a space before it and none
after, when every comma of the number is followed by exactly three digits.
Left alone: a separator with spaces on both sides, which may end a sentence (`aged 92 . 3
children`, `page 12 , 300 words`); lists (`1, 2, 3`), dates (`2024 . 10`), times (`10 : 30`),
and a separator with a space only after it (`3. 14`).
Example: `"3 .5 percent"` → `"3.5 percent"`.

### `confusables.in_words` — aggressive
Turns digits that look like letters into letters inside a word of at least three letters.
Evidence: without a lexicon, only a `0` between two letters, one of them lowercase, becomes `o`
(`McD0nald` → `McDonald`); a `1` could be an `i` or an `l`, so it is left. With a lexicon, `0`,
`1`, `5` and `8` may become the letters they look like when the result is a known word and the
original is not (`s1mple` → `simple`).
Left alone: `mp3`, `h264`, `4th`, `1st`, `2D`, `B2B`, `x86`.
Example: `"w0rd"` → `"word"`.

### `punctuation.dashes` — standard, aggressive
Replaces the hyphen variants U+2010 and U+2011 by `-`, and the figure dash U+2012 between digits.
Left alone: en and em dashes, the minus sign and `--`, which carry meaning.

### `punctuation.quotes` — aggressive (straight)
Makes quotation marks straight (`'` and `"`), or curly with `style="curly"`, where the context
decides between opening and closing marks and apostrophes.
Left alone: guillemets, the modifier letter apostrophe, and in the curly style a quote after a
digit (`5'10"` are primes).

### `punctuation.ellipsis` — aggressive (three dots)
Writes each ellipsis as three dots, or as `…` with `style="character"`; a spaced `. . .` becomes
the chosen form.
Left alone: runs of two dots, and four or more (leaders).

### `punctuation.spacing` — standard, aggressive
Removes the space OCR puts before `,` `.` `)` `]` `}` and after `(` `[` `{`, when the mark ends a
word or the bracket starts one. With `high_punctuation=True` it also removes the space before
`;` `:` `!` `?`; the default keeps it, because French typography puts one there.
Left alone: numbers and times (`3 . 14`, `10 : 30`), ellipses, `.gitignore`, `f( x )`, and line
breaks.
Example: `"species , most"` → `"species, most"`.
