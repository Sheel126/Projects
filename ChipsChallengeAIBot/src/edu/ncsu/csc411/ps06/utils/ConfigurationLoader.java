package edu.ncsu.csc411.ps06.utils;

import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Properties;

/**
 * Loads the config/config*.txt files into the project and returns
 * them to the VisualizeSimulation file. This allows users running
 * the project from lower resolution screens to see the entire map.
 * DO NOT MODIFY.
 */
public class ConfigurationLoader {
  /** 
   * Loads the configurations from the filename parameter.
   * @param filename config/config*.txt
   * @return A Map (dictionary) of properties found in the text file
   */
  public static Properties loadConfiguration(String filename) {
		Properties properties = new Properties();
		
		try {
			FileInputStream propsInput = new FileInputStream(filename);
			properties.load(propsInput);
		} catch (FileNotFoundException fnf) {
			String errorMsg = "%s is not a valid filename\n";
			System.out.printf(errorMsg, filename);
			fnf.printStackTrace();
			System.exit(0);
		} catch (IOException ioe) {
			String errorMsg = "An error occurred when attempting to load %s\n";
			System.out.printf(errorMsg, filename);
			ioe.printStackTrace();
			System.exit(0);
		}
		
		return properties;
	}

}
