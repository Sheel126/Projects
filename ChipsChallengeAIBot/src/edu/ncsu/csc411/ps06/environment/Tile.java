package edu.ncsu.csc411.ps06.environment;

/**
 * A simple object representing the Tiles in the
 * environment. Their only purpose is to pass their
 * status or change into a CLEAN tile.
 * DO NOT MODIFY.
 */
public class Tile {
  private TileStatus status;

  public Tile(TileStatus status) {
    this.status = status;
  }

  public TileStatus getStatus() { return status; }

  @Override
  public String toString() {
    return "Tile [status=" + status + "]";
  }
}

