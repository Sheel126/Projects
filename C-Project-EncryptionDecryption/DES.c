/** 
    @file DES.c
    @author Sheel Patel (scpatel6)
    Implementation of the DES algorithm.
*/

#include "DES.h"
#include "DESMagic.h"
#include <string.h>
#include <stdio.h>


/** Max length for how many bytes can be stored at a time */
#define MAX_LEN 8

/** Value for index 2 */
#define VAL_FOR_INDEX_TWO 2

/** Value for index 4 */
#define VAL_FOR_INDEX_FOUR 4

/** Value for index 6 */
#define VAL_FOR_INDEX_SIX 6

/** Value for shift by 24 bit */
#define VAL_FOR_SHIFT_TWO_FOUR 24

/** Value for shift by 16 bit */
#define VAL_FOR_SHIFT_ONE_SIX 16

/** Value for shift by 28 bit */
#define VAL_FOR_SHIFT_TWO_EIGHT 28

/** Value for shift by 32 bit */
#define VAL_FOR_SHIFT_THREE_TWO 32

/** Value for shift by 40 bit */
#define VAL_FOR_SHIFT_FOUR_ZERO 40

/** Value for shift by 27 bit */
#define VAL_FOR_SHIFT_TWENTY_SEVEN 27

/** Value for shift by 48 bit */
#define VAL_FOR_SHIFT_FOUR_EIGHT 48

/** Value for shift by 64 bit */
#define VAL_FOR_SHIFT_SIX_FOUR 64

/** Hex value 0x80 */
#define HEX_0X80 0x80


/** Hex value 0xFE */
#define HEX_0XFE 0xFE

/** Hex value 0x7F */
#define HEX_0X7F 0x7F

/** Hex value 0xBF */
#define HEX_0XBF 0xBF

/** Hex value 0xDF */
#define HEX_0XDF 0xDF

/** Hex value 0xEF */
#define HEX_0XEF 0xEF

/** Hex value 0xF7 */
#define HEX_0XF7 0xF7

/** Hex value 0xFB */
#define HEX_0XFB 0xFB

/** Hex value 0xFD */
#define HEX_0XFD 0xFD

/** Hex value 0x40 */
#define HEX_0X40 0x40

/** Hex value 0x20 */
#define HEX_0X20 0x20

/** Hex value 0x10 */
#define HEX_0X10 0x10

/** Hex value 0x08 */
#define HEX_0X08 0x08

/** Hex value 0x04 */
#define HEX_0X04 0x04

/** Hex value 0x02 */
#define HEX_0X02 0x02

/** Hex value 0xF0 */
#define HEX_0XF0 0xF0

/** Hex value 0x1E */
#define HEX_0X1E 0x1E

/** Hex value 0xC0000000 */
#define HEX_0XC0000000 0xC0000000

/** Hex value 0x80000000 */
#define HEX_0X80000000 0x80000000

/** Hex value 0xFF000000 */
#define HEX_0XFF000000 0xFF000000

/** Hex value 0x00FF0000 */
#define HEX_0X00FF0000 0x00FF0000

/** Hex value 0x0000FF00 */
#define HEX_0X0000FF00 0x0000FF00

/** Hex value 0x000000FF */
#define HEX_0X000000FF 0x000000FF


/** Hex value 0xFF0000000000 */
#define HEX_0XFF0000000000 0xFF0000000000

/** Hex value 0x00FF00000000 */
#define HEX_0X00FF00000000 0x00FF00000000

/** Hex value 0x0000FF000000 */
#define HEX_0X0000FF000000 0x0000FF000000

/** Hex value 0x000000FF0000 */
#define HEX_0X000000FF0000 0x000000FF0000

/** Hex value 0x00000000FF00 */
#define HEX_0X00000000FF00 0x00000000FF00

/** Hex value 0x0000000000FF */
#define HEX_0X0000000000FF 0x0000000000FF


/**
    Program that takes in the key name and adds the name in byte formate to an array
    @param key is the array that the keyname char needs to be copied into
    @param textKey is the string key name that needs to be entered into the key array
 */
void prepareKey( byte key[ BLOCK_BYTES ], char const *textKey )
{
    int len = strlen( textKey );
    // for instance if that is bigger than 64 its error

    if (len > MAX_LEN) {
        // problem
    }
    for ( int i = 0; i < MAX_LEN; i++ ) {
        if ( i >= len ) {
            // pad with o bytes
            key[ i ] = 0x00;
        } else {
            key[ i ] = textKey[ i ];
        }
    }
}

