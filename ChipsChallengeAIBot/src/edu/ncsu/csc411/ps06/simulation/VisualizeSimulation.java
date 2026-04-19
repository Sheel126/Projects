package edu.ncsu.csc411.ps06.simulation;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Properties;
import java.util.TreeMap;

import javax.imageio.ImageIO;
import javax.swing.ImageIcon;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.Timer;

import edu.ncsu.csc411.ps06.agent.Robot;
import edu.ncsu.csc411.ps06.environment.Environment;
import edu.ncsu.csc411.ps06.environment.Position;
import edu.ncsu.csc411.ps06.environment.Tile;
import edu.ncsu.csc411.ps06.utils.ConfigurationLoader;
import edu.ncsu.csc411.ps06.utils.MapManager;

/**
 * A Visual Guide toward testing whether your robot
 * agent is operating correctly. This visualization
 * will run for 1000 time steps.
 * Feel free to modify the class variables to adjust simulation maps
 * and visual configurations.
 */
@SuppressWarnings("serial")
public class VisualizeSimulation extends JFrame {
	private EnvironmentPanel envPanel;
	private StatusPanel statusPanel;
	private Environment env;
	private String mapFile = "maps/public/map07.txt";
	private String configFile = "config/configSmall.txt";
	private Timer timer;
	
	/* Builds the environment; while not necessary for this problem set,
	 * this could be modified to allow for different types of environments,
	 * for example loading from a file, or creating multiple agents that
	 * can communicate/interact with each other.
	 * 
	 * The map variable allows you to customize the environment to any configuration.
	 * Each line in the list represents a row in the environment, and each character in
	 * a string represents a column. The Environment constructor that accepts a String list
	 * will review each character and set that tile's status to one of the following mappings.
	 */
	public VisualizeSimulation() {
		// Loads configurations from the config directory. If the configNormal file is too large
		// for your monitor's resolution, you can set configFile to configSmall.txt,
		// or configLarge.txt if you want to increase the screen size.
		Properties properties = ConfigurationLoader.loadConfiguration(configFile);
		int ITERATIONS = Integer.parseInt(properties.getProperty("ITERATIONS", "200"));
		int TILESIZE = Integer.parseInt(properties.getProperty("TILESIZE", "50"));
		int DELAY = Integer.parseInt(properties.getProperty("DELAY", "200"));
		boolean DEBUG = Boolean.parseBoolean(properties.getProperty("DEBUG", "true"));
		
		// Currently loads the first public test case, but you can change the map file
		// or make your own!
		String[][] map = MapManager.loadMap(mapFile);
		this.env = new Environment(map);
		envPanel = new EnvironmentPanel(this.env, ITERATIONS, TILESIZE, DELAY, DEBUG);
		statusPanel = new StatusPanel(this.env, TILESIZE);
		setLayout(new FlowLayout());
    	add(envPanel);
    	add(statusPanel);
    	
    	this.timer = new Timer(DELAY, new ActionListener() {
			int timeStepCount = 0;
			public void actionPerformed(ActionEvent e) {
				try {
					// Wrapped in try/catch in case the Robot's decision results
					// in a crash; we'll treat that the same as Action.DO_NOTHING
					env.updateEnvironment();
				} catch (Exception ex) {
					if (DEBUG) {
						String error = "[ERROR AGENT CRASH AT TIME STEP %03d] %s\n";
						System.out.printf(error, timeStepCount, ex);
					}
				}
				repaint();
				timeStepCount++;
				
				// 2) The simulation has iterated through the passed number of iterations
				if (timeStepCount == ITERATIONS) {
					timer.stop();
					env.printPerformanceMeasure();
				}
				if (env.goalConditionMet()) {
					timer.stop();
					env.printPerformanceMeasure();
				}
			}
		});
		this.timer.start();
	}
	
