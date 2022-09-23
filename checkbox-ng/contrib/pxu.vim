" Vim syntax file
" Language:    PlainBox Unit Definition
" Maintainer:  Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
" Last Change: 2014 Mar 04
" URL: https://launchpad.net/checkbox
"
" This file is part of Checkbox.
"
" Copyright 2012 Canonical Ltd.
" Written by:
"   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
"
" Checkbox is free software: you can redistribute it and/or modify
" it under the terms of the GNU General Public License version 3,
" as published by the Free Software Foundation.
"
" Checkbox is distributed in the hope that it will be useful,
" but WITHOUT ANY WARRANTY; without even the implied warranty of
" MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
" GNU General Public License for more details.
"
" You should have received a copy of the GNU General Public License
" along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

" Standard syntax initialization
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

" Should match case except for the keys of each field
syn case match

" Everything that is not explicitly matched by the rules below
syn match pxuElse "^.*$"

" Common separators
syn match pxuComma ", *"
syn match pxuSpace " "

" Define some common expressions we can use later on
syn match pxuPlugin contained "\%(shell\|manual\|local\|resource\|attachment\|user-interact\|user-verify\|user-interact-verify\)"
syn match pxuFlags contained "\%(preserve-locale\|expected-failure\|legacy-remote\|multi-node\)"
syn match pxuId contained "[a-z0-9][a-z0-9+./:-]\+"
syn match pxuVariable contained "\${.\{-}}"
syn match pxuSpecialVariable contained "\%(\$PLAINBOX_SESSION_SHARE\|\$PLAINBOX_PROVIDER_DATA\)"
syn match pxuDeprecatedVariable contained "\%(\$CHECKBOX_SHARE\|\$CHECKBOX_DATA\)"
syn match pxuEstimatedDuration contained "\<\d+(\.\d+)?\>"
syn match pxuColonColon contained "::"

" #-Comments
syn match pxuComment "^#.*$" contains=@Spell

syn case ignore

" leading dot in multi-line fields
syn match pxuLeadingDot contained "^\s+\."

" List of all legal keys
syn match pxuKey contained "^\%(id\|plugin\|_?summary\|_?description\|requires\|depends\|estimated_duration\|command\|user\|environ\|flags\): *"

syn match pxuDeprecatedKey contained "^\%(name\): *"

" Fields for which we do strict syntax checking
syn region pxuStrictField start="^id" end="$" contains=pxuKey,pxuId,pxuSpace oneline
syn region pxuStrictField start="^plugin" end="$" contains=pxuKey,pxuPlugin,pxuSpace oneline
syn region pxuStrictField start="^flags" end="$" contains=pxuKey,pxuFlags,pxuSpace oneline
syn region pxuStrictField start="^estimated_duration" end="$" contains=pxuKey,pxuEstimatedDuration,pxuSpace oneline

" Catch-all for the other legal fields
syn region pxuField start="^\%(id\|plugin\|_?summary\|_?description\|requires\|depends\|estimated_duration\|command\|user\|environ\):" end="$" contains=pxuKey,pxuDeprecatedKey,pxuVariable,pxuColonColon,pxuId oneline
syn region pxuMultiField start="^\%(command\|depends\|requires\):" skip="^ " end="^$"me=s-1 end="^[^ #]"me=s-1 contains=pxuKey,pxuDeprecatedkey,pxuVariable,pxuSpecialVariable,pxuDeprecatedVariable,pxuId,pxuComment,pxuLeadingDot
syn region pxuMultiFieldSpell start="^_?\%(description\|summary\):" skip="^ " end="^$"me=s-1 end="^[^ #]"me=s-1 contains=pxuKey,pxuDeprecatedKey,pxuComment,pxuLeadingDot,@Spell

" Associate our matches and regions with pretty colours
if version >= 508 || !exists("did_pxu_syn_inits")
  if version < 508
    let did_pxu_syn_inits = 1
    command -nargs=+ HiLink hi link <args>
  else
    command -nargs=+ HiLink hi def link <args>
  endif

  HiLink pxuPlugin                 Keyword
  HiLink pxuKey                    Keyword
  HiLink pxuField                  Normal
  HiLink pxuStrictField            Error
  HiLink pxuDeprecatedKey          Error
  HiLink pxuDeprecatedVariable     Error
  HiLink pxuEstimatedDuratin       Float
  HiLink pxuMultiField             Normal
  HiLink pxuMultiFieldSpell        Normal
  HiLink pxuId                     Identifier
  HiLink pxuFlags                  Identifier
  HiLink pxuVariable               Identifier
  HiLink pxuSpecialVariable        Identifier
  HiLink pxuComment                Comment
  HiLink pxuElse                   Special
  HiLink pxuLeadingDot             Error
  HiLink pxuColonColon             Keyword

  delcommand HiLink
endif

let b:current_syntax = "pxu"

" vim: ts=4 sw=4
