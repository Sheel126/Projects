/** 
    @file DESMagic.h
    @author dbsturgi
    Magic numbers and constants used in the DES algorithm.
*/

/** Type used to represent a byte. */
typedef unsigned char byte;

/** Number of rounds and subkeys.  This is one larger than so we can
    index the round variables and the subkeys starting from 1 up to
    and including 16. */
#define ROUND_COUNT 17

/** Number of bits in the left-side and right-side values (C and D)
    used to create the subkeys. */
#define SUBKEY_HALF_BITS 28

/** Number of bits in the a whole subkey (K_1 .. K_16) */
#define SUBKEY_BITS 48

/** Permutation table for creating C_0 used in subkey generation.
    This is the first 28 elements from the PC-1 table in DES
    Algorithm Illustrated. */
extern int leftSubkeyPerm[ SUBKEY_HALF_BITS ];

/** Permutation table for creating D_0 using in subkey generation.
    This is the second 28 elements from the PC-1 table in DES
    Algorithm Illustrated. */
extern int rightSubkeyPerm[ SUBKEY_HALF_BITS ];

/** Sequence of shift operations applied to C_i and D_i during subkey
    generation.  This table doesn't have a name in the DES
    Algorithm Illustrated article. */
extern int subkeyShiftSchedule[ ROUND_COUNT ];

/** Permutation table for selecting bits for each 48-bit subkey.  This
    is PC-2 table in DES Algorithm Illustrated. */
extern int subkeyPerm[ SUBKEY_BITS ];

/** Number of bits in a DES block. */
#define BLOCK_BITS 64

/** Number of bits in half a block (L and R). */
#define BLOCK_HALF_BITS 32

/** Permutation table for creating L_0 during encryption.
    This is the first 32 elements from the IP table in DES
    Algorithm Illustrated. */
extern int leftInitialPerm[ BLOCK_HALF_BITS ];

/** Permutation table for creating R_0 during encryption.
    This is the second 32 elements from the IP table in DES
    Algorithm Illustrated. */
extern int rightInitialPerm[ BLOCK_HALF_BITS ];

/** Permutation table for selecting bits for the expanded half block.
    This is used compute the E function described in DES Algorithm
    Illustrated. */
extern int expandedRSelector[ SUBKEY_BITS ];

/** Number of different S-Box talbes used in the f() funciton. */
#define SBOX_COUNT 8
  
/** Number of rows in each S-Box talbe used in the f() funciton. */
#define SBOX_ROWS 4
  
/** Number of columns in each S-Box talbe used in the f() funciton. */
#define SBOX_COLS 16
  
/** Number of bits used to index into each S-Box table. */
#define SBOX_INPUT_BITS 6
  
/** Number of bits returned from each S-Box lookup. */
#define SBOX_OUTPUT_BITS 4
  
/** This is all of the S-Box tables used to convert 6-bit values to
    4-bit valeus in the f() function calculation.  The individual 2D
    tables in this array are called S1 .. S8 in the DES Algorithm
    Illustrated article, but the indices of the tables are indexed
    from zero.  For example S1 is at sBoxTable[ 0 ].  Starting from
    zero makes the indexing of the input and output bits for the S-Box
    a little easier to work with.
*/
extern int sBoxTable[ SBOX_COUNT ][ SBOX_ROWS ][ SBOX_COLS ];

/** This is all of the permutation applied at the end of the
    fFunction. In the DES Algorithm Illustrated article, it's called
    P. */
extern int fFunctionPerm[ BLOCK_HALF_BITS ];

/** This is the final permutation performed after 16 rounds.  It
    rearranges bits of R_16 L_16 to create the encrypted block. It's
    called IP^-1 in the DES Algorithm Illustrated article. */
extern int finalPerm[ BLOCK_BITS ];
