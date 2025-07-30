package edu.ncsu.csc411.ps06.simulation;

import edu.ncsu.csc411.ps06.environment.Environment;
import edu.ncsu.csc411.ps06.utils.MapManager;

/**
 * A non-GUI version of the simulation. This will allow
 * you to quickly test out your implementations without
 * having to wait for each time-step to occur (there is a
 * 200 millisecond delay between time-steps in the visualization).
 * Feel free to modify the class variables to adjust simulation maps.
 */
public class RunSimulation {
	private Environment env;
	private static int ITERATIONS = 1000;
	private static boolean DEBUG = false;
	private static String mapFile = "maps/public/map01.txt";
	
	// Build the simulation with the following parameters
	public RunSimulation(String mapFile, int iterations) {
		this(mapFile, iterations, false);
	}
	public RunSimulation(String mapFile, int iterations, boolean debug) {
		String[][] map = MapManager.loadMap(mapFile);
		this.env = new Environment(map);
		RunSimulation.ITERATIONS = iterations;
		RunSimulation.DEBUG = debug;
	}
	
	public void disableSimErrors() {
		RunSimulation.DEBUG = false;
	}
	
	// Iterate through the simulation, updating the environment at each time step
	public void run() {
		for (int i = 1; i <= RunSimulation.ITERATIONS; i++) {
			try {
				// Wrapped in try/catch in case the Robot's decision results
				// in a crash; we'll treat that the same as Action.DO_NOTHING
				env.updateEnvironment();
			} catch (Exception ex) {
				if (RunSimulation.DEBUG) {
					String error = "[ERROR AGENT CRASH AT TIME STEP %03d] %s\n";
					System.out.printf(error, i, ex);
				}
			}
			if (env.goalConditionMet()) {
				env.printPerformanceMeasure();
				break;
			}
		}
		
		env.printPerformanceMeasure();
	}
	
	public boolean goalConditionMet() {
		return this.env.goalConditionMet();
	}

	public static void main(String[] args) {
		RunSimulation sim = new RunSimulation(mapFile, ITERATIONS);
		sim.run();
    }
}