/**
    Program that gets the bit from the data array based on the index passed in it
    @param data is the array of bytes in which a bit needs to be retrived from
    @param idx is the index at which the bit needs to be retrived.
    @return int which is the bit from the data array
 */
int getBit( byte const data[], int idx )
{
    int otherIdx = idx;
    if ( idx % MAX_LEN == 0 ) {
        otherIdx = ( idx / MAX_LEN ) - 1;
    } else {
        otherIdx = idx / MAX_LEN;
    }

    // other index is right, the bit we need is index
    int indexToLookFor = idx % MAX_LEN;

    if ( indexToLookFor == 0 ) {
        if ( ( data[ otherIdx ] & 0x01 ) == 0x01) {
            return 1;
        } else {
            return 0;
        }
    }

    byte shiftedByte = 0x00;
    //printf("Shifted keys: %d\n", data[otherIdx]);
    shiftedByte = ( data[ otherIdx ] & ( HEX_0X80 >> ( indexToLookFor - 1 ) ) ) >> ( MAX_LEN - 1 - indexToLookFor + 1 );
    
    if ( shiftedByte == 0x01 ) {
        return 1;
    } else {
        return 0;
    }
}

/** 
    Program that replaces the bit at the index in the data with the value passed in.
    @param data is the array of bytes that the bit needs to be replaced in
    @param idx is the index at which the bit needs to be replaced
    @param val is the value of the bit that needs to be replaced in the data array
 */
void putBit( byte data[], int idx, int val )
{
    int otherIdx = idx;
    if ( idx % MAX_LEN == 0 ) {
        otherIdx = ( idx / MAX_LEN ) - 1;
    } else {
        otherIdx = idx / MAX_LEN;
    }

    int indexToLookFor = idx % MAX_LEN;

    // easy way out --> check each case and make a new hex for that like 11101111 would be for 4

    if ( val == 0 ) {
        if ( indexToLookFor == 0 ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XFE;
        } else if ( indexToLookFor == 1 ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0X7F;
        } else if ( indexToLookFor == VAL_FOR_INDEX_TWO ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XBF;
        } else if ( indexToLookFor == VAL_FOR_INDEX_TWO + 1 ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XDF;
        } else if ( indexToLookFor == VAL_FOR_INDEX_FOUR ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XEF;
        } else if ( indexToLookFor == VAL_FOR_INDEX_FOUR + 1 ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XF7;
        } else if ( indexToLookFor == VAL_FOR_INDEX_SIX ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XFB;
        } else if ( indexToLookFor == MAX_LEN - 1 ) {
            data[ otherIdx ] = data[ otherIdx ] & HEX_0XFD;
        }
        
    } else {
         if ( indexToLookFor == 0 ) {
            data[ otherIdx ] = data[ otherIdx ] | 0x01;
        } else if ( indexToLookFor == 1 ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X80;
        } else if ( indexToLookFor == VAL_FOR_INDEX_TWO ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X40;
        } else if ( indexToLookFor == VAL_FOR_INDEX_TWO + 1 ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X20;
        } else if ( indexToLookFor == VAL_FOR_INDEX_FOUR ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X10;
        } else if ( indexToLookFor == VAL_FOR_INDEX_FOUR + 1 ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X08;
        } else if ( indexToLookFor == VAL_FOR_INDEX_SIX ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X04;
        } else if ( indexToLookFor == MAX_LEN - 1 ) {
            data[ otherIdx ] = data[ otherIdx ] | HEX_0X02;
        }

    }
}

/**
    Program that permutes the input array of bytes using a perm array and stores it in the output array with n elements
    @param output is the output array that the permuted value is stored in
    @param input is the input array that the permuted value needs to be calculated from
    @param perm is the permutation array used to permute input array
    @param n is the n bits that need to be permuted.
 */
void permute( byte output[], byte const input[], int const perm[], int n )
{
    // get the digit itself at index input[i] then put it into output



    int size = n / MAX_LEN;
    if ( n % MAX_LEN != 0 ) {
        output[ size ] = 0x00;
    }
    for ( int i = 0; i < n; i++ ) {
        int bit = getBit( input, perm[ i ] );
        putBit( output, i + 1, bit );
        size++;
    }



}

