#!/bin/bash
# This is a shell script to check your program(s) on test cases.
# It usese the same language you normally use to type commands in
# a terminal window.  You can write whole programs in shell.

# Assume we've succeeded until we see otherwise.
FAIL=0

# Print an error message and set the fail flag.
fail() {
    echo "**** $1"
    FAIL=1
}

# Check the exit status.  The actual exit status (ASTATUS) should match
# the expected status (ESTATUS)
checkStatus() {
  ESTATUS="$1"
  ASTATUS="$2"

  # Make sure the program exited with the right exit status.
  if [ "$ASTATUS" -ne "$ESTATUS" ]; then
      fail "FAILED - incorrect program exit status. (expected $ESTATUS,  Got: $ASTATUS)"
      return 1
  fi

  return 0
}

# Check the contents of an a file.  If the expected file (EFILE)
# exists, then the actual file (AFILE) should exist and it should match.
checkFile() {
  NAME="$1"
  EFILE="$2"
  AFILE="$3"

  # Make sure we're really expecting this file.
  if [ ! -f "$EFILE" ]; then
      return 0
  fi

  # Make sure the output matches the expected output.
  echo "   diff $EFILE $AFILE"
  diff -q "$EFILE" "$AFILE" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
      fail "FAILED - $NAME ($AFILE) doesn't match expected ($EFILE)"
      return 1
  fi

  return 0
}

# Same as checkFile, but if the expected file (EFILE) doesn't exist, the
# actual file (AFILE) should be empty.
checkFileOrEmpty() {
  NAME="$1"
  EFILE="$2"
  AFILE="$3"
  
  # if the expected output file doesn't exist, the actual file should be
  # empty.
  if [ ! -f "$EFILE" ]; then
      if [ -s "$AFILE" ]; then
	  fail "FAILED - $NAME ($AFILE) should be empty."
	  return 1
      fi
      return 0
  fi

  # Make sure the output matches the expected output.
  echo "   diff $EFILE $AFILE"
  diff -q "$EFILE" "$AFILE" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
      fail "FAILED - $NAME ($AFILE) doesn't match expected ($EFILE)"
      return 1
  fi

  return 0
}

# Same as checkFile, but if the expected file (EFILE) doesn't exist, the
# actual file (AFILE) should not exist.
checkFileOrDNE() {
  NAME="$1"
  EFILE="$2"
  AFILE="$3"
  
  # if the expected output file doesn't exist, the actual file should not exist
  if [ ! -f "$EFILE" ]; then
      if [ -f "$AFILE" ]; then
	  fail "FAILED - $NAME ($AFILE) should not exist."
	  return 1
      fi
      return 0
  fi

  # Make sure the output matches the expected output.
  echo "   diff $EFILE $AFILE"
  diff -q "$EFILE" "$AFILE" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
      fail "FAILED - $NAME ($AFILE) doesn't match expected ($EFILE)"
      return 1
  fi

  return 0
}

# The given file should exist but should be empty.
checkEmpty() {
  NAME="$1"
  AFILE="$2"
  
  if [ -s "$AFILE" ]; then
      fail "FAILED - $NAME ($AFILE) should be empty."
      return 1
  fi

  return 0
}

# Run a test case on the encrypt program.
testEncrypt() {
    TESTNO="$1"
    EOUTPUT="$2"
    ESTATUS="$3"

    rm -f output.bin
    
    echo "Test $TESTNO"
    echo "   ./encrypt ${args[@]} > stdout.txt 2> stderr.txt"
    ./encrypt ${args[@]} > stdout.txt 2> stderr.txt
    ASTATUS=$?

    if ! checkStatus "$ESTATUS" "$ASTATUS" ||
	    ! checkEmpty "Terminal output" "stdout.txt" ||
	    ! checkFileOrDNE "Encrypted output file" "$EOUTPUT" "output.bin" ||
	    ! checkFileOrEmpty "Stderr output" "message-$TESTNO.txt" "stderr.txt"
    then
	FAIL=1
	return 1
    fi

    echo "Test $TESTNO PASS"
    return 0
}

# Run a test case on the decrypt program.
testDecrypt() {
    TESTNO="$1"
    EOUTPUT="$2"
    ESTATUS="$3"
    
    rm -f output.txt
    
    echo "Test $TESTNO"
    echo "   ./decrypt ${args[@]} > stdout.txt 2> stderr.txt"
    ./decrypt ${args[@]} > stdout.txt 2> stderr.txt
    ASTATUS=$?

    if ! checkStatus "$ESTATUS" "$ASTATUS" ||
	    ! checkEmpty "Terminal output" "stdout.txt" ||
	    ! checkFileOrDNE "Plaintext output file" "$EOUTPUT" "output.txt" ||
	    ! checkFileOrEmpty "Stderr output" "message-$TESTNO.txt" "stderr.txt"
    then
	FAIL=1
	return 1
    fi

    echo "Test $TESTNO PASS"
    return 0
}

# Try the unit tests
make clean
make DESTest

if [ -x DESTest ]
then
    if ./DESTest
    then
       echo "Unit tests executed successfully"
    else
	fail "Unit tests didn't execute successfully";
    fi
else
    fail "Unit tests didn't build successfully";
fi

# make a fresh copy of the target programs
make

if [ $? -ne 0 ]; then
  fail "Make exited unsuccessfully"
fi

# Run test cases
if [ -x encrypt ]; then
    args=(abcd1234 plain-a.txt output.bin)
    testEncrypt 01 cipher-a.bin 0
    
    args=(passw0rd plain-b.txt output.bin)
    testEncrypt 02 cipher-b.bin 0

    args=(ciaba++a plain-c.txt output.bin)
    testEncrypt 03 cipher-c.bin 0
    
    args=(short plain-d.txt output.bin)
    testEncrypt 04 cipher-d.bin 0
    
    args=(--x-- plain-e.txt output.bin)
    testEncrypt 05 cipher-e.bin 0
    
    args=(Claudius plain-f.txt output.bin)
    testEncrypt 06 cipher-f.bin 0
    
    args=(longPassword plain-g.txt output.bin)
    testEncrypt 07 noOutputFile.bin 1
    
    args=(password missing-file.txt output.bin)
    testEncrypt 08 noOutputFile.bin 1
else
    fail "Since your encrypt program didn't compile, we couldn't test it"
fi

# Run test cases
if [ -x decrypt ]; then
    args=(abcd1234 cipher-a.bin output.txt)
    testDecrypt 09 plain-a.txt 0
    
    args=(passw0rd cipher-b.bin output.txt)
    testDecrypt 10 plain-b.txt 0
    
    args=(ciaba++a cipher-c.bin output.txt)
    testDecrypt 11 plain-c.txt 0
    
    args=(short cipher-d.bin output.txt)
    testDecrypt 12 plain-d.txt 0
    
    args=(--x-- cipher-e.bin output.txt)
    testDecrypt 13 plain-e.txt 0
    
    args=(Claudius cipher-f.bin output.txt)
    testDecrypt 14 plain-f.txt 0
    
    args=(hashtags cipher-g.bin)
    testDecrypt 15 noOutputFile.txt 1
else
    fail "Since your decrypt program didn't compile, we couldn't test it"
fi

if [ $FAIL -ne 0 ]; then
  echo "FAILING TESTS!"
  exit 13
else 
  echo "TESTS SUCCESSFUL"
  exit 0
fi
