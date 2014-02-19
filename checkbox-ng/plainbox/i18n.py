# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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

"""
:mod:`plainbox.i18n` -- i18n support
====================================

This module provides public APIs for plainbox translation system. Currently
all functions exported here are STUB and offer no translations. In addition,
functions defined in this module are assumed to implicitly use the gettext
domain ``"plainbox"``.
"""

import codecs
import collections
import gettext as gettext_module
import os
import random
import re


class Rot13Translator:

    rot13 = codecs.getencoder("rot-13")

    @classmethod
    def gettext(cls, msgid):
        return cls.rot13(msgid)[0]

    @classmethod
    def dgettext(cls, domain, msgid):
        return cls.rot13(msgid)[0]

    @classmethod
    def ngettext(cls, msgid1, msgid2, n):
        if n == 1:
            return cls.rot13(msgid1)[0]
        else:
            return cls.rot13(msgid2)[0]


class NoOpTranslator:

    @classmethod
    def gettext(cls, msgid):
        return msgid

    @classmethod
    def dgettext(cls, domian, msgid):
        return msgid

    @classmethod
    def ngettext(cls, msgid1, msgid2, n):
        if n == 1:
            return msgid1
        else:
            return msgid2


class LoremIpsumTranslator:

    LOREM_IPSUM = {
        "ch": ('', """小經 施消 了稱 能文 安種 之用 無心 友市 景內 語格。坡對
               轉醫 題苦 們會員！ 我親就 藝了參 間通。 有發 轉前 藥想
               亞沒，通須 應管、打者 小成 公出？ 般記 中成化 他四華 分國越
               分位離，更為者 文難 我如 我布？經動 著為 安經， 們天然 我親 唱顯
               不；得當 出一來得金 著作 到到 操弟 人望！去指 在格據！"""),
        "kr": (' ' """말을 하고 곁에서 일 말려가고 그걸로 하다 같은 없네
               앉은 뿌리치더니 동소문 일 보지 재우쳤다 분량 말을 가지고
               김첨지의 시작하였다 내리는 나를 김첨지는 좁쌀 준 반가운지
               김첨지는 놓치겠구먼 늦추잡았다 인력거 속 생각하게 돈을 시체를
               한 정거장까지 느끼었다 귀에 넘어 왜목 것을 싶어 설레는 맞붙들고
               하네 오늘 배가 하늘은 하자마자 맞물고 일이었다 운수가 못쓸
               돈의 라고 어이 없지만 받아야 아내의 시작하였다 차도 왜
               사용자로부터 추어탕을 처음 보라 출판사 차원 따라서 펴서 풀이
               사람은 근심과 초조해온다 트고 제 창을 내리었다 인력거하고
               같으면 큰 이놈아 어린애 그 넘어 울었다V"""),
        "he": (' ', """תורת קרימינולוגיה אל אתה הטבע לחיבור אם אחר מדע חינוך
               ממונרכיה גם פנאי אחרים המקובל את אתה תנך אחרים לטיפול של את
               תיאטרון ואלקטרוניקה מתן דת והנדסה שימושיים סדר בה סרבול
               אינטרנט שתי ב אנא תוכל לערך רוסית כדי את תוכל כניסה המלחמה
               עוד מה מיזמי אודות ומהימנה"""),
        "ar": (' ', """ دار أن منتصف أوراقهم الرئيسية هو الا الحرب الجبهة لان
               مع تنفّس للصين لإنعدام نتيجة الثقيلة أي شيء عقبت وأزيز لألمانيا
               وفي كل حدى إختار المنتصرة أي به، بغزو بالسيطرة أن  جدول
               بالفشل إيطاليا قام كل هنا؟ فرنسا الهجوم هذه مع حقول
               الإمبراطورية لها أي قدما اليابانية عام مع جنود أراضي السوفييتي،
               هو بلا لم وجهان الساحة الإمبراطورية لان ما بحق ألمانيا الياباني،
               فعل فاتّبع الشّعبين المعركة، ما  الى ما يطول المشتّتون وكسبت
               وإيطالي ذات أم تلك ثم القصف قبضتهم قد وأزيز إستمات ونستون غزو
               الأرض الأولية عن بين بـ دفّة كانت النفط لمّ تلك فهرست الأرض
               الإتفاقية مع"""),
        "ru": (' ', """Магна азжюывырит мэль ут нам ыт видырэр такематыш кибо
               ыррор ут квюо Вяш аппарэат пондэрюм интылльэгэбат эи про ед
               еллум дикунт Квюо экз льаборэж нужквюам анкилльаы мэль омйттам
               мэнандря ед Мэль эи рэктэквуэ консэквюат контынтёонэж ты ёужто
               фэугяат вивэндюм шэа Атквюе трётанё эю квуй омнеж латины экз
               вимi"""),
        "jp": ('', """戸ぶだ の意 化巡奇 供 クソリヤ 無断 ヨサリヲ 念休ばイ
               例会 コトヤ 耕智う ばっゃ 佐告決う で打表 ぞ ぼび情記ト レ表関銀
               ロモア ニ次川 よ全子 コロフ ソ政象 住岳ぴ 読ワ 一針 ヘ断
               首画リ のぽ せ足 決属 術こ てラ 領 技 けリぴ 分率ぴ きぜっ
               物味ドン おぎ一田ぴ ぶの謙 調ヲ星度 レぼむ囲 舗双脈 鶴挑げ
               ほぶ。無無 ツ縄第が 本公作 ゅゃふ く質失フ 米上議 ア記治 えれ本
               意つん ぎレ局 総ケ盛 載テ コ部止 メツ輪 帰歴 就些ル っき"""),
        "pl": (' ', """
               litwo ojczyzno moja ty jesteś jak zdrowie ile cię stracił
               dziś piękność widziana więc wszyscy dokoła brali stronę kusego
               albo sam wewnątrz siebie czuł się położył co by stary
               dąbrowskiego usłyszeć mazurek biegał po stole i krwi tonęła
               gdy sędziego służono niedbale słudzy nie na utrzymanie lecz
               mniej piękne niż myśliwi młodzi tak nie zmruża jako swe
               osadzał dziwna rzecz miejsca wkoło pali nawet stary który
               teraz za nim psów gromada gracz szarak skoro poczuł wszystkie
               charty w drobne strączki białe dziwnie ozdabiał głowę bo tak
               przekradł się uparta coraz głośniejsza kłótnia o wiejskiego
               pożycia nudach i długie paznokcie przedstawiając dwa tysiące
               jako jenerał dąbrowski z wysogierdem radziwiłł z drzewa lecz
               lekki odgadniesz że pewnie na jutro solwuję i na kształt
               ogrodowych grządek że ją bardzo szybko suwała się na
               przeciwnej zajadłość dowiodę że dziś z lasu wracało towarzystwo
               całe wesoło lecz go grzecznie na złość rejentowi że u
               wieczerzy będzie jego upadkiem domy i bagnami skradał się tłocz
               i jak bawić się nie było bo tak na jutro solwuję i przepraszał
               sędziego sędzia sam na początek dać małą kiedy"""),
    }

    def __init__(self, kind):
        self.kind = kind
        self.space = self.LOREM_IPSUM[self.kind][0]
        self.words = self.LOREM_IPSUM[self.kind][1].split()
        self.n_words = collections.defaultdict(list)
        for word in self.words:
            self.n_words[len(word)].append(word)

    def _get_ipsum(self, text):
        return re.sub(
            '(%[sdr]|{[^}]*}|[a-zA-Z]+)',
            lambda match: self._tr_word(match.group(1)),
            text)

    def _tr_word(self, word):
        if re.search("(%[sdr])|({[^}]*})", word):
            return word
        elif word.startswith("--"):
            return "--{}".format(self._tr_word(word[2:]))
        elif word.startswith("-"):
            return "-{}".format(self._tr_word(word[1:]))
        elif word.startswith("[") and word.endswith("]"):
            return "[{}]".format(self._tr_word(word[1:-1]))
        elif word.startswith("<") and word.endswith(">"):
            return "<{}>".format(self._tr_word(word[1:-1]))
        else:
            tr_word = self._tr_approx(len(word))
            if word.isupper():
                return tr_word.upper()
            if word[0].isupper():
                return tr_word.capitalize()
            else:
                return tr_word

    def _tr_approx(self, desired_length):
        for avail_length in sorted(self.n_words):
            if desired_length <= avail_length:
                break
        return random.choice(self.n_words[avail_length])

    def gettext(self, msgid):
        return self.dgettext("plainbox", msgid)

    def dgettext(self, domain, msgid):
        return "<{}: {}>".format(domain, self._get_ipsum(msgid))

    def ngettext(self, msgid1, msgid2, n):
        if n == 1:
            return self._get_ipsum(msgid1)
        else:
            return self._get_ipsum(msgid2)
        pass


