# Readme for Crypto-Related Jobs

This readme provides an overview of the different crypto tests available in this project, categorized into two main types: "Generic" and "Accelerator."

## Generic Tests

### cryptoinfo
   - This resource job retrieves and displays the content of `/proc/crypto`.

### ce-oem-crypto/cryptsetup_benchmark
   - This job assesses cryptographic benchmarking using the `cryptsetup` tool.
   - The primary focus is on the performance of "aes-xts 512b," which is the cipher utilized by Ubuntu Core Full Disk Encryption (FDE).
   - Example
```
    ubuntu@ubuntu:~$ sudo cryptsetup luksDump /dev/mmcblk3p5
    LUKS header information
    Version:        2
    Epoch:          4
    Metadata area:  2097152 [bytes]
    Keyslots area:  2621440 [bytes]
    UUID:           f4877ac8-a501-42de-857e-02e7d4384386
    Label:          ubuntu-data-enc
    Subsystem:      (no subsystem)
    Flags:          (no flags)

    Data segments:
      0: crypt
            offset: 7340032 [bytes]
            length: (whole device)
            cipher: aes-xts-plain64
            sector: 512 [bytes]

    Keyslots:
      0: luks2
            Key:        512 bits
            Priority:   preferred
            Cipher:     aes-xts-plain64
            Cipher key: 512 bits
            PBKDF:      argon2i
            Time cost:  4
            Memory:     32
            Threads:    1
            Salt:       1d a1 25 80 ad a6 b1 81 c7 46 fa 3a 1e f9 93 b2 
                        df 74 a3 45 46 d5 2e 61 89 1c 71 dd 41 1f 6c 0e 
            AF stripes: 4000
            AF hash:    sha256
            Area offset:4194304 [bytes]
            Area length:258048 [bytes]
            Digest ID:  0
    Tokens:
    Digests:
      0: pbkdf2
            Hash:       sha256
            Iterations: 1000
            Salt:       13 c9 ce 61 7e 47 f8 6e 9f be 61 4b 2b 9c f0 69 
                        08 ff a6 52 1a 8d 59 fc 83 f3 fb 68 54 3c 56 d3 
            Digest:     da db 41 09 dc ac e0 3f 9d 56 3b 2e ac 2e 5b 26 
                        54 06 cd ba 58 52 d2 77 e2 31 c3 60 8f 9b 8b b5 
```
### ce-oem-crypto/af_alg{cipher}
The AF_ALG related jobs aim to test the kernel crypto API with specific ciphers.

## Accelerator Tests

### ce-oem-crypto/caam/caam_hwrng_test
This job tests the CAAM HWRNG for functionality.

### ce-oem-crypto/caam/algo_check
This job checks and validates cryptographic algorithms for the CAAM accelerator.

### ce-oem-crypto/check-caam-priority
This job ensures the proper priority settings for the CAAM accelerator.

### ce-oem-crypto/check-mcrc-priority
This job verifies the priority settings for the MCRC accelerator.

### ce-oem-crypto/check-sa2ul-priority
This job confirms the priority settings for the SA2UL accelerator.

### ce-oem-crypto/hwrng-current
This job checks the currently active Hardware Random Number Generator (HWRNG), ensuring it aligns with expectations. The job's execution depends on the `HWRNG` checkbox configuration variable.
- Example
  ```
  HWRNG = rng-caam
  or
  HWRNG = hwrng-hse
  ```
