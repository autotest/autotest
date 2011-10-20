/*
 * stress.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#define size (40000000)

void AddTwo(float *aa, float *bb, int num_threads) {
	{
		for (int j = 0; j < 4; j++) {
			#pragma omp parallel for
			for (int i = 0; i < size; i++) {
				aa[i] = bb[i] * 100.0f + 2.0f / bb[i];
			}
		}

		int *a = malloc(sizeof(int) * 4096);

		#pragma omp parallel for
		for (int i = 0; i < 4096; i++){
			a[i] = (int)aa[i];
		}

		int sum = 0;
		#pragma omp parallel for reduction(+:sum)
		for (int i = 0; i < 2048; i++){
			sum += a[2*i] & a[2*i+1];
		}
		printf("%d\n",sum);
		free(a);
	}
}


void stress(inst in) {

	// arrays must be aligned by 16
	float *a = malloc(sizeof(float)*size);
	float *b = malloc(sizeof(float)*size);
	// define two arrays
	for (int i = 0; i < size; i++) {
		b[i] = rand();
	}
	omp_set_num_threads(in.num_threads);
	#pragma omp parallel
	while (1){
		AddTwo(a, b, in.num_threads); // call AddTwo function}
		if (in.avx)
			avx();
		if (in.sse4)
			sse4();
		if (in.sse3)
			sse3();
		if (in.ssse3)
			ssse3();
		if (in.aes)
			aes();
		if (in.pclmul)
			pclmul();
		if (in.rdrand)
			rdrand();
	}

	int r = rand()%size;
	printf("rand a[%d]=%f\n",r ,a[r]);

	free(a);
	free(b);
}
