Camera unit
=======================

Unit is responsible for camera control and image processing tests.

Jobs
####

- **detect**
- **detect-rpi**
- **display**
- **led**
- **still**
- **multiple-resolution-images-rpi**
- **multiple-resolution-images-rpi**
- **roundtrip-qrcode**
- **camera-quality**: Computes the quality of the image using the brisque score
  It depends on python3-opencv and libsvm3.

    **NOTE:**

    The python svm library is vendorized and imports `libsvm.so.3` from the 
    `LD_LIBRARY_PATH`. If the version is updated in the future, it should be
    changed manually in the `svm.py` file under 
    `checkbox-support/vendor/brisque/svm`.

