# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
import logging

from plainbox.vendor.enum import Enum, unique


__all__ = ['WordScanner']

_logger = logging.getLogger("plainbox.xscanners")


class ScannerBase:

    def __init__(self, text):
        self._text = text
        self._text_len = len(text)
        self._pos = 0

    def __iter__(self):
        return self

    def __next__(self):
        token, lexeme = self.get_token()
        if token is self.TOKEN_EOF:
            raise StopIteration
        return token, lexeme

    def get_token(self):
        """
        Get the next pair (token, lexeme)
        """
        _logger.debug("inner: get_token()")
        state = self.STATE_START
        lexeme = ""
        stack = [self.STATE_BAD]
        while state is not self.STATE_ERROR:
            _logger.debug("inner: ------ (next loop)")
            _logger.debug("inner: text:   %r", self._text)
            _logger.debug("                %s^ (pos: %d of %d)",
                          '-' * self._pos, self._pos, self._text_len)
            char = self._next_char()
            _logger.debug("inner: char:   %r", char)
            _logger.debug("inner: state:  %s", state)
            _logger.debug("inner: stack:  %s", stack)
            _logger.debug("inner: lexeme: %r", lexeme)
            lexeme += char
            if state.is_accepting:
                stack[:] = ()
                _logger.debug("inner: rollback stack cleared")
            stack.append(state)
            state = self._next_state_for(state, char)
            _logger.debug("inner: state becomes %s", state)
        if state is self.STATE_ERROR:
            _logger.debug("inner/rollback: REACHED ERROR STATE, ROLLING BACK")
            while (not state.is_accepting and state is not self.STATE_BAD):
                state = stack.pop()
                _logger.debug("inner/rollback: popped new state %s", state)
                lexeme = lexeme[:-1]
                _logger.debug("inner/rollback: lexeme trimmed to: %r", lexeme)
                self._rollback()
            _logger.debug("inner/rollback: DONE")
        lexeme = lexeme.rstrip("\0")
        lexeme = state.modify_lexeme(lexeme)
        if state.is_accepting:
            _logger.debug(
                "inner: accepting/returning: %r, %r", state.token, lexeme)
            return state.token, lexeme
        else:
            _logger.debug("inner: not accepting: %r", state)
            return state.token, None

    def _rollback(self):
        if self._pos > 0:
            self._pos -= 1
        else:
            assert False, "rolling back before start of input?"

    def _next_char(self):
        assert self._pos >= 0
        if self._pos < self._text_len:
            char = self._text[self._pos]
            self._pos += 1
            return char
        else:
            # NOTE: this solves a lot of problems
            self._pos = self._text_len + 1
            return '\0'

    def _next_state_for(self, state, char):
        raise NotImplementedError


@unique
class WordScannerToken(Enum):
    """ Token kind produced by :class:`WordScanner` """
    INVALID = -1
    EOF = 0
    WORD = 1
    SPACE = 2
    COMMENT = 3
    COMMA = 4
    EQUALS = 5

    @property
    def is_irrelevant(self):
        return self in (WordScannerToken.SPACE, WordScannerToken.COMMENT)


@unique
class WordScannerState(Enum):
    """ State of the :class:`WordScanner` """
    BAD = -1  # the bad state, used only once as a canary
    START = 0  # the initial state
    EOF = 1  # state for end-of-input
    ERROR = 2  # state for all kinds of bad input
    BARE_WORD = 3  # state when we're seeing bare words
    QUOTED_WORD_INNER = 4  # state when we're seeing "-quoted word
    QUOTED_WORD_END = 5
    SPACE = 6  # state when we're seeing spaces
    COMMENT_INNER = 7  # state when we're seeing comments
    COMMENT_END = 8  # state when we've seen \n or ''
    COMMA = 9  # state where we saw a comma
    EQUALS = 10  # state where we saw the equals sign

    @property
    def is_accepting(self):
        return self in WordScannerState._ACCEPTING

    def modify_lexeme(self, lexeme):
        """ Get the value of a given lexeme """
        if self is WordScannerState.QUOTED_WORD_END:
            return lexeme[1:-1]
        else:
            return lexeme

    @property
    def token(self):
        """ Get the token corresponding to this state """
        return WordScannerState._TOKEN_MAP.get(self, WordScannerToken.INVALID)

# Inject some helper attributes into WordScannerState
WordScannerState._ACCEPTING = frozenset([
    WordScannerState.EOF, WordScannerState.BARE_WORD,
    WordScannerState.QUOTED_WORD_END, WordScannerState.SPACE,
    WordScannerState.COMMENT_END, WordScannerState.COMMA,
    WordScannerState.EQUALS
])
WordScannerState._TOKEN_MAP = {
    WordScannerState.EOF: WordScannerToken.EOF,
    WordScannerState.BARE_WORD: WordScannerToken.WORD,
    WordScannerState.QUOTED_WORD_END: WordScannerToken.WORD,
    WordScannerState.SPACE: WordScannerToken.SPACE,
    WordScannerState.COMMENT_END: WordScannerToken.COMMENT,
    WordScannerState.COMMA: WordScannerToken.COMMA,
    WordScannerState.EQUALS: WordScannerToken.EQUALS,
}


