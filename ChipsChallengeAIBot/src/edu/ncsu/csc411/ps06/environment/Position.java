package edu.ncsu.csc411.ps06.environment;

/**
 * Represents a particular [row, col] coordinate as
 * a "Node" within the Environment to produce a graph-like
 * representation.
 * DO NOT MODIFY.

 * @author Adam Gaweda
 */
public class Position {
  private int row; 
  private int col;
  private Position above;
  private Position below;
  private Position left;
  private Position right;

  /**
   * Instantiates a Position for the row, col combination
   * @param row - the row
   * @param col - the col
   */
  public Position(int row, int col) {
    this.row = row;
    this.col = col;
  }

  /**
   * Returns the position's row
   * @return the position's row
   */
  public int getRow() {
    return this.row;
  }

  /**
   * Returns the position's column
   * @return the position's column
   */
  public int getCol() {
    return this.col;
  }

  protected void setAbove(Position neighbor) {
    this.above = neighbor;
    neighbor.below = this;
  }

  protected void setBelow(Position neighbor) {
    this.below = neighbor;
    neighbor.above = this;
  }

  protected void setLeft(Position neighbor) {
    this.left = neighbor;
    neighbor.right = this;
  }

  protected void setRight(Position neighbor) {
    this.right = neighbor;
    neighbor.left = this;
  }

  protected Position getAbove() {
    return this.above;
  }

  protected Position getBelow() {
    return this.below;
  }

  protected Position getLeft() {
    return this.left;
  }

  protected Position getRight() {
    return this.right;
  }

  @Override
  public String toString() {
    return "Point (" + this.row + ", " + this.col + ")";
  }
}