/**
    Program that helps generate subkeys using the perm and the index at which the subkeys need to be generated at
    @param perm is the permute array used to permute some input byte array.
    @param i is the index of the subkey being generated.
 */
void static generateKeysHelper( byte perm[], int i ) {
     int leftShift = perm[ 0 ] << VAL_FOR_SHIFT_TWO_FOUR;
        leftShift = leftShift | ( perm[ 1 ] << VAL_FOR_SHIFT_ONE_SIX );
        leftShift = leftShift | ( perm[ VAL_FOR_INDEX_TWO ] << MAX_LEN );
        leftShift = leftShift | perm[ VAL_FOR_INDEX_TWO + 1 ];
        

        int tempShift;
        // store first value or second value
        if ( subkeyShiftSchedule[ i ] == VAL_FOR_INDEX_TWO ) {
            tempShift = ( leftShift & HEX_0XC0000000 ) >> ( VAL_FOR_SHIFT_TWENTY_SEVEN - 1 );
        } else {
            tempShift = ( leftShift & HEX_0X80000000 ) >> VAL_FOR_SHIFT_TWENTY_SEVEN;
        }

        leftShift = leftShift << subkeyShiftSchedule[ i ];
        leftShift = leftShift | tempShift;
        //printf( "%X\n", leftShift );

        // we have updated left right. Now we gotta update leftPerm to include this

        byte temp0 = ( leftShift & HEX_0XFF000000 ) >> VAL_FOR_SHIFT_TWO_FOUR;
        byte temp1 = ( leftShift & HEX_0X00FF0000 ) >> VAL_FOR_SHIFT_ONE_SIX;
        byte temp2 = ( leftShift & HEX_0X0000FF00 ) >> MAX_LEN;
        byte temp3 = ( leftShift & HEX_0X000000FF ) >> 0;
        //printf( "%X\n", temp0 );
        perm[ 0 ] = temp0;
        perm[ 1 ] = temp1;
        perm[ VAL_FOR_INDEX_TWO ] = temp2;
        perm[ VAL_FOR_INDEX_TWO + 1 ] = temp3;  
}

/**
    Program that generates subkeys based on the key passed in by the user
    @param K is the 2D array that contains arrays of the subkeys generated from the key passed in
    @param key is the array of bytes that represents the key name
 */
void generateSubkeys( byte K[ ROUND_COUNT ][ SUBKEY_BYTES ], byte const key[ BLOCK_BYTES ] )
{
    // generate left subkey with perm and right with perm
    // then run a loop where we shifting based on shift schedule then combine C and D then another permute and then add it

   

    byte leftPerm[ VAL_FOR_INDEX_FOUR ] = { 0, 0, 0, 0};
    byte rightPerm[ VAL_FOR_INDEX_FOUR ] = { 0, 0, 0, 0 };
    permute( leftPerm, key, leftSubkeyPerm, VAL_FOR_SHIFT_TWO_EIGHT );

    permute( rightPerm, key, rightSubkeyPerm, VAL_FOR_SHIFT_TWO_EIGHT );


    for ( int i = 1; i < VAL_FOR_SHIFT_ONE_SIX + 1; i++ ) {
        generateKeysHelper( leftPerm, i );
        generateKeysHelper( rightPerm, i );


        byte combined[ MAX_LEN - 1 ] = { 0, 0, 0, 0, 0, 0, 0 };

        combined[ 0 ] = leftPerm[ 0 ];
        combined[ 1 ] = leftPerm[ 1 ];
        combined[ VAL_FOR_INDEX_TWO ] = leftPerm[ VAL_FOR_INDEX_TWO ];

        byte firstFour = ( rightPerm[ 0 ] & HEX_0XF0 ) >> VAL_FOR_INDEX_FOUR;

        byte lastFourOne = ( rightPerm[ 0 ] & 0x0F ) << VAL_FOR_INDEX_FOUR;
        byte firstFourTwo = ( rightPerm[ 1 ] & HEX_0XF0 ) >> VAL_FOR_INDEX_FOUR;

        byte lastFourTwo = ( rightPerm[ 1 ] & 0x0F ) << VAL_FOR_INDEX_FOUR;
        byte firstFourThree = ( rightPerm[ VAL_FOR_INDEX_TWO ] & HEX_0XF0 ) >> VAL_FOR_INDEX_FOUR;

        byte lastFourThree = ( rightPerm[ VAL_FOR_INDEX_TWO ] & 0x0F ) << VAL_FOR_INDEX_FOUR;
        byte firstFourFour = ( rightPerm[ VAL_FOR_INDEX_TWO + 1 ] & HEX_0XF0 ) >> VAL_FOR_INDEX_FOUR;

        combined[ VAL_FOR_INDEX_TWO + 1 ] = leftPerm[ VAL_FOR_INDEX_TWO + 1 ] | firstFour;
        combined[ VAL_FOR_INDEX_FOUR ] = lastFourOne | firstFourTwo;
        combined[ VAL_FOR_INDEX_FOUR + 1 ] = lastFourTwo | firstFourThree;
        combined[ VAL_FOR_INDEX_SIX ] = lastFourThree | firstFourFour;
        permute( K[ i ], combined, subkeyPerm, VAL_FOR_SHIFT_FOUR_EIGHT );
    }

    // for (int i = 1; i < 2; i++) {
    //     for (int j = 0; j < 6; j++) {
    //         printf("%X ", K[i][j]);
    //     }
    //     printf("\n");
    // }


}

