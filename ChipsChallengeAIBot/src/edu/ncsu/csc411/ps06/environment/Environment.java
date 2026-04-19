package edu.ncsu.csc411.ps06.environment;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

import edu.ncsu.csc411.ps06.agent.Robot;

/**
 * The world in which this simulation exists. As a base
 * world, this produces a 10x10 room of blank tiles. Environments
 * can also be created using the (String[][] map) constructor to produce
 * different environments based on the contents of the String array.
 * 
 * This object will allow the agent to explore the world and is how
 * the agent will retrieve information about neighboring tiles.
 * DO NOT MODIFY.
 */
public class Environment {
  private Position[][] positions;
  private Map<Position, Tile> tiles;
  private ArrayList<Robot> robots;
  private Map<Robot, Position> robotPositions;
  private Map<Robot, ArrayList<String>> robotHoldings;
  private int rows, cols;
  private Position target;
  private Map<TileStatus, ArrayList<Position>> envPositions;

  /**
   * Calls Environment(int rows, int columns).
   */
  public Environment() {
    this(10, 10);
  }
  
  /**
   * Builds an Environment that is rows tall and columns wide.
   * Also instantiates many of the class variables, as well as
   * builds the connections between Position objects.
   * @param rows - the number of rows
   * @param columns 0 the number of columns
   */
	public Environment(int rows, int columns) {
		this.rows = rows;
		this.cols = columns;
		this.positions = new Position[this.rows][this.cols];
		this.tiles = new HashMap<Position, Tile>();
		this.robots = new ArrayList<Robot>();
		this.robotPositions = new HashMap<Robot, Position>();
		this.robotHoldings = new HashMap<Robot, ArrayList<String>>();
		buildEnvPositionMap();
		for(int row = 0; row < rows; row++) {
			for (int col = 0; col < cols; col++) {
				// Create a new position at (row, col)
				Position p = new Position(row, col);
				this.positions[row][col] = p;

				// And set it to BLANK
				Tile t = new Tile(TileStatus.BLANK);
				// Set the newly made dirty tile t to position p
				this.tiles.put(positions[row][col], t);
			}
		}

		// Establish neighbors for each Position
		for(int row = 0; row < rows; row++) {
			for (int col = 0; col < cols; col++) {
			  if (row > 0) {
          this.positions[row][col].setAbove(positions[row - 1][col]);
        }
        if (row < this.rows - 1) {
          this.positions[row][col].setBelow(positions[row + 1][col]);
        }
        if (col > 0) {
          this.positions[row][col].setLeft(positions[row][col - 1]);
        }
        if (col < this.cols - 1) {
          this.positions[row][col].setRight(positions[row][col + 1]);
        }
			}
		}
	}

