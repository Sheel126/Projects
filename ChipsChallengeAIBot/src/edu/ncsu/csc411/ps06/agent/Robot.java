package edu.ncsu.csc411.ps06.agent;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.PriorityQueue;
import java.util.Stack;

import edu.ncsu.csc411.ps06.environment.Tile;
import edu.ncsu.csc411.ps06.environment.Action;
import edu.ncsu.csc411.ps06.environment.Environment;
import edu.ncsu.csc411.ps06.environment.Position;
import edu.ncsu.csc411.ps06.environment.TileStatus;

/**
Represents a planning agent within an environment modeled after
the Chip's Challenge Windows 95 game. This agent must develop a
plan for navigating the environment to collect chips and keys
in order to reach the environment's portal (goal condition).

Problem Set 06 - In this problem set, you will be developing a planning
  agent to navigate the environment to collect chips scattered across the
  map. In order to reach the portal (goal condition), the agent must collect
  all the chips first. In order to do this, the agent will also need to collect
  assorted keys that can be used to unlock doors blocking some of the chips.

  Map difficulties increase by the number of subgoals that the agent must complete.
  While I will be able to assist in getting started debugging, planning is not a 
  simple algorithm and still a complex task for even the most advanced AIs. 
  This of this as one of those "unsolvable" math problems scrawled in chalk on some 
  abandoned blackboard. 
  
  That is to say, you are on your own in this "mostly uncharted" territory.
*/

public class Robot {
	private Environment env;
	
	/** priority queue to store visited tiles in priority order */
	private PriorityQueue<TileNode> frontier;
	
	/** Map to keep track of where each agent came from when it is on a tile */
	private Map<TileNode, TileNode> cameFrom;
	
	/** Map that keeps track of cost so far of visiting each tile */
	private Map<TileNode, Integer> costSoFar;
		
	/** Stack to keep track of actions taken, so we can get the path to the goal when items are popped */
	private Stack<Action> actionPath = new Stack<>();
	
	
	// Greedy
	/** Priority queue to store values when working with greedy algorithm */
	private PriorityQueue<TileNode> greedyFrontier;
	
	/** Mao to keep track of where each agent came from when it is on a tile with greedy algorithm */
	private Map<TileNode, TileNode> greedyCameFrom;
	
	
	
	/** Initializes a Robot on a specific tile in the environment.
   * @param env - The Environment
   */
  public Robot (Environment env) { this.env = env; }
  
  /**
	 * Gets the neighboring TileNodes from the current TileNode
	 * @param current is the node for which the neighbors need to be calculated
	 * @return List of TileNode objects that are the valid neighbors of the current node. 
	 */
	private List<TileNode> getNeighbors(TileNode current) {
		
		//Position selfPos = env.getRobotPosition(this);
		Map<Position, Tile> positions = env.getTiles();
		Map<String, Position> neighbors = null;
		for (Position pos : positions.keySet()) {
			if (pos.getRow() == current.getRow() && pos.getCol() == current.getCol()) {
				neighbors = env.getNeighborPositions(pos);
			}
		}
		
		//Map<String, Position> neighbors = env.getNeighborPositions(selfPos);
		//System.out.println(neighbors.size());
		Position abovePos = neighbors.get("above"); // Either a Tile or null
		Position belowPos = neighbors.get("below"); // Either a Tile or null
		Position leftPos = neighbors.get("left");   // Either a Tile or null
		Position rightPos = neighbors.get("right"); // Either a Tile or null
		
		
		
		ArrayList<TileNode> tileNodes = new ArrayList<>();
		if (abovePos != null) {
			tileNodes.add(new TileNode(positions.get(abovePos), 0, abovePos.getRow(), abovePos.getCol()));
		}
		if (belowPos != null) {
			tileNodes.add(new TileNode(positions.get(belowPos), 0, belowPos.getRow(), belowPos.getCol()));
		}
		if (leftPos != null) {
			tileNodes.add(new TileNode(positions.get(leftPos), 0, leftPos.getRow(), leftPos.getCol()));
		}
		if (rightPos != null) {
			tileNodes.add(new TileNode(positions.get(rightPos), 0, rightPos.getRow(), rightPos.getCol()));
		}
		
		return tileNodes;
	}
	