/**
    Program that gets the four bit value from the sBox based on the input of subkeys
    @param output is the array that contains the four bit value from the sBoxTable
    @param input is the array of bytes that contains a subkey at a time
    @param idx is the index at which the start needs to be to get the six bit value used to calculate four bit in sBoxTable
 */
void sBox( byte output[ 1 ], byte const input[ SUBKEY_BYTES ], int idx )
{
    // idx * 6 + 1 to idx * 6 + 6 = B from the input. We get that and use first and last to get row and middle four
    // to get positionin 2D array for output[0] top 4 bits

    int start = idx * VAL_FOR_INDEX_SIX + 1;
    //int end = idx * 6 + 6;
    // get and then shift constatly to make sure its good
    byte val1 = getBit( input, start );
    byte val2 = getBit( input, start + 1 );
    byte val3 = getBit( input, start + VAL_FOR_INDEX_TWO );
    byte val4 = getBit( input, start + VAL_FOR_INDEX_TWO + 1 );
    byte val5 = getBit( input, start + VAL_FOR_INDEX_FOUR );
    byte val6 = getBit( input, start + VAL_FOR_INDEX_FOUR + 1 );

    byte val = 0x00;
    val = val | val1;
    val = val << 1;
    val = val | val2;
    val = val << 1;
    val = val | val3;
    val = val << 1;
    val = val | val4;
    val = val << 1;
    val = val | val5;
    val = val << 1;
    val = val | val6;

    

    // extract 1st and last
    byte first = ( val & HEX_0X20 ) >> ( VAL_FOR_INDEX_FOUR + 1 );
    byte last = ( val & 0x01 );
    int row = ( first << 1 ) | last;

    int column = ( val & HEX_0X1E ) >> 1;
    int returnVal = sBoxTable[ idx ][ row ][ column ];
   
    byte returnValTwo = ( returnVal & 0x0000000F ) << VAL_FOR_INDEX_FOUR;
    //printf( "%X\n", returnValTwo );
    output[ 0 ] = returnValTwo; 

}

/**
    Program that gets the result array based on the custom R value and K subkeys array
    @param result is the array that contains encrypted value 
    @param R is the custom array used to create the result array of bytes
    @param K is the subkey array used to create the result array of bytes
 */
