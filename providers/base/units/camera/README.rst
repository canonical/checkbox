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
- **camera-quality**: Computes the quality of the image using the brisque score
  It depends on python3-opencv and libsvm3.
- **camera-quality-rpi**: RPi-specific variant of the BRISQUE image quality check.

    **NOTE:**

    The python svm library is vendorized and imports `libsvm.so.3` from the 
    `LD_LIBRARY_PATH`. If the version is updated in the future, it should be
    changed manually in the `svm.py` file under 
    `checkbox-support/vendor/brisque/svm`.
