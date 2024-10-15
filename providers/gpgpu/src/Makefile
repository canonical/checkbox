.PHONY: all
all: gpu_burn deviceQueryDrv vectorAddDrv matrixMulDrv simpleTextureDrv

DATA_DIR=../../data

.PHONY: clean
clean:
	rm -rf gpu-burn cuda-samples
	rm -f gpu_burn deviceQueryDrv vectorAddDrv matrixMulDrv simpleTextureDrv
	rm -f "${DATA_DIR}/{compare.ptx,matrixMul_kernel64.fatbin,vectorAdd_kernel64,simpleTexture_kernel64,ref_rotated.pgm,teapot512.pgm,teapot512_out.pgm}"

gpu-burn:
	git clone https://github.com/wilicc/gpu-burn.git
gpu_burn: gpu-burn
	make -C gpu-burn
	mv gpu-burn/gpu_burn .
	mv gpu-burn/compare.ptx ${DATA_DIR}

cuda-samples:
	git clone https://github.com/nvidia/cuda-samples.git
matrixMulDrv: cuda-samples
	make -C cuda-samples/Samples/0_Introduction/matrixMulDrv
	mv cuda-samples/Samples/0_Introduction/matrixMulDrv/matrixMulDrv .
	mv cuda-samples/Samples/0_Introduction/matrixMulDrv/data/* ${DATA_DIR}
vectorAddDrv: cuda-samples
	make -C cuda-samples/Samples/0_Introduction/vectorAddDrv
	mv cuda-samples/Samples/0_Introduction/vectorAddDrv/vectorAddDrv .
	mv cuda-samples/Samples/0_Introduction/vectorAddDrv/data/* ${DATA_DIR}
deviceQueryDrv: cuda-samples
	make -C cuda-samples/Samples/1_Utilities/deviceQueryDrv
	mv cuda-samples/Samples/1_Utilities/deviceQueryDrv/deviceQueryDrv .
simpleTextureDrv: cuda-samples
	make -C cuda-samples/Samples/0_Introduction/simpleTextureDrv
	mv cuda-samples/Samples/0_Introduction/simpleTextureDrv/simpleTextureDrv .
	mv cuda-samples/Samples/0_Introduction/simpleTextureDrv/data/* ${DATA_DIR}