void fFunction( byte result[ BLOCK_HALF_BYTES ], byte const R[ BLOCK_HALF_BYTES ], byte const K[ SUBKEY_BYTES ] )
{
    byte Rpermute[ VAL_FOR_INDEX_SIX ];
    permute( Rpermute, R, expandedRSelector, VAL_FOR_SHIFT_FOUR_EIGHT );

    //printf( "R: %X %X %X %X\n", R[0], R[1], R[2], R[3] );
    //printf( "R: %X %X %X %X %X %X\n", Rpermute[0], Rpermute[1], Rpermute[2], Rpermute[3], Rpermute[4], Rpermute[5] );

    // need two longs for exclusive OR
    unsigned long long rLong = 0x000000000000;
    rLong = (unsigned long long)Rpermute[ 0 ] << VAL_FOR_SHIFT_FOUR_ZERO;
    rLong = rLong | ( (unsigned long long)Rpermute[ 1 ] << VAL_FOR_SHIFT_THREE_TWO );
    rLong = rLong | ( (unsigned long long)Rpermute[ VAL_FOR_INDEX_TWO ] << VAL_FOR_SHIFT_TWO_FOUR );
    rLong = rLong | ( (unsigned long long)Rpermute[ VAL_FOR_INDEX_TWO + 1 ] << VAL_FOR_SHIFT_ONE_SIX );
    rLong = rLong | ( (unsigned long long)Rpermute[ VAL_FOR_INDEX_FOUR ] << MAX_LEN );
    rLong = rLong | ( (unsigned long long)Rpermute[ VAL_FOR_INDEX_FOUR + 1 ] << 0);

    // printf( "long1: %llX\n", rLong );

    unsigned long long kLong = 0x000000000000;
    kLong = (unsigned long long)K[ 0 ] << VAL_FOR_SHIFT_FOUR_ZERO;
    kLong = kLong | ( (unsigned long long)K[ 1 ] << VAL_FOR_SHIFT_THREE_TWO );
    kLong = kLong | ( (unsigned long long)K[ VAL_FOR_INDEX_TWO ] << VAL_FOR_SHIFT_TWO_FOUR );
    kLong = kLong | ( (unsigned long long)K[ VAL_FOR_INDEX_TWO + 1 ] << VAL_FOR_SHIFT_ONE_SIX );
    kLong = kLong | ( (unsigned long long)K[ VAL_FOR_INDEX_FOUR ] << MAX_LEN );
    kLong = kLong | ( (unsigned long long)K[ VAL_FOR_INDEX_FOUR + 1 ] );

    // printf( "long: %llX\n", kLong );

    unsigned long long exclusiveOR = kLong ^ rLong;
    //printf( "%llX\n", exclusiveOR );

    byte temp0 = ( exclusiveOR & HEX_0XFF0000000000 ) >> VAL_FOR_SHIFT_FOUR_ZERO;
    byte temp1 = ( exclusiveOR & HEX_0X00FF00000000 ) >> VAL_FOR_SHIFT_THREE_TWO;
    byte temp2 = ( exclusiveOR & HEX_0X0000FF000000 ) >> VAL_FOR_SHIFT_TWO_FOUR;
    byte temp3 = ( exclusiveOR & HEX_0X000000FF0000 ) >> VAL_FOR_SHIFT_ONE_SIX;
    byte temp4 = ( exclusiveOR & HEX_0X00000000FF00 ) >> MAX_LEN;
    byte temp5 = ( exclusiveOR & HEX_0X0000000000FF ) >> 0;

    byte newPermutedList[ VAL_FOR_INDEX_SIX ];
    newPermutedList[ 0 ] = temp0;
    newPermutedList[ 1 ] = temp1;
    newPermutedList[ VAL_FOR_INDEX_TWO ] = temp2;
    newPermutedList[ VAL_FOR_INDEX_TWO + 1 ] = temp3;
    newPermutedList[ VAL_FOR_INDEX_FOUR ] = temp4;
    newPermutedList[ VAL_FOR_INDEX_FOUR + 1 ] = temp5;

    //printf( "R: %X %X %X %X %X %X\n", newPermutedList[0], newPermutedList[1], newPermutedList[2], newPermutedList[3], 
      //      newPermutedList[4], newPermutedList[5] );

    byte beforePerm[ VAL_FOR_INDEX_FOUR ];
    byte output[ 1 ];
    byte output2[ 1 ];
    sBox( output, newPermutedList, 0 );
    sBox( output2, newPermutedList, 1 );

    byte in = ( output[ 0 ] ) | ( output2[ 0 ] >> VAL_FOR_INDEX_FOUR );
    beforePerm[ 0 ] = in;

    sBox( output, newPermutedList, VAL_FOR_INDEX_TWO );
    sBox( output2, newPermutedList, VAL_FOR_INDEX_TWO + 1 );

    in = ( output[ 0 ] ) | ( output2[ 0 ] >> VAL_FOR_INDEX_FOUR );
    beforePerm[ 1 ] = in;

    sBox( output, newPermutedList, VAL_FOR_INDEX_FOUR );
    sBox( output2, newPermutedList, VAL_FOR_INDEX_FOUR + 1 );

    in = ( output[ 0 ] ) | ( output2[ 0 ] >> VAL_FOR_INDEX_FOUR );
    beforePerm[ VAL_FOR_INDEX_TWO ] = in;

    sBox( output, newPermutedList, VAL_FOR_INDEX_SIX );
    sBox( output2, newPermutedList, MAX_LEN - 1 );

    in = ( output[ 0 ] ) | ( output2[ 0 ] >> VAL_FOR_INDEX_FOUR );
    beforePerm[ VAL_FOR_INDEX_TWO + 1 ] = in;

    //printf( "%X %X %X %X\n", beforePerm[0], beforePerm[1], beforePerm[2], beforePerm[3] );

    permute( result, beforePerm, fFunctionPerm, VAL_FOR_SHIFT_THREE_TWO );
    


}

