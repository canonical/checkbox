
## <a id='top'>environ keys for crypto test</a>
- HWRNG
	- Affected Test Cases:
		- [ce-oem-crypto/hwrng-current](#ce-oem-crypto/hwrng-current)

## Detailed test cases
### <a id='ce-oem-crypto/hwrng-current'>ce-oem-crypto/hwrng-current</a>
- **environ :**  HWRNG
- **summary :**  Check if current Hardware Random Number Generate is expected.
- **description :**  
```
None
```
- **command :**  
```
path_hwrng='/sys/class/misc/hw_random/'
if [ -e "$path_hwrng/rng_available" ]; then
    echo "HWRNG_Available: $(cat "$path_hwrng"rng_available)"
fi
if [ -e "$path_hwrng/rng_current" ]; then
    echo "HWRNG_Current: $(cat "$path_hwrng"rng_current)"
fi
if [ -e "$path_hwrng/rng_qulity" ]; then
    echo "HWRNG_Quality: $(cat "$path_hwrng"rng_qulity)"
fi
if [ -e "$path_hwrng/rng_selected" ]; then
    echo "HWRNG_Selected: $(cat "$path_hwrng"rng_selected)"
fi
if [ -z "$HWRNG" ];then
    echo "FAIL: Checkbox config HWRNG has not been set!"
    exit 1
elif [ "$HWRNG" == "$(cat "$path_hwrng"rng_current)" ];then
    echo "PASS: $HWRNG is available"
    exit 0
else
    echo "FAIL: $HWRNG is not available"
    exit 1
fi
```

[Back to top](#top)
### <a id='ce-oem-crypto/caam/caam_hwrng_test'>ce-oem-crypto/caam/caam_hwrng_test</a>
- **environ :**  None
- **summary :**  Check if CAAM job ring increased after generate random number by using hwrng.
- **description :**  
```
None
```
- **command :**  
```
init_interrupt=$(awk '/\.jr/ {printf "%s ",$2;next;}' /proc/interrupts|sed 's/ //g')
if [ -z "$init_interrupt" ]
then
    echo "ERROR: Can not find CAAM job ring interrupts"
    exit 1
fi
echo "CAAM Job ring interrupt before using Hardware RNG: $init_interrupt"
echo "Starting DD of /dev/hwrng ..."
for i in {1..20}
do
    dd if=/dev/hwrng bs=512K count=1 > /dev/null
    echo "Finished $i/20 times DD ..."
    interrupt=$(awk '/\.jr/ {printf "%s ",$2;next;}' /proc/interrupts|sed 's/ //g')
    echo "Current job ring interrupt: $interrupt"
    if [ "$interrupt" -gt "$init_interrupt" ];
    then
        echo "PASS: CAAM job ring interrupts have increased."
        exit 0
    fi
done
echo "FAIL: CAAM job ring interrupts didn't increase!"
exit 1
```

[Back to top](#top)
### <a id='ce-oem-crypto/caam/algo_check'>ce-oem-crypto/caam/algo_check</a>
- **environ :**  None
- **summary :**  Check CAAM algorithm is in the system /proc/crypto
- **description :**  
```
None
```
- **command :**  
```
status=0
if grep -q caam /proc/crypto; then
    echo -e "\nInfo: Found CAAM algorithm in /proc/crypto"
else
    echo -e "\nError: No any CAAM algorithm has been found in /proc/crytpo"
    status=1
fi
echo -e "\nPlease refer to resource job cryptoinfo for more detail"
exit "$status"
```

[Back to top](#top)
### <a id='ce-oem-crypto/caam-crypto-profiles'>ce-oem-crypto/caam-crypto-profiles</a>
- **environ :**  None
- **summary :**  Generates a crypto profiles for CAAM accelerator
- **description :**  
```
A set of crypto profile mapping for CAAm accelerator.
```
- **command :**  
```
check_crypto_profile.py resource -t caam
```

[Back to top](#top)
### <a id='ce-oem-crypto/mcrc-crypto-profiles'>ce-oem-crypto/mcrc-crypto-profiles</a>
- **environ :**  None
- **summary :**  Generates a crypto profiles for MCRC accelerator
- **description :**  
```
A set of crypto profile mapping for MCRC accelerator.
```
- **command :**  
```
check_crypto_profile.py resource -t mcrc
```

[Back to top](#top)
### <a id='ce-oem-crypto/sa2ul-crypto-profiles'>ce-oem-crypto/sa2ul-crypto-profiles</a>
- **environ :**  None
- **summary :**  Generates a crypto profiles for SA2UL accelerator
- **description :**  
```
A set of crypto profile mapping for SA2UL accelerator.
```
- **command :**  
```
check_crypto_profile.py resource -t sa2ul
```

[Back to top](#top)
### <a id='cryptoinfo'>cryptoinfo</a>
- **environ :**  None
- **summary :**  Collect information about the crypto algorithm in system
- **description :**  
```
Gets crypto algorithm resource info from /proc/crypto
```
- **command :**  
```
cat /proc/crypto
```

[Back to top](#top)
### <a id='ce-oem-crypto/cryptsetup_benchmark'>ce-oem-crypto/cryptsetup_benchmark</a>
- **environ :**  None
- **summary :**  Measure the cryptographic performance of system
- **description :**  
```
Measure the cryptographic performance of system by using cryptsetup
```
- **command :**  
```
log=$(mktemp)
echo "Starting cryptographic benchmark testing ..."
cryptsetup benchmark | tee "$log"
awk '/aes-xts *512b/ {encryption=$3; decryption=$5} END {print "Performace of AES-XTS 512b", "\nEncryption:", encryption, "Mib/s", "\nDecryption:", decryption, "Mib/s"}' "$log"
```

[Back to top](#top)
### <a id='ce-oem-crypto/af_alg_hash_crc64_test'>ce-oem-crypto/af_alg_hash_crc64_test</a>
- **environ :**  None
- **summary :**  Check kernel crypto API is functional with type HASH - CRC64 algorithm
- **description :**  
```
None
```
- **command :**  
```
af_alg_test.py --type hash_crc64
```

[Back to top](#top)
### <a id='ce-oem-crypto/af_alg_hash_sha256_test'>ce-oem-crypto/af_alg_hash_sha256_test</a>
- **environ :**  None
- **summary :**  Check kernel crypto API is functional with type HASH - SHA256 algorithm
- **description :**  
```
None
```
- **command :**  
```
af_alg_test.py --type hash_sha256
```

[Back to top](#top)
### <a id='ce-oem-crypto/af_alg_aead_gcm_aes_test'>ce-oem-crypto/af_alg_aead_gcm_aes_test</a>
- **environ :**  None
- **summary :**  Check if kernel crypto API is functional with type AEAD - GCM AES algorithm.
- **description :**  
```
None
```
- **command :**  
```
af_alg_test.py --type aead_gcm_aes
```

[Back to top](#top)
### <a id='ce-oem-crypto/af_alg_skcipher_cbc_aes_test'>ce-oem-crypto/af_alg_skcipher_cbc_aes_test</a>
- **environ :**  None
- **summary :**  Check if kernel crypto API is functional with type SKCIPHER - CBC AES algorithm.
- **description :**  
```
None
```
- **command :**  
```
af_alg_test.py --type skcipher_cbc_aes
```

[Back to top](#top)
### <a id='ce-oem-crypto/af_alg_rng_stdrng_test'>ce-oem-crypto/af_alg_rng_stdrng_test</a>
- **environ :**  None
- **summary :**  Check if kernel crypto API is functional with type RNG - stdrng algorithm.
- **description :**  
```
None
```
- **command :**  
```
af_alg_test.py --type rng_stdrng
```

[Back to top](#top)
### <a id='ce-oem-crypto/check-caam-crypto-profiles'>ce-oem-crypto/check-caam-crypto-profiles</a>
- **environ :**  None
- **summary :**  Check CAAM crypto {name} profile and its driver in the system
- **template_summary :**  Check CAAM crypto profile and its driver in the system
- **description :**  
```
None
```
- **command :**  
```
   check_crypto_profile.py check -n "{name}" -t {type} -d {driver_pattern}
```

[Back to top](#top)
### <a id='ce-oem-crypto/check-mcrc-crypto-profiles'>ce-oem-crypto/check-mcrc-crypto-profiles</a>
- **environ :**  None
- **summary :**  Check MCRC crypto {name} profile and its driver in the system
- **template_summary :**  Check MCRC crypto profile and its driver in the system
- **description :**  
```
None
```
- **command :**  
```
   check_crypto_profile.py check -n "{name}" -t {type} -d {driver_pattern}
```

[Back to top](#top)
### <a id='ce-oem-crypto/check-sa2ul-crypto-profiles'>ce-oem-crypto/check-sa2ul-crypto-profiles</a>
- **environ :**  None
- **summary :**  Check SA2UL crypto {name} profile and its driver in the system
- **template_summary :**  Check SA2UL crypto profile and its driver in the system
- **description :**  
```
None
```
- **command :**  
```
   check_crypto_profile.py check -n "{name}" -t {type} -d {driver_pattern}
```

[Back to top](#top)
