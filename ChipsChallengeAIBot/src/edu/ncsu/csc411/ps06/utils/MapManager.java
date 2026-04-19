package edu.ncsu.csc411.ps06.utils;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.ArrayList;
import java.util.Scanner;

/**
 * Reads the files from map/ and converts them into a nested array
 * structure that can be processed by the environment.
 * DO NOT MODIFY.
 */
public class MapManager {
  /**
   * Reads in a text file and loads each line as an ArrayList.
   * Once finished, converts the ArrayList into a String array.

   * @param filename - a text file from map/
   * @return an array of the values from the filename
   */
	public static String[][] loadMap(String filename) {
		// First build an ArrayList to store each line as a String array
		ArrayList<String[]> map = new ArrayList<String[]>();
		try {
			File fi = new File(filename);
			Scanner fiReader = new Scanner(fi);
			// Each line is read in and split to create a String array for
			// that particular line.
			while (fiReader.hasNextLine()) {
		        String line = fiReader.nextLine();
		        map.add(line.split(" "));
		      }
			fiReader.close();
		} catch (FileNotFoundException fnf) {
			String errorMsg = "%s is not a valid filename\n";
			System.out.printf(errorMsg, filename);
			fnf.printStackTrace();
		}
		
		// Finally, convert the ArrayList into a String[][]
		String[][] result = new String[map.size()][];
		for(int i = 0; i < result.length; i++) {
		    result[i] = map.get(i);
		}
		return result;
	}

}