class WordScanner(ScannerBase):
    """
    Support class for tokenizing a stream of words with shell comments.

    A word is anything that's not whitespace (of any kind). Since everything
    other than whitespace is a word, there is no way to break the scanner and
    end up in an error state. Comments are introduced with the ``#`` character
    and run to the end of the line.

    Iterating over the scanner will produce subsequent pairs of (token, lexeme)
    where the kind is one of the constants from :class:`WordScannerToken` and
    lexeme is the actual text (value) of the token

        >>> for token, lexeme in WordScanner('ala ma kota'):
        ...     print(lexeme)
        ala
        ma
        kota

    Empty input produces an EOF token:

        >>> WordScanner('').get_token()
        (<WordScannerToken.EOF: 0>, '')

    Words with white space can be quoted using double quotes:

        >>> WordScanner('"quoted word"').get_token()
        (<WordScannerToken.WORD: 1>, 'quoted word')

    White space is ignored and is not returned in any way (normally):

        >>> WordScanner('\\n\\t\\v\\rword').get_token()
        (<WordScannerToken.WORD: 1>, 'word')

    Though if you *really* want to, you can see everything by passing the
    ``ignore_irrelevant=False`` argument to :meth:`get_token()`:

        >>> scanner = WordScanner('\\n\\t\\v\\rword')
        >>> while True:
        ...     token, lexeme = scanner.get_token(ignore_irrelevant=False)
        ...     print('{:6} {!a}'.format(token.name, lexeme))
        ...     if token == scanner.TOKEN_EOF:
        ...         break
        SPACE  '\\n\\t\\x0b\\r'
        WORD   'word'
        EOF    ''

    The scanner has special provisions for recognizing some punctuation, this
    includes the comma and the equals sign as shown below:

        >>> for token, lexeme in WordScanner("k1=v1, k2=v2"):
        ...     print('{:6} {!a}'.format(token.name, lexeme))
        WORD   'k1'
        EQUALS '='
        WORD   'v1'
        COMMA  ','
        WORD   'k2'
        EQUALS '='
        WORD   'v2'

    Since both can appear in regular expressions, they can be quoted to prevent
    being recognized for their special meaning:

        >>> for token, lexeme in WordScanner('k1="v1, k2=v2"'):
        ...     print('{:6} {!a}'.format(token.name, lexeme))
        WORD   'k1'
        EQUALS '='
        WORD   'v1, k2=v2'

    """
    STATE_ERROR = WordScannerState.ERROR
    STATE_START = WordScannerState.START
    STATE_BAD = WordScannerState.BAD
    TOKEN_EOF = WordScannerToken.EOF

    TokenEnum = WordScannerToken

    def get_token(self, ignore_irrelevant=True):
        while True:
            token, lexeme = super().get_token()
            _logger.debug("outer: GOT %r %r", token, lexeme)
            if ignore_irrelevant and token.is_irrelevant:
                _logger.debug("outer: CONTINUING (irrelevant token found)")
                continue
            break
        return token, lexeme

    def _next_state_for(self, state, char):
        if state is WordScannerState.START:
            if char.isspace():
                return WordScannerState.SPACE
            elif char == '\0':
                return WordScannerState.EOF
            elif char == '#':
                return WordScannerState.COMMENT_INNER
            elif char == '"':
                return WordScannerState.QUOTED_WORD_INNER
            elif char == ',':
                return WordScannerState.COMMA
            elif char == '=':
                return WordScannerState.EQUALS
            else:
                return WordScannerState.BARE_WORD
        elif state is WordScannerState.SPACE:
            if char.isspace():
                return WordScannerState.SPACE
        elif state is WordScannerState.BARE_WORD:
            if char.isspace() or char in '\0#,=':
                return WordScannerState.ERROR
            else:
                return WordScannerState.BARE_WORD
        elif state is WordScannerState.COMMENT_INNER:
            if char == '\n' or char == '\0':
                return WordScannerState.COMMENT_END
            else:
                return WordScannerState.COMMENT_INNER
        elif state is WordScannerState.QUOTED_WORD_INNER:
            if char == '"':
                return WordScannerState.QUOTED_WORD_END
            if char == '\x00':
                return WordScannerState.ERROR
            else:
                return WordScannerState.QUOTED_WORD_INNER
            if char.isspace() or char == '\0' or char == '#':
                return WordScannerState.ERROR
            else:
                return WordScannerState.WORD
        elif state is WordScannerState.QUOTED_WORD_END:
            pass
        elif state is WordScannerState.COMMENT_END:
            pass
        elif state is WordScannerState.COMMA:
            pass
        elif state is WordScannerState.EQUALS:
            pass
        return WordScannerState.ERROR
