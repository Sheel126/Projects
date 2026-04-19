package edu.ncsu.csc411.ps06.environment;

/**
 * A list of possible actions the robot can take.With regard
 * to the actions, the agent will automatically "pick up" items
 * and "unlock" doors as soon as the way through them (provided
 * they have the required items picked up). Maybe in the future
 * if the agent needs to pick up and "drop" an item this could
 * change, but for now these actions should be sufficient.
 * DO NOT MODIFY.
 */
public enum Action {
  /** Move Right */
  MOVE_RIGHT,
  /** Move Left */
  MOVE_LEFT, 
  /** Move Up */
  MOVE_UP, 
  /** Move Down */
  MOVE_DOWN,
  /** Do Nothing */
  DO_NOTHING;
}