	/** 
   * Converts the String array acronyms into their respective objects. Likewise,
   * establishes what each position contains and builds envPositions, which creates
   * a mapping for TileStatus to a list of Positions that have that particular tile.
   * For example, this.envPositions.get(TileStatus.CHIP) will return an ArrayList of
   * Position objects corresponding to all of the Chip Positions.
   *   
   * The acronyms correspond to the following environment objects:
   * ST - Agent Starting Position
   * BL - Blank Tile
   * WL - Wall Tile
   * CH - Chip
   * PL - Portal (Goal)
   * DP - Door to Portal
   * DG - Door (Green)
   * DY - Door (Yellow)
   * DB - Door (Blue)
   * DR - Door (Red)
   * KG - Key (Green)
   * KY - Key (Yellow)
   * KB - Key (Blue)
   * KR - Key (Red)
   * @param map - the String array containing these values
   */
	public Environment(String[][] map) {
		this(map.length, map[0].length);
		for (int row = 0; row < map.length; row++) {
			for (int col = 0; col < map[row].length; col++) {
				String tile = map[row][col];
				Position p = this.positions[row][col];
				switch(tile) {
				case "ST": 
					Robot robot = new Robot(this);
					addRobot(robot, p);
					this.tiles.put(p, new Tile(TileStatus.BLANK));
					break;
				case "BL": tiles.put(p, new Tile(TileStatus.BLANK)); break;
				case "WL": tiles.put(p, new Tile(TileStatus.WALL)); break;
				case "WA": tiles.put(p, new Tile(TileStatus.WATER)); break;
				case "CH": 
					this.tiles.put(p, new Tile(TileStatus.CHIP));
					this.envPositions.get(TileStatus.CHIP).add(p);
					break;
				case "PL": 
					this.tiles.put(p, new Tile(TileStatus.GOAL));
					this.envPositions.get(TileStatus.GOAL).add(p);
					this.target = p;
					break;
				case "DP":
					this.tiles.put(p, new Tile(TileStatus.DOOR_GOAL)); 
					this.envPositions.get(TileStatus.DOOR_GOAL).add(p);
					break;
				case "DG":
					this.tiles.put(p, new Tile(TileStatus.DOOR_GREEN)); 
					this.envPositions.get(TileStatus.DOOR_GREEN).add(p);
					break;
				case "DY":
					this.tiles.put(p, new Tile(TileStatus.DOOR_YELLOW)); 
					this.envPositions.get(TileStatus.DOOR_YELLOW).add(p);
					break;
				case "DB":
					this.tiles.put(p, new Tile(TileStatus.DOOR_BLUE)); 
					this.envPositions.get(TileStatus.DOOR_BLUE).add(p);
					break;
				case "DR":
					this.tiles.put(p, new Tile(TileStatus.DOOR_RED)); 
					this.envPositions.get(TileStatus.DOOR_RED).add(p);
					break;
				case "KG": 
					this.tiles.put(p, new Tile(TileStatus.KEY_GREEN));
					this.envPositions.get(TileStatus.KEY_GREEN).add(p);
					break;
				case "KY": 
					this.tiles.put(p, new Tile(TileStatus.KEY_YELLOW));
					this.envPositions.get(TileStatus.KEY_YELLOW).add(p);
					break;
				case "KB": 
					this.tiles.put(p, new Tile(TileStatus.KEY_BLUE));
					this.envPositions.get(TileStatus.KEY_BLUE).add(p);
					break;
				case "KR": 
					this.tiles.put(p, new Tile(TileStatus.KEY_RED));
					this.envPositions.get(TileStatus.KEY_RED).add(p);
					break;
				default: throw new IllegalArgumentException("Tile Not Found - " + tile);
				}
			}
		}
	}

	private void buildEnvPositionMap() {
		this.envPositions = new HashMap<TileStatus, ArrayList<Position>>();
		this.envPositions.put(TileStatus.CHIP, new ArrayList<Position>());
		this.envPositions.put(TileStatus.GOAL, new ArrayList<Position>());
		this.envPositions.put(TileStatus.KEY_BLUE, new ArrayList<Position>());
		this.envPositions.put(TileStatus.KEY_GREEN, new ArrayList<Position>());
		this.envPositions.put(TileStatus.KEY_RED, new ArrayList<Position>());
		this.envPositions.put(TileStatus.KEY_YELLOW, new ArrayList<Position>());
		this.envPositions.put(TileStatus.DOOR_BLUE, new ArrayList<Position>());
		this.envPositions.put(TileStatus.DOOR_GREEN, new ArrayList<Position>());
		this.envPositions.put(TileStatus.DOOR_RED, new ArrayList<Position>());
		this.envPositions.put(TileStatus.DOOR_YELLOW, new ArrayList<Position>());
		this.envPositions.put(TileStatus.DOOR_GOAL, new ArrayList<Position>());
	}

	/* Traditional Getters */
	protected TileStatus getTileStatus(Position p) { return tiles.get(p).getStatus(); }
	public Position getRobotPosition(Robot robot) { return this.robotPositions.get(robot); }
	public Map<TileStatus, ArrayList<Position>> getEnvironmentPositions() { return this.envPositions; }
	public Map<Position, Tile> getTiles() { return tiles; }
	public ArrayList<Robot> getRobots() { return this.robots; }
	public int getRows() { return this.rows; }
	public int getCols() { return this.cols; }

	protected void addRobot(Robot robot, Position p) {
		this.robotPositions.put(robot, p);
		this.robotHoldings.put(robot, new ArrayList<String>());
		this.robots.add(robot);
	}

