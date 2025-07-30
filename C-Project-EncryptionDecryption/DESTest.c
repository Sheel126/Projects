#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include "DES.h"

/** Number of tests we should have, if they're all turned on. */
#define EXPECTED_TOTAL 46

/** Total number or tests we tried. */
static int totalTests = 0;

/** Number of test cases passed. */
static int passedTests = 0;

/** Macro to check the condition on a test case, keep counts of
    passed/failed tests and report a message if the test fails. */
#define TestCase( conditional ) {\
  totalTests += 1; \
  if ( conditional ) { \
    passedTests += 1; \
  } else { \
    printf( "**** Failed unit test on line %d of %s\n", __LINE__, __FILE__ );    \
  } \
}

/** Return true if A and B contain the same sequence of n bytes. */
bool cmpBytes( byte const A[], byte const B[], int n )
{
  for ( int i = 0; i < n; i++ )
    if ( A[ i ] != B[ i ] )
      return false;
  return true;
}

int main()
{
  // As you finish parts of your implementation, move this directive
  // down past the blocks of code below.  That will enable tests of
  // various functions you're expected to implement.


  
  ////////////////////////////////////////////////////////////////////////
  // Test prepareKey()

  {
    char textKey[] = "abc";
    byte key[ BLOCK_BYTES ];

    prepareKey( key, textKey );
    
    // Make sure it got copied and padded with zeros.
    TestCase( cmpBytes( key, (byte []){0x61, 0x62, 0x63, 0x00,
                                       0x00, 0x00, 0x00, 0x00}, 8 ) );
  }
  

  ////////////////////////////////////////////////////////////////////////
  // Test getBit()


  {
    byte data[] = { 0xFF, 0x00, 0x55, 0xAA };

    // Check some positions in this array of bytes.
    TestCase( getBit( data, 1 ) == 1 );
    TestCase( getBit( data, 8 ) == 1 );
    TestCase( getBit( data, 9 ) == 0 );
    TestCase( getBit( data, 16 ) == 0 );
    TestCase( getBit( data, 17 ) == 0 );
    TestCase( getBit( data, 18 ) == 1 );
    TestCase( getBit( data, 31 ) == 1 );
    TestCase( getBit( data, 32 ) == 0 );
  }


  ////////////////////////////////////////////////////////////////////////
  // Test setBit()

  {
    byte data[] = { 0xFF, 0x00, 0x55, 0xAA };

    // Flip the first bit to 0.
    putBit( data, 1, 0 );
    TestCase( data[ 0 ] == 0x7F );
    
    // Flip the 8th bit to 0.
    putBit( data, 8, 0 );
    TestCase( data[ 0 ] == 0x7E );
    
    // No change to bit 5.
    putBit( data, 5, 1 );
    //printf("hex: %X\n", data[0]);
    TestCase( data[ 0 ] == 0x7E );

    // Set bits number 9 and 16
    putBit( data, 9, 1 );
    putBit( data, 16, 1 );
    TestCase( data[ 1 ] == 0x81 );
    
    // Clear bit 17 and set 19 (no change)
    putBit( data, 17, 0 );
    putBit( data, 18, 1 );
    TestCase( data[ 2 ] == 0x55 );
    
    // Clear bit 31 and set 32
    putBit( data, 31, 0 );
    putBit( data, 32, 1 );
    TestCase( data[ 3 ] == 0xA9 );
  }
  
  
  ////////////////////////////////////////////////////////////////////////
  // Test permute()

  {
    byte input[ 2 ] = { 0xBC, 0xD6 };
    int perm[ 16 ] = { 7, 14, 12, 13, 1, 6, 11, 8, 4, 16, 15, 10, 3, 5, 9, 2 };
    byte output[ 2];

    permute( output, input, perm, 16 );
    TestCase( output[ 0 ] == 0x6C );
    TestCase( output[ 1 ] == 0xBE );
  }

  {
    // Try selecting a subset of the bits.
    byte input[ 2 ] = { 0xFF, 0x00 };
    int perm[ 16 ] = { 9, 10, 11, 12, 1, 2, 3, 4, 7, 8 };
    byte output[ 2] = { 0xFF, 0xFF };

    permute( output, input, perm, 10 );
    TestCase( output[ 0 ] == 0x0F );

    // Make sure the last byte gets filled in with zeros.
    TestCase( output[ 1 ] == 0xC0 );
  }

  ////////////////////////////////////////////////////////////////////////
  // Test generateSubkeys()

  {
    // Same example shown in the DES Algorithm Illustrated article.
    byte key[ BLOCK_BYTES ] = { 0x13, 0x34, 0x57, 0x79,
      0x9B, 0xBC, 0xDF, 0xF1 };

    byte K[ ROUND_COUNT ][ SUBKEY_BYTES ];
    generateSubkeys( K, key );

    TestCase( cmpBytes( K[1], (byte []){0x1B, 0x02, 0xEF, 0xFC, 0x70, 0x72 }, 6 ) );
    TestCase( cmpBytes( K[2], (byte []){0x79, 0xAE, 0xD9, 0xDB, 0xC9, 0xE5 }, 6 ) );
    TestCase( cmpBytes( K[3], (byte []){0x55, 0xFC, 0x8A, 0x42, 0xCF, 0x99 }, 6 ) );
    TestCase( cmpBytes( K[4], (byte []){0x72, 0xAD, 0xD6, 0xDB, 0x35, 0x1D }, 6 ) );
    TestCase( cmpBytes( K[5], (byte []){0x7C, 0xEC, 0x07, 0xEB, 0x53, 0xA8 }, 6 ) );
    TestCase( cmpBytes( K[6], (byte []){0x63, 0xA5, 0x3E, 0x50, 0x7B, 0x2F }, 6 ) );
    TestCase( cmpBytes( K[7], (byte []){0xEC, 0x84, 0xB7, 0xF6, 0x18, 0xBC }, 6 ) );
    TestCase( cmpBytes( K[8], (byte []){0xF7, 0x8A, 0x3A, 0xC1, 0x3B, 0xFB }, 6 ) );
    TestCase( cmpBytes( K[9], (byte []){0xE0, 0xDB, 0xEB, 0xED, 0xE7, 0x81 }, 6 ) );
    TestCase( cmpBytes( K[10], (byte []){0xB1, 0xF3, 0x47, 0xBA, 0x46, 0x4F }, 6 ) );
    TestCase( cmpBytes( K[11], (byte []){0x21, 0x5F, 0xD3, 0xDE, 0xD3, 0x86 }, 6 ) );
    TestCase( cmpBytes( K[12], (byte []){0x75, 0x71, 0xF5, 0x94, 0x67, 0xE9 }, 6 ) );
    TestCase( cmpBytes( K[13], (byte []){0x97, 0xC5, 0xD1, 0xFA, 0xBA, 0x41 }, 6 ) );
    TestCase( cmpBytes( K[14], (byte []){0x5F, 0x43, 0xB7, 0xF2, 0xE7, 0x3A }, 6 ) );
    TestCase( cmpBytes( K[15], (byte []){0xBF, 0x91, 0x8D, 0x3D, 0x3F, 0x0A }, 6 ) );
    TestCase( cmpBytes( K[16], (byte []){0xCB, 0x3D, 0x8B, 0x0E, 0x17, 0xF5 }, 6 ) );
  }



  ////////////////////////////////////////////////////////////////////////
  // Test sBox()

  {
    byte B[ 6 ] = { 0x61, 0x17, 0xBA, 0x86, 0x65, 0x27 };
    byte output[ 1 ];

    sBox( output, B, 0 );
    TestCase( output[ 0 ] == 0x50 );
    sBox( output, B, 1 );
    TestCase( output[ 0 ] == 0xC0 );
    sBox( output, B, 2 );
    TestCase( output[ 0 ] == 0x80 );
    sBox( output, B, 3 );
    TestCase( output[ 0 ] == 0x20 );
    sBox( output, B, 4 );
    TestCase( output[ 0 ] == 0xB0 );
    sBox( output, B, 5 );
    TestCase( output[ 0 ] == 0x50 );
    sBox( output, B, 6 );
    TestCase( output[ 0 ] == 0x90 );
    sBox( output, B, 7 );
    TestCase( output[ 0 ] == 0x70 );
  }
  

  ////////////////////////////////////////////////////////////////////////
  // Test fFunction()

  {
    byte R[ 4 ] = { 0xF0, 0xAA, 0xF0, 0xAA };
    byte subkey[ 6 ] = { 0x1B, 0x02, 0xEF, 0xFC, 0x70, 0x72 };
    byte result[ 4 ];

    fFunction( result, R, subkey );
    
    TestCase( cmpBytes( result, (byte []){ 0x23, 0x4A, 0xA9, 0xBB }, 4 ) );
  }

  ////////////////////////////////////////////////////////////////////////
  // Test encryptBlock()

  {
    // Make the same message and subkey array as the DES Algorithm Illustrated article.
    DESBlock block = { { 0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF }, 8 };
    byte K[ ROUND_COUNT ][ SUBKEY_BYTES ] = {
      {0, 0, 0, 0, 0, 0}, // First element not used.
      {0x1B, 0x02, 0xEF, 0xFC, 0x70, 0x72 },
      {0x79, 0xAE, 0xD9, 0xDB, 0xC9, 0xE5 },
      {0x55, 0xFC, 0x8A, 0x42, 0xCF, 0x99 },
      {0x72, 0xAD, 0xD6, 0xDB, 0x35, 0x1D },
      {0x7C, 0xEC, 0x07, 0xEB, 0x53, 0xA8 },
      {0x63, 0xA5, 0x3E, 0x50, 0x7B, 0x2F },
      {0xEC, 0x84, 0xB7, 0xF6, 0x18, 0xBC },
      {0xF7, 0x8A, 0x3A, 0xC1, 0x3B, 0xFB },
      {0xE0, 0xDB, 0xEB, 0xED, 0xE7, 0x81 },
      {0xB1, 0xF3, 0x47, 0xBA, 0x46, 0x4F },
      {0x21, 0x5F, 0xD3, 0xDE, 0xD3, 0x86 },
      {0x75, 0x71, 0xF5, 0x94, 0x67, 0xE9 },
      {0x97, 0xC5, 0xD1, 0xFA, 0xBA, 0x41 },
      {0x5F, 0x43, 0xB7, 0xF2, 0xE7, 0x3A },
      {0xBF, 0x91, 0x8D, 0x3D, 0x3F, 0x0A },
      {0xCB, 0x3D, 0x8B, 0x0E, 0x17, 0xF5 }
    };

    encryptBlock( &block, K );
    
    TestCase( cmpBytes( block.data, (byte []){0x85, 0xE8, 0x13, 0x54,
                                              0x0F, 0x0A, 0xB4, 0x05}, 8 ) );
  }

  ////////////////////////////////////////////////////////////////////////
  // Test decryptBlock()

  {
    // Reverse the example above.
    DESBlock block = { { 0x85, 0xE8, 0x13, 0x54, 0x0F, 0x0A, 0xB4, 0x05 }, 8 };
    byte K[ ROUND_COUNT ][ SUBKEY_BYTES ] = {
      {0, 0, 0, 0, 0, 0}, // First element not used.
      {0x1B, 0x02, 0xEF, 0xFC, 0x70, 0x72 },
      {0x79, 0xAE, 0xD9, 0xDB, 0xC9, 0xE5 },
      {0x55, 0xFC, 0x8A, 0x42, 0xCF, 0x99 },
      {0x72, 0xAD, 0xD6, 0xDB, 0x35, 0x1D },
      {0x7C, 0xEC, 0x07, 0xEB, 0x53, 0xA8 },
      {0x63, 0xA5, 0x3E, 0x50, 0x7B, 0x2F },
      {0xEC, 0x84, 0xB7, 0xF6, 0x18, 0xBC },
      {0xF7, 0x8A, 0x3A, 0xC1, 0x3B, 0xFB },
      {0xE0, 0xDB, 0xEB, 0xED, 0xE7, 0x81 },
      {0xB1, 0xF3, 0x47, 0xBA, 0x46, 0x4F },
      {0x21, 0x5F, 0xD3, 0xDE, 0xD3, 0x86 },
      {0x75, 0x71, 0xF5, 0x94, 0x67, 0xE9 },
      {0x97, 0xC5, 0xD1, 0xFA, 0xBA, 0x41 },
      {0x5F, 0x43, 0xB7, 0xF2, 0xE7, 0x3A },
      {0xBF, 0x91, 0x8D, 0x3D, 0x3F, 0x0A },
      {0xCB, 0x3D, 0x8B, 0x0E, 0x17, 0xF5 }
    };

    decryptBlock( &block, K );
    
    TestCase( cmpBytes( block.data, (byte []){0x01, 0x23, 0x45, 0x67,
                                              0x89, 0xAB, 0xCD, 0xEF}, 8 ) );
  }

  // Once you move the #ifdef DISABLE_TESTS to here, you've enabled
  // all the tests.
#ifdef DISABLE_TESTS
#endif
  
 // Report a message if some tests are still disabled.
  if ( totalTests < EXPECTED_TOTAL )
    printf( "** %d of %d tests currently enabled.\n", totalTests,
            EXPECTED_TOTAL );

  //printf( "Passed tests so far: %d\n", passedTests );
  // Exit successfully if all tests are enabled and they all pass.
  if ( passedTests != EXPECTED_TOTAL )
    return EXIT_FAILURE;
  else
    return EXIT_SUCCESS;
}
