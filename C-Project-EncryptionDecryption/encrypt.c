/**
    @file encrypt.c
    @author Sheel Patel (scpatel6)
    The program takes in key, input, and output files for the encryption procedure.
    It takes the key to encrypt the input and store it in the output file (this will contain the
    cipher text)
 */

#include <stdio.h>
#include "io.h"
#include <stdlib.h>
#include <string.h>

/** Max length for how many bytes can be stored at a time */
#define MAX_LEN 8

/** Value for index 2 */
#define VAL_FOR_INDEX_TWO 2

/** Value for index 4 */
#define VAL_FOR_INDEX_FOUR 4

/**
   Program starting point that reads the input from the console that includes the key name, input text file, and
   the output file to write the output to. It creates subkeys and uses those to encrypt the input
   text and store it in the output file.
   @param argc is the number of elements passed into the main function from the command line
   @param argv is the array of pointers that point to command line arguments passed in like
   name of the program, key name, input file, and output file
   @return 0 if the program exits successfully and encryption is created. 1 if the program
   exits with failure
*/
int main( int argc, char *argv[] )
{

    if ( argc != VAL_FOR_INDEX_FOUR )
    {
        fprintf(stderr, "usage: encrypt <key-file> <input_file> <output_file>\n");
        exit( EXIT_FAILURE );
    }

    char keyName[ MAX_LEN + 1 ] = "";
    strcpy( keyName, argv[1] );
    if ( strlen(keyName) > MAX_LEN )
    {
        fprintf( stderr, "Key too long\n" );
        exit( EXIT_FAILURE );
    }

    byte key[ BLOCK_BYTES ];

    prepareKey( key, keyName );

    FILE *fp = fopen( argv[VAL_FOR_INDEX_TWO], "r" );
     if (!fp)
    {
        // printf( "%s: ", argv[2] );
        perror( argv[ VAL_FOR_INDEX_TWO ] );
        exit( EXIT_FAILURE );
    }
    FILE *fp2 = fopen( argv[ VAL_FOR_INDEX_TWO + 1 ], "wb" );

   
    if ( !fp2 )
    {
        perror( argv[ VAL_FOR_INDEX_TWO + 1 ] );
        exit( EXIT_FAILURE );
    }
    int instance = 0;

    while ( 1 )
    {
        // DESBlock *block = (DESBlock *)malloc(sizeof(DESBlock));
        //if ( feof( fp ) )
        //{
            //printf("RIGHT here? %d\n", instance);
            //break;
        //}
        DESBlock *block = ( DESBlock * )malloc( sizeof( DESBlock ) );
        block->len = 0;
        for ( int i = 0; i < MAX_LEN; i++ )
        {
            block->data[ i ] = 0x00;
        }
        byte K[ ROUND_COUNT ][ SUBKEY_BYTES ];
        generateSubkeys( K, key );
        readBlock( fp, block );
        block->len = MAX_LEN + 1;
        //printf("%d\n", block->len);
        //if ( block->len <= 8 ) {
          //      block->data[ 7 ] = 0x0a;
        //}
        // now block has what we need...
       
        //for ( int i = 0; i < 8; i++ ) {
          //  printf("%X\n", key[i]);
        //}
        
        
        encryptBlock( block, K );
        //for ( int i = 0; i < 8; i++ ) {
          //printf("%X\n", block->data[i]);
        //}
        
        
        writeBlock( fp2, block );
        char c = fgetc( fp );
        if ( c == EOF ) {
            free( block );
            break;
        }
        ungetc( c, fp );

        //for ( int i = 0; i < 8; i++ ) {
          //printf("%X\n", block->data[i]);
        //}
        free(block);
        instance++;
    }
    fclose( fp );
    fclose( fp2 );

    

    return 0;
}