	/**
	 * Runs the Greedy approach for this problem
	 */
	public void runGreedy(Position targetPos) {
		
		Position selfPos = env.getRobotPosition(this);
		Map<Position, Tile> positions = env.getTiles();
		
		// Position targetPos = env.getTarget();
		
		
		
		greedyFrontier = new PriorityQueue<>();
		greedyCameFrom = new HashMap<>();
		
		Tile selfTile = positions.get(selfPos);
		TileNode start = new TileNode(selfTile, 0, selfPos.getRow(), selfPos.getCol());
		start.setPriority(heuristic(targetPos, start));
		greedyFrontier.add(start);
		
		greedyCameFrom.put(start, null);
		
		while (!greedyFrontier.isEmpty()) {
			
			TileNode current = greedyFrontier.poll();
			
			if (current.getTile().getStatus() == TileStatus.GOAL) {
				return;
			}
			
			for (TileNode node : getNeighbors(current)) {
				ArrayList<String> inventory = env.getRobotHoldings(this);
				if (node.getTile() == null || node.getTile().getStatus() == TileStatus.WALL || node.getTile().getStatus() == TileStatus.WATER) {
					continue;
				}
				
				if (node.getTile().getStatus() == TileStatus.DOOR_BLUE && !inventory.contains("KEY_BLUE")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_RED && !inventory.contains("KEY_RED")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_YELLOW && !inventory.contains("KEY_YELLOW")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_GREEN && !inventory.contains("KEY_GREEN")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_GOAL && env.getNumRemainingChips() != 0) continue;
				
				
				if (!greedyCameFrom.containsKey(node)) {
					int priority = heuristic(targetPos, node);
					node.setPriority(priority);
					greedyFrontier.add(node);
					greedyCameFrom.put(node, current);
				}
			}
			
			
		}
		
		
	}
	
	/**
	 * Runs the A* approach for this problem
	 */
	public void runAStar(Position targetPos) {
		Position selfPos = env.getRobotPosition(this);
		Map<Position, Tile> positions = env.getTiles();
		
		// Position targetPos = env.getGoalPosition();
		
		frontier = new PriorityQueue<>();
		cameFrom = new HashMap<>();
		costSoFar = new HashMap<>();
		
		Tile selfTile = positions.get(selfPos);
		TileNode start = new TileNode(selfTile, 0, selfPos.getRow(), selfPos.getCol());
		frontier.add(start);
		
		cameFrom.put(start, null);
		costSoFar.put(start, 0);
		
			
		while (!frontier.isEmpty()) {
			TileNode current = frontier.poll();
			
			if (current.getTile().getStatus() == TileStatus.GOAL) {
				return;
			}
			
			//System.out.println(current.getRow() + "" + current.getCol());
			
			for (TileNode node : getNeighbors(current)) {
				ArrayList<String> inventory = env.getRobotHoldings(this);
				if (node.getTile() == null || node.getTile().getStatus() == TileStatus.WALL || node.getTile().getStatus() == TileStatus.WATER ) {
					continue;
				}

				if (node.getTile().getStatus() == TileStatus.DOOR_BLUE && !inventory.contains("KEY_BLUE")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_RED && !inventory.contains("KEY_RED")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_YELLOW && !inventory.contains("KEY_YELLOW")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_GREEN && !inventory.contains("KEY_GREEN")) continue;
				if (node.getTile().getStatus() == TileStatus.DOOR_GOAL && env.getNumRemainingChips() != 0) continue;
				
				//System.out.println(node.getRow() + "" + node.getCol());
				int newCost = costSoFar.get(current) + 1;
				if (!costSoFar.containsKey(node) || newCost < costSoFar.get(node)) {
					
					costSoFar.put(node, newCost);
					int priority = newCost + heuristic(targetPos, node);
					node.setPriority(priority);
					frontier.add(node);
					//System.out.println("NEXT: " + node);
					//System.out.println("CURRENT" + current);
					cameFrom.put(node, current);
				}
			}
			
				
		}	
		}
	
