#!/bin/bash
set -e

##
# Pre-requirements:
# - env FUZZER: path to fuzzer work dir
# - env TARGET: path to target work dir
# - env MAGMA: path to Magma support files
# - env BUG: bug patch name to be directed towards
# - env OUT: path to directory where artifacts are stored
# - env CFLAGS and CXXFLAGS must be set to link against Magma instrumentation
##

export CC="$FUZZER/repo/afl-clang-fast"
export CXX="$FUZZER/repo/afl-clang-fast++"
export AS="$FUZZER/repo/afl-as"

export LIBS="$LIBS -l:afl_driver.o -lstdc++"

"$MAGMA/build.sh"


# Setup directory containing all temporary files for AFLgo
export TMP_DIR=$OUT/temp
mkdir -p $TMP_DIR

# Set targets
# Download commit-analysis tool
wget -P $TMP_DIR/ https://raw.githubusercontent.com/jay/showlinenum/develop/showlinenum.awk
chmod +x $TMP_DIR/showlinenum.awk

# Generate BBtargets $BUG.patch
echo "" > $TMP_DIR/BBtargets.txt
echo ""> $TMP_DIR/Ftargets.txt.bk
for f in $TARGET/patches/bugs/*;
do
    echo $f;
    cat $f |  $TMP_DIR/showlinenum.awk show_header=0 path=1 | grep --color=never -e "\.[ch]:[0-9]*:+" -e "\.cpp:[0-9]*:+" -e "\.cc:[0-9]*:+" | cut -d+ -f1 | rev | cut -c2- | rev >> $TMP_DIR/BBtargets.txt
    cat $f |  $TMP_DIR/showlinenum.awk | grep @@ | cut -f1 -d"(" | rev | cut -f1 -d" " | rev | tr -d "{" | tr -d "*" | tr -d ":" >> $TMP_DIR/Ftargets.txt.bk
done

# Set aflgo-instrumentation flags
export COPY_CFLAGS=$CFLAGS
export COPY_CXXFLAGS=$CXXFLAGS
export COPY_LDFLAGS=$LDFLAGS
export ADDITIONAL="-targets=$TMP_DIR/BBtargets.txt -outdir=$TMP_DIR -flto -fuse-ld=gold -Wl,-plugin-opt=save-temps"
export CFLAGS="$CFLAGS $ADDITIONAL"
export CXXFLAGS="$CXXFLAGS $ADDITIONAL"
export RANLIB="/usr/bin/llvm-ranlib"
if [[ "$TARGET" = "/magma/targets/lua" ]]; then
    echo "setting ld flags"
    export LDFLAGS="$LDFLAGS $ADDITIONAL"
    cp $TARGET/repo/makefile $TARGET/repo/makefile.old
    sed '/RANLIB= ranlib/d' $TARGET/repo/makefile.old > $TARGET/repo/makefile
    diff $TARGET/repo/makefile $TARGET/repo/makefile.old || true
else
    echo "ignoring ldflags"
fi

# Build target in order to generate CG and CFGs
echo "building"
"$TARGET/build.sh"

# Test whether CG/CFG extraction was successful
echo "Dot-file number: $(ls $TMP_DIR/dot-files | wc | awk '{print $1}')" 
echo "Function targets"
if [[ ! -s $TMP_DIR/Ftargets.txt ]]; then
    cp $TMP_DIR/Ftargets.txt.bk $TMP_DIR/Ftargets.txt
    echo "Replacing ftargets..."
fi
cat $TMP_DIR/Ftargets.txt
if [[ ! -s $TMP_DIR/Ftargets.txt ]]; then
	echo "Empty Ftargets.txt"
	echo "Aborting..."
	exit 1
fi

# Clean up
cat $TMP_DIR/BBnames.txt | rev | cut -d: -f2- | rev | sort | uniq > $TMP_DIR/BBnames2.txt && mv $TMP_DIR/BBnames2.txt $TMP_DIR/BBnames.txt
cat $TMP_DIR/BBcalls.txt | sort | uniq > $TMP_DIR/BBcalls2.txt && mv $TMP_DIR/BBcalls2.txt $TMP_DIR/BBcalls.txt

# Generate distance
echo $TARGET
build_dir="$OUT"
source "$TARGET/configrc"
for P in "${PROGRAMS[@]}"; do
        echo "Running $P\n\n"
        echo "RunStart\n" >> $OUT/timing
        date +%s >> $OUT/timing
        $FUZZER/repo/scripts/genDistance.sh $build_dir $TMP_DIR $P
        echo "RunStage1\n" >> $OUT/timing
        date +%s >> $OUT/timing
        echo "Distance values:"
        cp "$TMP_DIR/distance.cfg.txt" "$TMP_DIR/distance_$P.cfg.txt"
        rm "$TMP_DIR/distance.cfg.txt"
        head -n5 "$TMP_DIR/distance_$P.cfg.txt"
        echo "..."
        tail -n5 "$TMP_DIR/distance_$P.cfg.txt"


        export CFLAGS="$COPY_CFLAGS -distance=$TMP_DIR/distance_$P.cfg.txt"
        export CXXFLAGS="$COPY_CXXFLAGS -distance=$TMP_DIR/distance_$P.cfg.txt"
        if [[ "$TARGET" = "/magma/targets/lua" ]]; then
            echo "setting ld flags 2"
            export LDFLAGS="$COPY_LDFLAGS"
        else
            echo "ignoring ldflags 2"
        fi

        "$TARGET/build.sh"
        echo "RunEnd\n" >> $OUT/timing
        date +%s >> $OUT/timing
        mkdir -p $OUT/$P-tmp/
        cp $OUT/$P $OUT/$P-tmp/
        rm $OUT/$P
        cp $OUT/$P-tmp/$P $OUT/
done
