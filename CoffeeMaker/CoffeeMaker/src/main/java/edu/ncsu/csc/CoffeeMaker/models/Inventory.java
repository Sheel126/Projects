package edu.ncsu.csc.CoffeeMaker.models;

import java.util.ArrayList;
import java.util.List;

import javax.persistence.CascadeType;
import javax.persistence.Entity;
import javax.persistence.FetchType;
import javax.persistence.GeneratedValue;
import javax.persistence.Id;
import javax.persistence.OneToMany;

import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;

/**
 * Inventory for the coffee maker. Inventory is tied to the database using
 * Hibernate libraries. See InventoryRepository and InventoryService for the
 * other two pieces used for database support.
 *
 * @author Kai Presler-Marshall
 */
@Entity
public class Inventory extends DomainObject {

    /**
     * Id of inventory instance.
     */
    @Id
    @GeneratedValue
    private Long             id;

    /**
     * List of all current ingredients in the system.
     */
    @OneToMany ( cascade = CascadeType.ALL, fetch = FetchType.EAGER )
    private List<Ingredient> ingredients = new ArrayList<>();

    /**
     * Empty constructor for Hibernate
     */
    public Inventory () {
        // Intentionally empty so that Hibernate can instantiate
        // Inventory object.
    }

    /**
     * Constructs an inventory instance.
     *
     * @param coffee
     *            amount of initial coffee
     * @param milk
     *            amount of initial milk
     * @param sugar
     *            amount of initial sugar
     * @param chocolate
     *            amount of initial chocolate
     */
    public Inventory ( final Integer coffee, final Integer milk, final Integer sugar, final Integer chocolate ) {
        ingredients = new ArrayList<>();
        ingredients.add( new Ingredient( IngredientType.COFFEE, coffee ) );
        ingredients.add( new Ingredient( IngredientType.MILK, milk ) );
        ingredients.add( new Ingredient( IngredientType.SUGAR, sugar ) );
        ingredients.add( new Ingredient( IngredientType.CHOCOLATE, chocolate ) );
    }

    /**
     * Returns the ID of the entry in the DB
     *
     * @return long
     */
    @Override
    public Long getId () {
        return id;
    }

    /**
     * Gets the list of ingredients in the system.
     *
     * @return Ingredient list
     */
    public List<Ingredient> getIngredients () {
        return ingredients;
    }

    /**
     * Set the ID of the Inventory (Used by Hibernate)
     *
     * @param id
     *            the ID
     */
    public void setId ( final Long id ) {
        this.id = id;
    }

    /**
     * Returns true if there are enough ingredients to make the beverage.
     *
     * @param r
     *            recipe to check if there are enough ingredients
     * @return true if enough ingredients to make the beverage
     */
    public boolean enoughIngredients ( final Recipe r ) {
        final List<Ingredient> recipeIngredients = r.getIngredients();
        for ( final Ingredient recipeIngredient : recipeIngredients ) {
            for ( final Ingredient inventoryIngredient : ingredients ) {
                if ( recipeIngredient.getIngredient() == inventoryIngredient.getIngredient() ) {
                    if ( inventoryIngredient.getAmount() < recipeIngredient.getAmount() ) {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    /**
     * Removes the ingredients used to make the specified recipe. Assumes that
     * the user has checked that there are enough ingredients to make
     *
     * @param r
     *            recipe to make
     * @return true if recipe is made.
     */
    public boolean useIngredients ( final Recipe r ) {
        if ( enoughIngredients( r ) ) {
            final List<Ingredient> recipeIngredients = r.getIngredients();
            for ( final Ingredient recipeIngredient : recipeIngredients ) {
                for ( final Ingredient inventoryIngredient : ingredients ) {
                    if ( recipeIngredient.getIngredient() == inventoryIngredient.getIngredient() ) {
                        inventoryIngredient.setAmount( inventoryIngredient.getAmount() - recipeIngredient.getAmount() );
                    }
                }
            }
            return true;
        }
        return false;
    }

    /**
     * Adds ingredients to the system
     *
     * @param ingredient
     *            ingredient to add to system
     * @return true if ingredient successfully added, false otherwise
     */
    public boolean addIngredients ( final Ingredient ingredient ) {
        for ( final Ingredient existingIngredient : ingredients ) {
            if ( existingIngredient.getIngredient() == ingredient.getIngredient() ) {
                if ( existingIngredient.getAmount() < 0 ) {
                    throw new IllegalArgumentException();
                }
                existingIngredient.setAmount( existingIngredient.getAmount() + ingredient.getAmount() );
                return true;
            }
        }
        return ingredients.add( ingredient );
    }

    /**
     * Updates the values of each ingredient in the system.
     *
     * @param type
     *            the type of ingredient to update
     * @param amount
     *            the amount to update the ingredient by/to
     * @return true if successful, false otherwise
     */
    public boolean updateIngredientValues ( final IngredientType type, final int amount ) {
        for ( final Ingredient existingIngredient : ingredients ) {
            if ( existingIngredient.getIngredient() == type ) {
                if ( amount < 0 ) {
                    throw new IllegalArgumentException();
                }
                existingIngredient.setAmount( existingIngredient.getAmount() + amount );
                return true;
            }
        }
        return false;
    }

    /**
     * Resets an ingredient in the system
     *
     * @param type
     *            the type of ingredient to reset to
     * @return true if successful, false otherwise
     */
    public boolean resetIngredient ( final IngredientType type ) {
        for ( final Ingredient existingIngredient : ingredients ) {
            if ( existingIngredient.getIngredient() == type ) {
                existingIngredient.setAmount( 0 );
                return true;
            }
        }
        return false;
    }

    /**
     * Gets an ingredient from the system
     *
     * @param type
     *            the type of ingredient to get
     * @return the amount of the type of ingredient requested
     */
    public Ingredient getIngredient ( final IngredientType type ) {
        for ( final Ingredient existingIngredient : ingredients ) {
            if ( existingIngredient.getIngredient() == type ) {
                // existingIngredient.setAmount( existingIngredient.getAmount()
                // + ingredient.getAmount() );
                return existingIngredient;
            }
        }
        return null;
    }

    /**
     * Checks if an ingredient has a valid amount
     *
     * @param ingre
     *            ingredient to check
     * @return amount of ingredient checked
     * @throws IllegalArgumentException
     *             if units are invalid
     */
    public Integer checkIngredient ( final String ingre ) throws IllegalArgumentException {
        Integer amtIngredient = 0;
        try {
            amtIngredient = Integer.parseInt( ingre );
        }
        catch ( final NumberFormatException e ) {
            throw new IllegalArgumentException( "Units of ingredient must be a positive integer" );
        }
        if ( amtIngredient < 0 ) {
            throw new IllegalArgumentException( "Units of ingredient must be a positive integer" );
        }

        return amtIngredient;
    }

    /**
     * Returns a string describing the current contents of the inventory.
     *
     * @return String
     */
    @Override
    public String toString () {
        final StringBuilder buf = new StringBuilder();
        for ( final Ingredient ingredient : ingredients ) {
            buf.append( ingredient.toString() ).append( "\n" );
        }
        return buf.toString();
    }

}