	public static void main(String[] args) {
	    JFrame frame = new VisualizeSimulation();

	    frame.setTitle("Chip's Challenge");
	    frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
	    frame.pack();
	    frame.setVisible(true);
	    frame.setResizable(false);
    }
}

@SuppressWarnings("serial")
class EnvironmentPanel extends JPanel{
	private Environment env;
	private ArrayList<Robot> robots;
	public static int TILESIZE;
	private static boolean DEBUG;
	
	// Designs a GUI Panel based on the dimensions of the Environment and implements 
	// a Timer object to run the simulation. This timer will iterate through time-steps
	// with a X ms delay (or wait X ms before updating again).
	public EnvironmentPanel(Environment env, int iterations, int tilesize, int delay, boolean debug) {
		TILESIZE = tilesize;	
	    setPreferredSize(new Dimension(env.getCols()*TILESIZE, env.getRows()*TILESIZE));
		this.env = env;
		this.robots = env.getRobots();
		EnvironmentPanel.DEBUG = debug;
	}
	
	/*
	 * The paintComponent method draws all of the objects onto the
	 * panel. This is updated at each time step when we call repaint().
	 */
	@Override
	protected void paintComponent(Graphics g) {
		super.paintComponent(g);
		// Paint Environment Tiles
		Map<Position, Tile> tiles = env.getTiles();
		for (Position pos : tiles.keySet()) {
			switch(tiles.get(pos).getStatus()) {
				case BLANK: 
					drawSprite("sprite/tile.png", g, pos);
					break;
				case CHIP:
					drawSprite("sprite/chip.png", g, pos);
					break;
				case WALL:
					drawSprite("sprite/wall.png", g, pos);
					break;
				case GOAL:
					drawSprite("sprite/goal.png", g, pos);
					break;
				case DOOR_GOAL:
					drawSprite("sprite/door_goal.png", g, pos);
					break;
				case DOOR_BLUE:
					drawSprite("sprite/door_blue.png", g, pos);
					break;
				case DOOR_GREEN:
					drawSprite("sprite/door_green.png", g, pos);
					break;
				case DOOR_RED:
					drawSprite("sprite/door_red.png", g, pos);
					break;
				case DOOR_YELLOW:
					drawSprite("sprite/door_yellow.png", g, pos);
					break;
				case KEY_BLUE:
					drawSprite("sprite/key_blue.png", g, pos);
					break;
				case KEY_GREEN:
					drawSprite("sprite/key_green.png", g, pos);
					break;
				case KEY_RED:
					drawSprite("sprite/key_red.png", g, pos);
					break;
				case KEY_YELLOW:
					drawSprite("sprite/key_yellow.png", g, pos);
					break;
				case WATER:
					drawSprite("sprite/water.png", g, pos);
					break;
				default:
					break;
			}
	    }
		// Paint Robot
		for(Robot robot : robots) {
			Position robotPos = env.getRobotPosition(robot);
			drawSprite("sprite/chip_forward.png", g, robotPos);
		}
	}
	
	private void drawSprite(String string, Graphics g, Position p) {
		Graphics2D g2 = (Graphics2D)g;
		BufferedImage sprite;
		try {
			sprite = ImageIO.read(new File(string));
			g2.drawImage(sprite, p.getCol() * TILESIZE, p.getRow() * TILESIZE, TILESIZE-1, TILESIZE-1, this);
		} catch (IOException e) {
			if (EnvironmentPanel.DEBUG) {
				String template = "An error has occurred while drawing %s at Position %s";
				String line = String.format(template, string, p);
				System.out.println(line);
				e.printStackTrace();
			}
		}
	}
}

@SuppressWarnings("serial")
class StatusPanel extends JPanel{
	private static int TILESIZE;
	private JPanel chipsPanel;
	private JPanel inventoryPanel;
	
