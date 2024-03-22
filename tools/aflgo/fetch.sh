#!/bin/bash
set -e

##
# Pre-requirements:
# - env FUZZER: path to fuzzer work dir
##

git clone --no-checkout https://github.com/aflgo/aflgo.git "$FUZZER/repo"
git -C "$FUZZER/repo" checkout cf5c7ab0eafead7f697e48e676ba6bab6c8d9958 
python3 -c "import os,glob; print([os.remove(f) for f in glob.glob(os.environ['TARGET']+'/patches/bugs/*.patch') if (os.environ['FUZZER']).split('_')[-1] not in f.lower()]); assert(len(os.listdir(os.environ['TARGET']+'/patches/bugs/')) == 1)"
python3 -c "import os,shutil,glob; print([shutil.copy(os.environ['FUZZER']+'/pocs/'+os.environ['FUZZER'].split('_')[-1].lower(), f) for f in glob.glob(os.environ['TARGET']+'/corpus/**/*')])"
#wget -O "$FUZZER/repo/afl_driver.cpp" \
#    "https://cs.chromium.org/codesearch/f/chromium/src/third_party/libFuzzer/src/afl/afl_driver.cpp"
cp "$FUZZER/src/afl_driver.cpp" "$FUZZER/repo/afl_driver.cpp"
