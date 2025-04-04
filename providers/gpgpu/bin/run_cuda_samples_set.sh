#!/bin/bash
set -e  # Exit immediately if any command fails

# Function to print text in a specified color
print_colored() {
    local color="$1"  # First argument is the color
    local text="$2"   # Second argument is the text to print

    # Check the color argument and set the corresponding ANSI escape code
    case "$color" in
        green)
            echo -e "\033[32m$text\033[0m"  # Green text
            ;;
        red)
            echo -e "\033[31m$text\033[0m"   # Red text
            ;;
        *)
            echo "Unsupported color: $color"  # Default for unsupported colors
            ;;
    esac
}

function exit_trap {
    if [[ $KEEP_CACHE != 1 ]]; then
        cd $orig_dir && rm -rf $TEST_SET
    fi
}

if [[ -z "$1" || $1 == "-h" ]]; then
    echo "Please provide the index of the test set you need [0 to 8]".
    echo "Option are:"
    echo "    0 --> Introduction"
    echo "    1 --> Utilities"
    echo "    2 --> Concepts_and_Techniques"
    echo "    3 --> CUDA_Features"
    echo "    4 --> CUDA_Libraries"
    echo "    5 --> Domain_Specific"
    echo "    6 --> Performance"
    echo "    7 --> libNVVM"
    echo "    8 --> Platform_Specific"
    echo ""
    echo 'Set CUDA_IGNORE_TESTS="<test1 test2 test3>" to ignore specific tests. Do not put "" if you are in a checkbox config file.'
    echo "Set CUDA_SAMPLES_VERSION=MAJOR.MINOR to set the sample version you need. default is 12.8."
    echo "set CUDA_IGNORE_TENSORCORE=1 if your machine does not have TensorCores."
    echo "Set CUDA_MULTIGPU=1 if your machine has multiple NVIDIA GPUs"
    echo "Set KEEP_CACHE=1 to keep the file from the session. Then set CLONE=0 to reuse the files from a previous session."
    exit 1
fi

set -x

TEST_SET=$1
orig_dir=$(pwd)

#########################
### clone the cuda samples repo and build the right subfolder
##############################
if [[ $CLONE != 0 ]]; then
    # Ensure CUDA, cmake, other deps are installed before running.
    if [[ -d $TEST_SET ]];then
        echo "Error: folder $TEST_SET exists."
        exit 1
    fi

    echo "Cloning CUDA Samples $CUDA_SAMPLES_VERSION."

    git clone -b v${CUDA_SAMPLES_VERSION:-"12.8"} --single-branch https://github.com/NVIDIA/cuda-samples.git $TEST_SET

    # after that, set the trap
    trap exit_trap EXIT

    # a small trick for the executables to be within a 'bin' folder, to find them more easily

    { echo 'set(EXECUTABLE_OUTPUT_PATH "bin")'; cat $TEST_SET/CMakeLists.txt; } > temp && mv temp $TEST_SET/CMakeLists.txt

    # remove all folders except the one we need
    cd ${orig_dir}/$TEST_SET/Samples
    for DIR in [0-9]_*; do
        # Check if it's a directory
        if [ -d "$DIR" ]; then
            # Extract the first number from the folder name
            FOLDER_NUMBER=$(echo "$DIR" | cut -d'_' -f1)

            if [[ "$FOLDER_NUMBER" != "$TEST_SET" ]]; then
                echo "Removing directory: $DIR"
                rm -r "$DIR" 
                # Remove the corresponding line from the CMakeLists.txt file
                echo "Removing line for $DIR in CMakeLists.txt"
                sed -i "/add_subdirectory($DIR)/d" CMakeLists.txt
            else
                echo "Keeping directory: $DIR"
            fi
        fi
    done

    cd ${orig_dir}/${TEST_SET}
    mkdir -p build && cd build
    cmake -DCMAKE_CUDA_ARCHITECTURES=native -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/ -DCMAKE_INCLUDE_PATH=/usr/local/cuda/include ..
    make -j$(($(nproc) - 1))
fi

#########################
### Exclude feature tests. To put in checkbox resources in the future?
##############################
if [[ $CUDA_IGNORE_TENSORCORE == 1 ]]; then
    EXCLUDE_LIST_TENSORCORES="dmmaTensorCoreGemm tf32TensorCoreGemm bf16TensorCoreGemm"
fi

if [[ $CUDA_MULTIGPU != 1 ]]; then
    EXCLUDE_LIST_MULTIGPU="simpleCUFFT_MGPU simpleCUFFT_2d_MGPU conjugateGradientMultiDeviceCG"
fi

exclude_list="
$EXCLUDE_LIST_TENSORCORES
$EXCLUDE_LIST_MULTIGPU
$CUDA_IGNORE_TESTS
"

#########################
### Run the tests
##############################
cd ${orig_dir}/${TEST_SET}/build/Samples
file_list=($(find . -type f -path "./${TEST_SET}_*/*/bin/*" -executable))
list_length=${#file_list[@]}
skipped=0
for ((index=0; index<list_length; index++)); do
    exe="${file_list[$index]}"
    print_colored green "Step $((index+1)) of $list_length: $exe"
    exe_dir=$(dirname "$exe")  # Get the directory of the executable
    exe_name=$(basename "$exe") # Get the executable file name

    # Check if exe_name is in the exclude_list
    excluded=false
    for pattern in $exclude_list; do
        if [[ "$exe_name" =~ ^$pattern$ ]]; then
            excluded=true
            break
        fi
    done

    if [ "$excluded" = true ]; then
        print_colored red "Skipping $exe."
        skipped=$((skipped+1)) 
        continue
    fi

    echo "Running: $exe in $exe_dir"

    cd "$exe_dir"  # Navigate to the executable's directory
    "./$exe_name"  # Run the executable
    cd ${orig_dir}/${TEST_SET}/build/Samples
done

print_colored green "All $list_length test done, $skipped skipped."