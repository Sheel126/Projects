/**
    @file io.c
    @author Sheel Patel (scpatel6)
    This program takes in file pointer to read or write eight byte blocks to the file provided.
 */

#include "io.h"
#include <stdio.h>
#include <stdlib.h>

/** Max length for how many bytes can be stored at a time */
#define MAX_LEN 8

/**
    Program reads the file pointer and the block struct type to read eight bytes from the file and store them in the block->data 
    which is an array of bytes read from the file and is eight long
    @param fp is the file pointer that the program reads from
    @param block is the block pointer to the struct that contains data to hold bytes read from the file
 */
void readBlock( FILE *fp, DESBlock *block )
{
    block->len = fread( block->data, sizeof( byte ), BLOCK_BYTES, fp );
    
    // EOF Errors maybe?
}

/**
    Program that reads the file pointer and the block struct type to write eight bytes to the file from the block->data struct
    @param fp is the file pointer that the program writes to
    @param block is the block pointer to the struct that contains data to write from (cotains bytes). 
 */
void writeBlock( FILE *fp, DESBlock const *block )
{

    //for ( int i = 0; i < 8; i++ ) {
       //   printf("%X\n", block->data[i]);
     //}    


    //fwrite( block->data, sizeof( byte ) , block->len, fp );

    int remove0 = block->len;
    
    int end = MAX_LEN;
    if ( block->len % MAX_LEN + 1 == 0 ) {
        end = block->len - 1;
    }    

    for ( int i = 0; i < end; i++ ) {
        if ( block->data[i] == 0x00 && remove0 == MAX_LEN ) {
            break;
        }
        fputc( block->data[ i ], fp );
    }
}
