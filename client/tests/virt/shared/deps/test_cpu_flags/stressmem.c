/*
 * stress.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

typedef float vector_type;//

void stressmem(unsigned int sizeMB) {
	unsigned int size = sizeMB * 1024*1024;
	unsigned int subsize = (size / sizeof(vector_type));

	vector_type *a = malloc(size);

	printf("size %lld, subsize %lld", size, subsize);
	vector_type __attribute__ ((aligned(32))) v[256] = {0};
	while (1){
		#pragma omp parallel for private(v)
		for (unsigned int q = 0; q < subsize; q += 256) {
			for (unsigned int i = 0; i < 256; i++){
				v[i] += 1;
			}
			for (unsigned int i = 0; i < 256; i++) {
				a[q+i] += v[i];
			}
		}
	}
	printf("Stress round.\n");
	free(a);
}
