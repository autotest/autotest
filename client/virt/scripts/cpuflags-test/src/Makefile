MKDIR = mkdir -p

OPTFLAGS=-O3

CFLAGS= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-fopenmp \

CFLAGSAVX= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-mavx \
	-fopenmp \

CFLAGSSSE4= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-msse4 -msse4.1 -msse4.2 \
	-fopenmp \

CFLAGSSSSE3= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-mssse3 \
	-fopenmp \

CFLAGSSSE3= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-msse3 \
	-fopenmp \

CFLAGSAES= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-maes \
	-fopenmp \

CFLAGSPCLMUL= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-mpclmul \
	-fopenmp \

CFLAGSRDRAND= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	-mrdrnd \
	-fopenmp \

CFLAGSSTRESS= -m64 ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize -ftree-vectorizer-verbose=0 \
	-ffast-math \
	$(EXTRA_FLAGS) \
	-fopenmp \

CXX=g++
CC=gcc

LIBS=-lgomp

.PHONY: default all cpuflags-test clean

default:cpuflags-test

all:cpuflags-test

cpuflags-test: avx.o sse4.o ssse3.o sse3.o aes.o pclmul.o rdrand.o stress.o
	$(CC) $(CFLAGS) $(LIBS) cpuflags-test.c -o cpuflags-test \
		aes.o \
		pclmul.o \
		rdrand.o \
		avx.o \
		sse4.o \
		ssse3.o \
		sse3.o \
		stress.o \

aes.o: aes.c
	$(CC) $(CFLAGSAES) $(LIBS) -c aes.c

pclmul.o: pclmul.c
	$(CC) $(CFLAGSPCLMUL) $(LIBS) -c pclmul.c

rdrand.o: rdrand.c
	$(CC) $(CFLAGSRDRAND) $(LIBS) -c rdrand.c

avx.o: avx.c
	$(CC) $(CFLAGSAVX) $(LIBS) -c avx.c

sse4.o: sse4.c
	$(CC) $(CFLAGSSSE4) $(LIBS) -c sse4.c

ssse3.o: ssse3.c
	$(CC) $(CFLAGSSSSE3) $(LIBS) -c ssse3.c

sse3.o: sse3.c
	$(CC) $(CFLAGSSSE3) $(LIBS) -c sse3.c

stress.o: stress.c
	$(CC) $(CFLAGSSTRESS) $(LIBS) -c stress.c

ARCHIVE= cpuflags-test

tar: clean
	tar cf - ../src | bzip2 -9 > ../$(ARCHIVE).tar.bz2

clean:
	rm -f *~
	rm -f *.o
	rm -f cpuflags-test