/**
    Program that encrypts the the input file and stores it in the block->data array of custom struct
    @param block is the pointer to the block struct that contains the encrypted data
    @param K is the 2D array of subkeys used to encrypt data and store it
 */
void encryptBlock( DESBlock *block, byte const K[ ROUND_COUNT ][ SUBKEY_BYTES ] )
{
    byte L[] = { 0, 0, 0, 0 };
    byte R[] = { 0, 0, 0, 0 };
    permute( L, block->data, leftInitialPerm, VAL_FOR_SHIFT_THREE_TWO );
    permute( R, block->data, rightInitialPerm, VAL_FOR_SHIFT_THREE_TWO );
    
    for ( int i = 1; i < VAL_FOR_SHIFT_ONE_SIX + 1; i++ ) {
        byte rightResult[] = { 0, 0, 0, 0 };
        fFunction( rightResult, R, K[ i ] );

        // Ex OR with L and rightResult
        int rightInt = 0x00000000;
        rightInt = rightResult[ 0 ] << VAL_FOR_SHIFT_TWO_FOUR;
        rightInt = rightInt | ( rightResult[ 1 ] << VAL_FOR_SHIFT_ONE_SIX );
        rightInt = rightInt | ( rightResult[ VAL_FOR_INDEX_TWO ] << MAX_LEN );
        rightInt = rightInt | ( rightResult[ VAL_FOR_INDEX_TWO + 1 ] );

        int leftInt =0x00000000;
        leftInt = L[ 0 ] << VAL_FOR_SHIFT_TWO_FOUR;
        leftInt = leftInt | ( L[ 1 ] << VAL_FOR_SHIFT_ONE_SIX );
        leftInt = leftInt | ( L[ VAL_FOR_INDEX_TWO ] << MAX_LEN );
        leftInt = leftInt | ( L[ VAL_FOR_INDEX_TWO + 1 ] );

        int combineLeftRight = rightInt ^ leftInt;

        // the combineLeftRight goes into the new right
        // before that we must update L to be old right

        L[ 0 ] = R[ 0 ];
        L[ 1 ] = R[ 1 ];
        L[ VAL_FOR_INDEX_TWO ] = R[ VAL_FOR_INDEX_TWO ];
        L[ VAL_FOR_INDEX_TWO + 1 ] = R[ VAL_FOR_INDEX_TWO + 1 ];

        byte temp0 = ( combineLeftRight & HEX_0XFF000000 ) >> VAL_FOR_SHIFT_TWO_FOUR;
        byte temp1 = ( combineLeftRight & HEX_0X00FF0000 ) >> VAL_FOR_SHIFT_ONE_SIX;
        byte temp2 = ( combineLeftRight & HEX_0X0000FF00 ) >> MAX_LEN;
        byte temp3 = ( combineLeftRight & HEX_0X000000FF ) >> 0;

        R[ 0 ] = temp0;
        R[ 1 ] = temp1;
        R[ VAL_FOR_INDEX_TWO ] = temp2;
        R[ VAL_FOR_INDEX_TWO + 1 ] = temp3;
        // we repeat 16 times
    }

    // we now have R and L we want
    // combine into a block of 64 bits

    byte temp[ MAX_LEN ] = { 0, 0, 0, 0, 0, 0, 0, 0 };

    temp[ 0 ] = R[ 0 ];
    temp[ 1 ] = R[ 1 ];
    temp[ VAL_FOR_INDEX_TWO ] = R[ VAL_FOR_INDEX_TWO ];
    temp[ VAL_FOR_INDEX_TWO + 1 ] = R[ VAL_FOR_INDEX_TWO + 1 ];

    temp[ VAL_FOR_INDEX_FOUR ] = L[ 0 ];
    temp[ VAL_FOR_INDEX_FOUR + 1 ] = L[ 1 ];
    temp[ VAL_FOR_INDEX_SIX ] = L[ VAL_FOR_INDEX_TWO ];
    temp[ MAX_LEN - 1 ] = L[ VAL_FOR_INDEX_TWO + 1 ];

    permute( block->data, temp, finalPerm, VAL_FOR_SHIFT_SIX_FOUR );

}

