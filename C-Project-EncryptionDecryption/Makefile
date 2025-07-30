CC = gcc
CFLAGS = -Wall -std=c99

all: encrypt decrypt

encrypt: encrypt.o DES.o DESMagic.o io.o
	gcc encrypt.o DES.o DESMagic.o io.o -o encrypt

decrypt: decrypt.o DES.o DESMagic.o io.o
	gcc decrypt.o DES.o DESMagic.o io.o -o decrypt

DESTest: DESTest.o DES.o DESMagic.o
	gcc DESTest.o DES.o DESMagic.o -o DESTest

encrypt.o: encrypt.c io.h DES.h
	gcc -Wall -std=c99 -g -c encrypt.c

decrypt.o: decrypt.c io.h DES.h
	gcc -Wall -std=c99 -g -c decrypt.c

DES.o: DES.c DES.h DESMagic.h
	gcc -Wall -std=c99 -g -c DES.c

DESMagic.o: DESMagic.c
	gcc -Wall -std=c99 -g -c DESMagic.c

io.o: io.c io.h DES.h
	gcc -Wall -std=c99 -g -c io.c

DESTest.o: DESTest.c DES.h DESMagic.h
	gcc -Wall -std=c99 -g -c DESTest.c

clean: 
	rm -f *.o
	rm -f encrypt decrypt
	rm -f DESTest
	rm -f output.txt
	rm -f stderr.txt



