"""Study material generated from a whole document: flashcards and slide decks.

Like quizzes, both sample chunks across the document (`quiz.sampling`), let the
model write from numbered blocks, and bind every item to the block it cites in
code. An item citing a block that was never provided is dropped, because every
card and every slide must point back at the lecture it came from.
"""