	/**
	 * 
	 * @param cameFrom is the Map that contains the path from start to end, so it can be tracked back
	 * @param goal is the goal TileNode to ensure that we stop the search in the map once we hit the goal
	 * @return Stack<Action> which is the stack of actions so they can be popped and returned in getAction
	 */
	private Stack<Action> reconstructActions(Map<TileNode, TileNode> cameFrom, TileNode goal) {
	    Stack<Action> actions = new Stack<>();
	    TileNode current = goal;

	    while (cameFrom.get(current) != null) { 
	        TileNode previous = cameFrom.get(current);

	        if (previous.row < current.row) {
	        	actions.push(Action.MOVE_DOWN);
	        }
	        else if (previous.row > current.row) {
	        	actions.push(Action.MOVE_UP);
	        }
	        else if (previous.col < current.col) {actions.push(Action.MOVE_RIGHT);
	        
	        }
	        else if (previous.col > current.col) {actions.push(Action.MOVE_LEFT);
	        
	        }

	        // move backwards in path from cameFrom map
	        current = previous; 
	    }
	    
	    return actions;
	}
	
	/**
	 * The heuristic function that calculates the distance between two points on the grid
	 * @param targetPos is the position of the target tile where the agent needs to reach
	 * @param node is the TileNode that the the program needs to calculate the distance to the target
	 * @return int which is the distance between the two positions
	 */
	private int heuristic(Position targetPos, TileNode node) {
		return Math.abs(targetPos.getRow() - node.getRow()) + Math.abs(targetPos.getCol() - node.getCol());
	}
	
	/**
	 * Conducts A* on the closest item within the arraylist of items. The list of keys, doors, or chips is passed and the method
	 * conducts A* on the closest item from within those lists to move the agent closer to the goal
	 * @param items is the list of keys, doors, or chips that we need to find the closest item in
	 * @return Action on what action the agent should conduct after computing the path using the A* algorithm.
	 */
	private Action conductAStatOnClosestItem(ArrayList<Position> items) {
		PriorityQueue<TileNode> distanceQueue = new PriorityQueue<>();
		Position selfPos = env.getRobotPosition(this);
		for (int i = 0; i < items.size(); i++) {
			TileNode current = new TileNode(env.getTiles().get(items.get(i)), 0, items.get(i).getRow(), items.get(i).getCol());
			int cost = Math.abs(selfPos.getRow() - current.getRow()) + Math.abs(selfPos.getCol() - current.getCol());
			current.setPriority(cost);
			distanceQueue.add(current);
		}
		
		TileNode targetTileNode = distanceQueue.poll();
		runAStar(new Position(targetTileNode.getRow(), targetTileNode.getCol()));
		actionPath = reconstructActions(cameFrom, targetTileNode);
//		runGreedy(new Position(targetTileNode.getRow(), targetTileNode.getCol()));
//		actionPath = reconstructActions(greedyCameFrom, targetTileNode);
		if (!actionPath.isEmpty()) {
			return actionPath.pop();
		}
		return Action.DO_NOTHING;
		
	}
	
	/**	The method called by Environment to retrieve the agent's actions.
	 *  The method takes into account the different priorities of what the agent needs to get. The agent first looks for keys,
	 *  followed by checking for locked doors, and then getting the chips before getting to the portal.The idea is to get to the closest 
	 *  item that we need. The method then determines what key, door, or chip to get depending on what is closest. Each item is appended to a priority
	 *  queue respectively (all keys for instance) with the shortest distance being at the top. Then an A star algo is ran from current agent position
	 *  to closest key, door, or chip. This occurs until agent has all keys and all doors. Finally, the agent then uses A star algo to get to the portal.
	 *         
	    @return should return a single Action from the Action class.
	    	- Action.DO_NOTHING
	    	- Action.MOVE_UP
	    	- Action.MOVE_DOWN
	    	- Action.MOVE_LEFT
	    	- Action.MOVE_RIGHT
	*/
	public Action getAction () {
		Map<Position, Tile> positions = env.getTiles();
		Map<TileStatus, ArrayList<Position>> envPositions = env.getEnvironmentPositions();
		Position targetPos = envPositions.get(TileStatus.GOAL).get(0);
		
		ArrayList<String> inventory = env.getRobotHoldings(this);
		
		if (!envPositions.get(TileStatus.KEY_BLUE).isEmpty()) {
			// find closest one and move toward it
			return conductAStatOnClosestItem(envPositions.get(TileStatus.KEY_BLUE));
		} else if (!envPositions.get(TileStatus.KEY_GREEN).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.KEY_GREEN));
		} else if (!envPositions.get(TileStatus.KEY_RED).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.KEY_RED));
		} else if (!envPositions.get(TileStatus.KEY_YELLOW).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.KEY_YELLOW));
		} else if (inventory.contains("KEY_GREEN") && !envPositions.get(TileStatus.DOOR_GREEN).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.DOOR_GREEN));
		} else if (inventory.contains("KEY_RED") && !envPositions.get(TileStatus.DOOR_RED).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.DOOR_RED));
		} else if (inventory.contains("KEY_BLUE") && !envPositions.get(TileStatus.DOOR_BLUE).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.DOOR_BLUE));
		} else if (inventory.contains("KEY_YELLOW") && !envPositions.get(TileStatus.DOOR_YELLOW).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.DOOR_YELLOW));
		} else if (!envPositions.get(TileStatus.CHIP).isEmpty()) {
			return conductAStatOnClosestItem(envPositions.get(TileStatus.CHIP));
		}
		runAStar(targetPos);
		actionPath = reconstructActions(cameFrom, new TileNode(positions.get(targetPos), 0, targetPos.getRow(), targetPos.getCol()));
