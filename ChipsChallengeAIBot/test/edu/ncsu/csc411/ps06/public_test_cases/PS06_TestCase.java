package edu.ncsu.csc411.ps06.public_test_cases;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import org.junit.Before;
import org.junit.Test;

import edu.ncsu.csc411.ps06.simulation.RunSimulation;

/**
 * This JUnit test suite uses JUnit5. In order to run these 
 * test cases, you will need to have JUnit5 installed on your
 * local machines. You can set your Project to use JUnit5 by
 * right-clicking on the project and selecting "Properties", then
 * selecting "Java Build Path". Finally, selecting "Add Library..."
 * will allow you to select "JUnit" and specify the version.
 * DO NOT MODIFY.
 */ 
public class PS06_TestCase {
	private final int NUM_TRIALS = 10; // Number of trials per test case
	private final int ITERATIONS = 1000; // Number of iterations ("moves") per trial
	private final double PASS_THRESHOLD = 0.7; // Pass a map 70% of the time
	private int TIMEOUT = 2000; // Test Case will fail after 2 seconds
	private int successfulTrials = 0;
	private boolean DEBUG = false;
	private String line = "Test %02d success rate: %.2f after %d trials";
	private String error = "Error on iteration %02d: %s";

	@Before
	public void setUp() {
		successfulTrials = 0;
	}

	/**
	 * Each test case runs exactly one (1) map NUM_TRIALS times. If the agent
	 * is successful (goalConditionMet), then successfulTrials is incremented
	 * by 1. In order to pass a test case, the agent must successfully complete
	 * the trial (map) 70% of the time.
	 */
	@Test
	public void testEnvironment01() {
		String map = "maps/public/map01.txt";
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				// CompletableFuture will run an iteration's simulation
				// asynchronously for 2000 milliseconds (2 seconds) before timing out.
				// This is to prevent infinite loops or inefficient implementations
				// like brute forcing the solution.
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		// Checks to see if the simulation was successful 70% of the time
		String msg = String.format(line, 1, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T1");
	}

	@Test
	public void testEnvironment02() {
		String map = "maps/public/map02.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 2, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T2");
	}

	@Test
	public void testEnvironment03() {
		String map = "maps/public/map03.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 3, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T3");
	}

	@Test
	public void testEnvironment04() {
		String map = "maps/public/map04.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T4");
	}
	
	@Test
	public void testEnvironment05() {
		String map = "maps/public/map05.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T5");
	}
	
	@Test
	public void testEnvironment06() {
		String map = "maps/public/map06.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T6");
	}
	
	@Test
	public void testEnvironment07() {
		String map = "maps/public/map07.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T7");
	}
	
	@Test
	public void testEnvironment08() {
		String map = "maps/public/map08.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T8");
	}
	
	@Test
	public void testEnvironment09() {
		String map = "maps/public/map09.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T9");
	}
	
	@Test
	public void testEnvironment10() {
		String map = "maps/public/map10.txt";
		
		long startTime = System.nanoTime();

		for (int trial = 0; trial < NUM_TRIALS; trial++) {
			RunSimulation sim = new RunSimulation(map, ITERATIONS, false);
			try {
				Runnable simulation = () -> sim.run();
				CompletableFuture.runAsync(simulation).get(TIMEOUT, TimeUnit.MILLISECONDS);
				if(sim.goalConditionMet()) {
					successfulTrials++;
				}
			} catch (InterruptedException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (ExecutionException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			} catch (TimeoutException e) {
				if (DEBUG)
					System.out.printf(error, trial, e.getClass());
			}
		}

		String msg = String.format(line, 4, successfulTrials / (NUM_TRIALS * 1.0) * 100, NUM_TRIALS);
		System.out.println(msg);
		assertTrue(successfulTrials / (NUM_TRIALS * 1.0) >= PASS_THRESHOLD, msg);
		long endTime = System.nanoTime();
		long duration = endTime - startTime;
		System.out.println("Algorithm took: " + duration + " nanoseconds for T10");
	}
}
