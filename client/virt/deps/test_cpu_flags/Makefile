MKDIR = mkdir -p

OPTFLAGS=-O3

CFLAGS= ${OPTFLAGS} -std=c99 -pipe \
	-ftree-vectorize \
	-ffast-math \
	-fopenmp \

CFLAGSAVX= ${CFLAGS} \
		-mavx \

CFLAGSFMA4= ${CFLAGS} \
	-mfma4 \

CFLAGSSSE4A= ${CFLAGS} \
	-msse4a \

CFLAGSSSE4= ${CFLAGS} \
	-msse4 -msse4.1 -msse4.2 \

CFLAGSSSSE3= ${CFLAGS} \
	-mssse3 \

CFLAGSSSE3= ${CFLAGS} \
	-msse3 \

CFLAGSAES= ${CFLAGS} \
	-maes \

CFLAGSPCLMUL= ${CFLAGS} \
	-mpclmul \

CFLAGSRDRAND= ${CFLAGS} \
	-mrdrnd \

CFLAGSXOP= ${CFLAGS} \
	-mxop \

CFLAGSSTRESS= ${CFLAGS} \
	$(EXTRA_FLAGS) \

CXX=g++
CC=gcc

LIBS=-lgomp

.PHONY: default all cpuflags-test clean

default:cpuflags-test

all:cpuflags-test

cpuflags-test: avx.o fma4.o xop.o sse4a.o sse4.o ssse3.o sse3.o aes.o pclmul.o rdrand.o stress.o stressmem.o
	$(CC) $(CFLAGS) $(LIBS) cpuflags-test.c -o cpuflags-test \
		aes.o \
		pclmul.o \
		rdrand.o \
		avx.o \
		fma4.o \
		xop.o \
		sse4a.o \
		sse4.o \
		ssse3.o \
		sse3.o \
		stress.o \
		stressmem.o \

aes.o: aes.c tests.h
	$(CC) $(CFLAGSAES) $(LIBS) -c aes.c

pclmul.o: pclmul.c tests.h
	$(CC) $(CFLAGSPCLMUL) $(LIBS) -c pclmul.c

rdrand.o: rdrand.c tests.h
	$(CC) $(CFLAGSRDRAND) $(LIBS) -c rdrand.c

fma4.o: fma4.c tests.h
	$(CC) $(CFLAGSFMA4) $(LIBS) -c fma4.c

xop.o: xop.c tests.h
	$(CC) $(CFLAGSXOP) $(LIBS) -c xop.c

avx.o: avx.c tests.h
	$(CC) $(CFLAGSAVX) $(LIBS) -c avx.c

sse4a.o: sse4a.c tests.h
	$(CC) $(CFLAGSSSE4A) $(LIBS) -c sse4a.c

sse4.o: sse4.c tests.h
	$(CC) $(CFLAGSSSE4) $(LIBS) -c sse4.c

ssse3.o: ssse3.c tests.h
	$(CC) $(CFLAGSSSSE3) $(LIBS) -c ssse3.c

sse3.o: sse3.c tests.h
	$(CC) $(CFLAGSSSE3) $(LIBS) -c sse3.c

stress.o: stress.c tests.h
	$(CC) $(CFLAGSSTRESS) $(LIBS) -c stress.c

stressmem.o: stressmem.c tests.h
	$(CC) $(CFLAGSSTRESS) $(LIBS) -c stressmem.c


ARCHIVE= cpuflags-test

tar: clean
	tar cf - ../src | bzip2 -9 > ../$(ARCHIVE).tar.bz2

clean:
	rm -f *~
	rm -f *.o
	rm -f cpuflags-test