	/**
   * Serves are the method for agents to 'sense' the Environment.
   * Returns a Map/Dictionary containing the tiles to the 
   * right, left, above, and below the Robot. If a particular
   * location is invalid (outside the environment), it will not
   * create that key-value pair.
   * @param robot - the robot to center the method around
   * @return a Map (dictionary) of its neighbors
   */
	public Map<String, Tile> getNeighborTiles(Robot robot) {
		Map<String, Tile> neighbors = new HashMap<String, Tile>();

		Position robotPos = getRobotPosition(robot);
		neighbors.put("self", tiles.get(robotPos));
		if(robotPos.getAbove() != null) {
			neighbors.put("above", tiles.get(robotPos.getAbove()));
		}
		if(robotPos.getBelow() != null) {
			neighbors.put("below", tiles.get(robotPos.getBelow()));
		}
		if(robotPos.getLeft() != null) {
			neighbors.put("left", tiles.get(robotPos.getLeft()));
		}
		if(robotPos.getRight() != null) {
			neighbors.put("right", tiles.get(robotPos.getRight()));
		}

		return neighbors;
	}
	
	/**
   * Serves are the method for agents to 'sense' the Environment.
   * Returns a Map/Dictionary containing the tiles to the 
   * right, left, above, and below the Robot. If a particular
   * location is invalid (outside the environment), it will not
   * create that key-value pair.
   * @param p - the Position to center this method call on
   * @return A Map (dictionary) of the respective neighbors
   */
	public Map<String, Position> getNeighborPositions(Position p) {
		Map<String, Position> neighbors = new HashMap<String, Position>();
		
		if(p.getAbove() != null) {
			neighbors.put("above", p.getAbove());
		}
		if(p.getBelow() != null) {
			neighbors.put("below", p.getBelow());
		}
		if(p.getLeft() != null) {
			neighbors.put("left", p.getLeft());
		}
		if(p.getRight() != null) {
			neighbors.put("right", p.getRight());
		}
		
		return neighbors;
	}
	
	/** 
   * Returns the Position of the DOOR_GOAL tile.
   * @return the Goal Position
   */
	public Position getGoalPosition() {
		return this.envPositions.get(TileStatus.DOOR_GOAL).get(0);
	}
	
	/** 
   * Counts number of chips remaining.
   * @return an integer
   */
	public int getNumRemainingChips() {
		int count = 0;
		for (int row = 0; row < rows; row++) {
			for (int col = 0; col < cols; col++) {
				Position p = positions[row][col];
				if (this.tiles.get(p).getStatus() == TileStatus.CHIP)
					count++;
			}
		}
		return count;
	}

	/** 
   * Returns the inventory of the Robot parameter.
   * @param robot - the Robot whose inventory we are pulling
   * @return an ArrayList of the Robot's inventory
   */
	public ArrayList<String> getRobotHoldings(Robot robot) {
		return this.robotHoldings.get(robot);
	}
	

	/* Determines if a particular [row][col] coordinate is within
	 * the boundaries of the environment. This is a rudimentary
	 * "collision detection" to ensure the agent does not walk
	 * outside the world (or through walls/doors). Likewise, ensures
	 * the agent does not pass through a door without meeting the 
	 * required criteria - having a corresponding key for a door, or
	 * having collected all the chips.
	 */
	protected boolean validPos(int row, int col, Robot robot) {
		try {
			ArrayList<String> inventory = this.robotHoldings.get(robot);
			Position p = positions[row][col];
			TileStatus status = this.tiles.get(p).getStatus();

			// Cannot pass through the final door without collecting all the chips
			boolean doorGoalMissingChip = status == TileStatus.DOOR_GOAL && getNumRemainingChips() > 0;
			if(doorGoalMissingChip)
				return false;
			
			// Door Bouncer - cannot pass through a given door without having its respective key
			boolean doorBlueKey = status == TileStatus.DOOR_BLUE && !inventory.contains("KEY_BLUE");
			if(doorBlueKey)
				return false;
			boolean doorGreenKey = status == TileStatus.DOOR_GREEN && !inventory.contains("KEY_GREEN");
			if(doorGreenKey)
				return false;
			boolean doorRedKey = status == TileStatus.DOOR_RED && !inventory.contains("KEY_RED");
			if(doorRedKey)
				return false;
			boolean doorYellowKey = status == TileStatus.DOOR_YELLOW && !inventory.contains("KEY_YELLOW");
			if(doorYellowKey)
				return false;
			
			// Finally, checking the position is within the Environment and not a wall.
			boolean withinWorld = row >= 0 && row < this.rows && col >= 0 && col < this.cols;
			boolean notWall = (status != TileStatus.WALL) && (status != TileStatus.WATER);
			return withinWorld && notWall;
		} catch (ArrayIndexOutOfBoundsException e) {
			return false;
		}
	}

