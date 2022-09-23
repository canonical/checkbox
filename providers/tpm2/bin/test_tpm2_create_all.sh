#;**********************************************************************;
#
# Copyright (c) 2016, Intel Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, 
# this list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice, 
# this list of conditions and the following disclaimer in the documentation 
# and/or other materials provided with the distribution.
#
# 3. Neither the name of Intel Corporation nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE 
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS 
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF 
# THE POSSIBILITY OF SUCH DAMAGE.
#;**********************************************************************;
#!/bin/bash

new_path=`dirname $0`
PATH="$PATH":"$new_path"
pCtx=
gAlg=
GAlg=
gAlgList="0x04 0x0B"
STATUS=0

rm -f /root/create.error.log /root/opr* /root/opu*

ctx_count=`ls /root/ | grep -c ^ctx.cpri`
if [ $ctx_count -le 1 ];then
	echo "we should execute test_tpm2_createprimary_all.sh first!"
    test_tpm2_createprimary_all.sh
fi

if [[ "$@" == *"--384"* ]]; then
    gAlgList="$gAlgList 0x0C"
fi

if [[ "$@" == *"--512"* ]]; then
    gAlgList="$gAlgList 0x0D"
fi

if [[ "$@" == *"--sm3256"* ]]; then
    gAlgList="$gAlgList 0x12"
fi

for pCtx in `ls /root/ctx.cpri*`
    do
    for gAlg in $gAlgList
        do 
        for GAlg in 0x01 0x08 0x23 0x25
            do 
            tpm2_create -c $pCtx -g $gAlg -G $GAlg -o /root/opu."$pCtx".g"$gAlg".G"$GAlg" -O /root/opr."$pCtx".g"$gAlg".G"$GAlg"
            if [ $? != 0 ];then 
            echo "tpm2_create error: pCtx=$pCtx gAlg=$gAlg GAlg=$GAlg"
            echo "tpm2_create error: pCtx=$pCtx gAlg=$gAlg GAlg=$GAlg" >> /root/create.error.log
            STATUS=1
            fi
        done
    done
done
exit $STATUS