	public StatusPanel(Environment env, int tilesize) {
		TILESIZE = tilesize;
		setPreferredSize(new Dimension(4*TILESIZE, 4*TILESIZE));
		setLayout(new BorderLayout());
		this.chipsPanel = new ChipsPanel(env);
		this.inventoryPanel = new InventoryPanel(env);
		
		JPanel p = new JPanel(new BorderLayout());
		p.add(chipsPanel, BorderLayout.NORTH);
		p.add(inventoryPanel, BorderLayout.SOUTH);
		add(p, BorderLayout.CENTER);
//		setBorder(BorderFactory.createLineBorder(ColorPalette.BLACK));
	}
	
	@Override
	protected void paintComponent(Graphics g) {
		super.paintComponent(g);
	}
}

@SuppressWarnings("serial")
class ChipsPanel extends JPanel{
	private Environment env;
	private JLabel header;
	private JLabel number;
	
	public ChipsPanel(Environment env) {
		this.env = env;
		
		this.header = new JLabel("Chips Remaining");
		this.header.setHorizontalAlignment(JLabel.CENTER);
		this.number = new JLabel(this.env.getNumRemainingChips()+"");
		this.number.setHorizontalAlignment(JLabel.CENTER);
		
		setLayout(new BorderLayout());
		add(header, BorderLayout.NORTH);
		add(number, BorderLayout.SOUTH);
	}
	
	@Override
	protected void paintComponent(Graphics g) {
		super.paintComponent(g);
		this.number.setText(this.env.getNumRemainingChips()+"");
	}
}

@SuppressWarnings("serial")
class InventoryPanel extends JPanel {
	private Environment env;
	private ArrayList<Robot> robots;
	private Map<String, Boolean> itemStatus;
	private JLabel[] icons;
	private ImageIcon[] keyIcons;
	
	public InventoryPanel(Environment env) {
		this.env = env;
		setLayout(new FlowLayout(FlowLayout.CENTER, 0, 0));
		this.robots = env.getRobots();
		this.itemStatus = new TreeMap<String, Boolean>();
		this.itemStatus.put("KEY_BLUE", false);
		this.itemStatus.put("KEY_GREEN", false);
		this.itemStatus.put("KEY_RED", false);
		this.itemStatus.put("KEY_YELLOW", false);
		this.icons = new JLabel[4];
		for(int i = 0; i < icons.length; i++) {
			icons[i] = new JLabel(new ImageIcon("sprite/tile.png"));
			add(icons[i]);
		}
		this.keyIcons = new ImageIcon[5];
		this.keyIcons[0] = new ImageIcon("sprite/tile.png");
		this.keyIcons[1] = new ImageIcon("sprite/key_blue.png");
		this.keyIcons[2] = new ImageIcon("sprite/key_green.png");
		this.keyIcons[3] = new ImageIcon("sprite/key_red.png");
		this.keyIcons[4] = new ImageIcon("sprite/key_yellow.png");
	}
	
	public void updateHoldings() {
		for(Robot robot : robots) {
			ArrayList<String> inventory = env.getRobotHoldings(robot);
			for(Entry<String, Boolean> entry : this.itemStatus.entrySet()) {
				String key = entry.getKey();
				if (inventory.contains(key)) {
					this.itemStatus.put(key, true);
				} else {
					this.itemStatus.put(key, false);
				}
			}
		}
	}
	
	/*
	 * The paintComponent method draws all of the objects onto the
	 * panel. This is updated at each time step when we call repaint().
	 */
	@Override
	protected void paintComponent(Graphics g) {
		super.paintComponent(g);
		// Update what items the agent is carrying
		updateHoldings();
		
		// Paint Item Tiles
		for(Robot robot : robots) {
			ArrayList<String> inventory = env.getRobotHoldings(robot);
			int count = 0;
			for(Entry<String, Boolean> entry : this.itemStatus.entrySet()) {
				String key = entry.getKey();
				if (inventory.contains(key)) {
					icons[count].setIcon(keyIcons[count+1]);
				} else {
					icons[count].setIcon(keyIcons[0]);
				}
				count++;
			}
		}
	}
}