/**
    Program that decrypts the data from file text and stores it in the block struct data array
    @param block is the pointer to the block in the struct that contains the decrypted data
    @param K is the array of subkeys used to decrypt the cipher file
 */
void decryptBlock( DESBlock *block, byte const K[ ROUND_COUNT ][ SUBKEY_BYTES ] )
{
    byte L[] = { 0, 0, 0, 0 };
    byte R[] = { 0, 0, 0, 0 };
    permute( L, block->data, leftInitialPerm, VAL_FOR_SHIFT_THREE_TWO );
    permute( R, block->data, rightInitialPerm, VAL_FOR_SHIFT_THREE_TWO );
    
    for ( int i = VAL_FOR_SHIFT_ONE_SIX; i >= 1; i-- ) {
        byte rightResult[] = { 0, 0, 0, 0 };
        fFunction( rightResult, R, K[ i ] );

        // Ex OR with L and rightResult
        int rightInt = 0x00000000;
        rightInt = rightResult[ 0 ] << VAL_FOR_SHIFT_TWO_FOUR;
        rightInt = rightInt | ( rightResult[ 1 ] << VAL_FOR_SHIFT_ONE_SIX );
        rightInt = rightInt | ( rightResult[ VAL_FOR_INDEX_TWO ] << MAX_LEN );
        rightInt = rightInt | ( rightResult[ VAL_FOR_INDEX_TWO + 1 ] );

        int leftInt =0x00000000;
        leftInt = L[ 0 ] << VAL_FOR_SHIFT_TWO_FOUR;
        leftInt = leftInt | ( L[ 1 ] << VAL_FOR_SHIFT_ONE_SIX );
        leftInt = leftInt | ( L[ VAL_FOR_INDEX_TWO ] << MAX_LEN );
        leftInt = leftInt | ( L[ VAL_FOR_INDEX_TWO + 1 ] );

        int combineLeftRight = rightInt ^ leftInt;

        // the combineLeftRight goes into the new right
        // before that we must update L to be old right

        L[ 0 ] = R[ 0 ];
        L[ 1 ] = R[ 1 ];
        L[ VAL_FOR_INDEX_TWO ] = R[ VAL_FOR_INDEX_TWO ];
        L[ VAL_FOR_INDEX_TWO + 1 ] = R[ VAL_FOR_INDEX_TWO + 1 ];

        byte temp0 = ( combineLeftRight & HEX_0XFF000000 ) >> VAL_FOR_SHIFT_TWO_FOUR;
        byte temp1 = ( combineLeftRight & HEX_0X00FF0000 ) >> VAL_FOR_SHIFT_ONE_SIX;
        byte temp2 = ( combineLeftRight & HEX_0X0000FF00 ) >> MAX_LEN;
        byte temp3 = ( combineLeftRight & HEX_0X000000FF ) >> 0;

        R[ 0 ] = temp0;
        R[ 1 ] = temp1;
        R[ VAL_FOR_INDEX_TWO ] = temp2;
        R[ VAL_FOR_INDEX_TWO + 1 ] = temp3;
        // we repeat 16 times
    }

    // we now have R and L we want
    // combine into a block of 64 bits

    byte temp[ MAX_LEN ] = { 0, 0, 0, 0, 0, 0, 0, 0 };

    temp[ 0 ] = R[ 0 ];
    temp[ 1 ] = R[ 1 ];
    temp[ VAL_FOR_INDEX_TWO ] = R[ VAL_FOR_INDEX_TWO ];
    temp[ VAL_FOR_INDEX_TWO + 1 ] = R[ VAL_FOR_INDEX_TWO + 1 ];

    temp[ VAL_FOR_INDEX_FOUR ] = L[ 0 ];
    temp[ VAL_FOR_INDEX_FOUR + 1 ] = L[ 1 ];
    temp[ VAL_FOR_INDEX_SIX ] = L[ VAL_FOR_INDEX_TWO ];
    temp[ MAX_LEN - 1 ] = L[ VAL_FOR_INDEX_TWO + 1 ];

    permute( block->data, temp, finalPerm, VAL_FOR_SHIFT_SIX_FOUR );
}