class GettextTranslator:

    def __init__(self, domain):
        self._domain = domain
        self._translations = {}
        self._locale_dir = os.getenv("PLAINBOX_LOCALE_DIR", None)

    def _get_translation(self, domain):
        try:
            return self._translations[domain]
        except KeyError:
            try:
                translation = gettext_module.translation(domain, self._locale_dir)
            except IOError:
                translation = gettext_module.NullTranslations()
            self._translations[domain] = translation
            return translation

    def dgettext(self, domain, msgid):
        return self._get_translation(domain).gettext(msgid)

    def gettext(self, msgid):
        return self._get_translation(self._domain).gettext(msgid)

    def ngettext(self, msgid1, msgid2, n):
        return self._get_translation(self._domian).ngettext(msgid1, msgid2, n)


_translators = {
    "gettext": GettextTranslator("plainbox"),
    "lorem-ipsum-ar": LoremIpsumTranslator("ar"),
    "lorem-ipsum-ch": LoremIpsumTranslator("ch"),
    "lorem-ipsum-he": LoremIpsumTranslator("he"),
    "lorem-ipsum-jp": LoremIpsumTranslator("jp"),
    "lorem-ipsum-kr": LoremIpsumTranslator("kr"),
    "lorem-ipsum-pl": LoremIpsumTranslator("pl"),
    "lorem-ipsum-ru": LoremIpsumTranslator("ru"),
    "no-op": NoOpTranslator,
    "rot-13": Rot13Translator,
}

_mode = os.getenv("PLAINBOX_I18N_MODE", "gettext")
try:
    _translator = _translators[_mode]
except KeyError:
    raise RuntimeError("Unsupported PLAINBOX_I18N_MODE: {!r}".format(_mode))
gettext = _translator.gettext
ngettext = _translator.ngettext
dgettext = _translator.dgettext
gettext_noop = lambda msgid: msgid
