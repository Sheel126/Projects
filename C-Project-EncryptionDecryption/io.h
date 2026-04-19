/**
    @file io.h
    @author Sheel Patel (scpatel6)
    Header file program that contains prototypes for functions in io.c
    readBlock and writeBlock
 */

#include "DES.h"
#include <stdio.h>
#include <stdlib.h>

/**
    Program reads the file pointer and the block struct type to read eight bytes from the file and store them in the block->data 
    which is an array of bytes read from the file and is eight long
    @param fp is the file pointer that the program reads from
    @param block is the block pointer to the struct that contains data to hold bytes read from the file
 */
void readBlock( FILE *fp, DESBlock *block );

/**
    Program that reads the file pointer and the block struct type to write eight bytes to the file from the block->data struct
    @param fp is the file pointer that the program writes to
    @param block is the block pointer to the struct that contains data to write from (cotains bytes). 
 */
void writeBlock( FILE *fp, DESBlock const *block );
