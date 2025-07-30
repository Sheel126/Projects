/**
    @file DES.h
    @author Sheel Patel (scpatel6)
    Header for the DES Implementation.
*/

#include "DESMagic.h"

/** Number of bits in a byte. */
#define BYTE_SIZE 8

/** Round a number of bits up to the nearest number of bytes needed
    to store that many bits. */
#define ROUND_TO_BYTES( bits ) ( ( ( bits ) + BYTE_SIZE - 1 ) / BYTE_SIZE )

/** Number of bytes in a DES block. */
#define BLOCK_BYTES ROUND_TO_BYTES( BLOCK_BITS )

/** Number of bytes in the left or right halves of a block (L and R). */
#define BLOCK_HALF_BYTES ROUND_TO_BYTES( BLOCK_HALF_BITS )

/** Number of bytes to store the left-side and right-side values (C
    and D) used to create the subkeys. */
#define SUBKEY_HALF_BYTES ROUND_TO_BYTES( SUBKEY_HALF_BITS )

/** Number of bytes to store a whole subkey (K_1 .. K_16). */
#define SUBKEY_BYTES ROUND_TO_BYTES( SUBKEY_BITS )

/** Type used to represent a block to encrypt or decrypt with DES. */
typedef struct
{
    /** Sequence of bytes in the block. */
    byte data[ BLOCK_BYTES ];

    /** Number of bytes currently in the data array (e.g., the last block in a file could
        be shorter. */
    int len;
} DESBlock;

/**
    Program that takes in the key name and adds the name in byte formate to an array
    @param key is the array that the keyname char needs to be copied into
    @param textKey is the string key name that needs to be entered into the key array
 */
void prepareKey( byte key[ BLOCK_BYTES ], char const *textKey );

/**
    Program that gets the bit from the data array based on the index passed in it
    @param data is the array of bytes in which a bit needs to be retrived from
    @param idx is the index at which the bit needs to be retrived.
    @return int which is the bit from the data array
 */
int getBit( byte const data[], int idx );

/** 
    Program that replaces the bit at the index in the data with the value passed in.
    @param data is the array of bytes that the bit needs to be replaced in
    @param idx is the index at which the bit needs to be replaced
    @param val is the value of the bit that needs to be replaced in the data array
 */
void putBit( byte data[], int idx, int val );

/**
    Program that permutes the input array of bytes using a perm array and stores it in the output array with n elements
    @param output is the output array that the permuted value is stored in
    @param input is the input array that the permuted value needs to be calculated from
    @param perm is the permutation array used to permute input array
    @param n is the n bits that need to be permuted.
 */
void permute( byte output[], byte const input[], int const perm[], int n );

/**
    Program that generates subkeys based on the key passed in by the user
    @param K is the 2D array that contains arrays of the subkeys generated from the key passed in
    @param key is the array of bytes that represents the key name
 */
void generateSubkeys( byte K[ ROUND_COUNT ][ SUBKEY_BYTES ], byte const key[ BLOCK_BYTES ] );

/**
    Program that gets the four bit value from the sBox based on the input of subkeys
    @param output is the array that contains the four bit value from the sBoxTable
    @param input is the array of bytes that contains a subkey at a time
    @param idx is the index at which the start needs to be to get the six bit value used to calculate four bit in sBoxTable
 */
void sBox( byte output[ 1 ], byte const input[ SUBKEY_BYTES ], int idx );

/**
    Program that gets the result array based on the custom R value and K subkeys array
    @param result is the array that contains encrypted value 
    @param R is the custom array used to create the result array of bytes
    @param K is the subkey array used to create the result array of bytes
 */
void fFunction( byte result[ BLOCK_HALF_BYTES ], byte const R[ BLOCK_HALF_BYTES ], byte const K[ SUBKEY_BYTES ] );


/**
    Program that encrypts the the input file and stores it in the block->data array of custom struct
    @param block is the pointer to the block struct that contains the encrypted data
    @param K is the 2D array of subkeys used to encrypt data and store it
 */
void encryptBlock( DESBlock *block, byte const K[ ROUND_COUNT ][ SUBKEY_BYTES ] );

/**
    Program that decrypts the data from file text and stores it in the block struct data array
    @param block is the pointer to the block in the struct that contains the decrypted data
    @param K is the array of subkeys used to decrypt the cipher file
 */
void decryptBlock( DESBlock *block, byte const K[ ROUND_COUNT ][ SUBKEY_BYTES ] );