//		runGreedy(targetPos);
//		actionPath = reconstructActions(greedyCameFrom, new TileNode(positions.get(targetPos), 0, targetPos.getRow(), targetPos.getCol()));
		return actionPath.pop();
	}
	

	@Override
	public String toString() {
		return "Robot [pos=" + env.getRobotPosition(this) + "]";
	}
	
	
	/**
	 * TileNode class that creates a node representation of tiles in the grid
	 * @author Sheel Patel
	 *
	 */
	public class TileNode implements Comparable<TileNode> {
		
		/** Tile object associated with position row and col*/
		private Tile tile;
		
		/** Priority int that contains the priority of the node */
		private int priority;
		
		/** Row value of the tile */
		private int row;
		
		/** Col value of the tile */
		private int col;
		
		/**
		 * Constructor that sets the tile, priority, row and col for a TileNode
		 * @param tile is the tile correlating to position at row and col
		 * @param priority is the priority of the node which determines its position in the priority queue
		 * @param row is the row value of the tile
		 * @param col is the col value of the tile
		 */
		public TileNode(Tile tile, int priority, int row, int col) {
			this.tile = tile;
			this.priority = priority;
			this.row = row;
			this.col = col;
		}
		
		/**
		 * Gets priority
		 * @return int priority of the tile
		 */
		public int getPriority() {
			return this.priority;
		}
		
		/**
		 * Gets the tile object
		 * @return Tile object from the TileNode
		 */
		public Tile getTile() {
			return this.tile;
		}
		
		/**
		 * Gets the row value
		 * @return int which is the row value
		 */
		public int getRow() {
			return this.row;
		}
		
		/**
		 * Gets the col value
		 * @return int which is the col value
		 */
		public int getCol() {
			return this.col;
		}
		
		/**
		 * Sets the priority value of the TileNode
		 * @param priority is the priority to set
		 */
		public void setPriority(int priority) {
			this.priority = priority;
		}

		/**
		 * Compares two TileNodes based on priority value
		 * @param o is the TileNode to compare to
		 * @return int which indicates if this object is greater or less than or equal to passed in TileNode
		 */
		@Override
		public int compareTo(TileNode o) {
			return Integer.compare(this.getPriority(), o.getPriority());
		}
		
		/**
		 * Calculates if two TileNode objs are equal to each other based on row and col values
		 * @param obj is the object to compare to this object
		 * @return true if objs are same and false otherwise
		 */
		@Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            TileNode node = (TileNode) obj;
            return row == node.row && col == node.col;
        }

		/**
		 * Calculates the hash code of an object based on row and col values
		 * @return int which is the hash code
		 */
        @Override
        public int hashCode() {
            return Objects.hash(row, col);
        }
        
        /**
         * Returns the toString representation of the TileNode object
         * @return string which is the TileNode in string format
         */
        @Override
        public String toString() {
        	return "Priority: " + priority + " Row: " + row + " Col: " + col;
        }
		
	}
	
}