	/** 
   * Updates the position of a Robot. Prior to this method, validPos is called.
   * @param robot - the Robot
   * @param row - the Robot's new row
   * @param col - the Robot's new column
   */
	protected void updateRobotPos(Robot robot, int row, int col) {
		Position p = positions[row][col];
		robotPositions.put(robot, p);
	}

	/** Gets the new state of the world after robot actions. */
	public void updateEnvironment() {
		for(Robot robot : robots) {
			Action action = robot.getAction();
			Position robotPos = getRobotPosition(robot);
			int row = robotPos.getRow();
			int col = robotPos.getCol();
			switch(action) {
			case MOVE_DOWN:
        if (validPos(row + 1, col, robot))
          updateRobotPos(robot, row + 1, col);
        break;
      case MOVE_LEFT:
        if (validPos(row, col - 1, robot))
          updateRobotPos(robot, row, col - 1);
        break;
      case MOVE_RIGHT:
        if (validPos(row, col + 1, robot))
          updateRobotPos(robot, row, col + 1);
        break;
      case MOVE_UP:
        if (validPos(row - 1, col, robot))
          updateRobotPos(robot, row - 1, col);
        break;
      case DO_NOTHING: // pass to default
      default:
        break;
			}

			TileStatus status = tiles.get(robotPos).getStatus();
			ArrayList<String> inventory = this.robotHoldings.get(robot);
			if(status == TileStatus.CHIP) {
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.KEY_BLUE) {
				inventory.add("KEY_BLUE");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.KEY_GREEN) {
				inventory.add("KEY_GREEN");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.KEY_RED) {
				inventory.add("KEY_RED");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.KEY_YELLOW) {
				inventory.add("KEY_YELLOW");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.DOOR_BLUE) {
				inventory.remove("KEY_BLUE");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.DOOR_GREEN) {
				inventory.remove("KEY_GREEN");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.DOOR_RED) {
				inventory.remove("KEY_RED");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.DOOR_YELLOW) {
				inventory.remove("KEY_YELLOW");
				removeFromEvironment(status, robotPos);
			} else if(status == TileStatus.DOOR_GOAL) {
				removeFromEvironment(status, robotPos);
			} 
		}
	}

	private void removeFromEvironment(TileStatus tile, Position robotPos) {
		this.tiles.put(robotPos, new Tile(TileStatus.BLANK));
		this.envPositions.get(tile).remove(robotPos);
		//System.out.println("UPDATED " + tile + ": ");
		//System.out.println(this.getEnvironmentPositions().get(tile));
	}
	
	/** Prints the number of chips remaining and whether the goal condition was met. */
	public void printPerformanceMeasure() {
		System.out.println("Simulation Complete");
		System.out.println("Chips Remaining: " + getNumRemainingChips());
		String reachGoal = "No";
		if( goalConditionMet() ) {
			reachGoal = "Yes";
		}
		System.out.print("Reached Portal: " + reachGoal);
	}

	/**
   * Check if any robots have reached the PORTAL tile and there are no chips remaining.
   * @return true if the goal conditional has been met, else false
   */
	public boolean goalConditionMet() {
		for(Robot robot : robots) {
			Position robotPos = getRobotPosition(robot);
			if (robotPos.equals(this.target)) {
				return getNumRemainingChips() == 0;
			}
		}
		return false;
	}
}
