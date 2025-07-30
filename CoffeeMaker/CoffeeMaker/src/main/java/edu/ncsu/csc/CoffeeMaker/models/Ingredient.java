/**
 *
 */
package edu.ncsu.csc.CoffeeMaker.models;

import javax.persistence.Entity;
import javax.persistence.EnumType;
import javax.persistence.Enumerated;
import javax.persistence.GeneratedValue;
import javax.persistence.Id;
import javax.validation.constraints.PositiveOrZero;

import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;

/**
 * Models an ingredient to be used in coffee recipes.
 *
 * @author Rithik Kulkarni
 *
 */
@Entity
public class Ingredient extends DomainObject {

    /**
     * Id of an ingredient.
     */
    @Id
    @GeneratedValue
    private Long   id;

    /**
     * Enumerated type of ingredient.
     */
    @Enumerated ( EnumType.STRING )
    IngredientType ingredient;

    /**
     * Amount of initial units of this ingredient.
     */
    @PositiveOrZero
    Integer        amount;

    /**
     * Constructs an ingredient object
     *
     * @param ingredient
     *            type of ingredient
     * @param amount
     *            initial amount in inventory
     */
    public Ingredient ( final IngredientType ingredient, final Integer amount ) {
        super();
        this.amount = amount;
        this.ingredient = ingredient;
    }

    /**
     * Empty constructor for an Ingredient
     */
    public Ingredient () {

    }

    /**
     * Gets the ingredient as an ingredient type.
     *
     * @return the ingredient
     */
    public IngredientType getIngredient () {
        return ingredient;
    }

    /**
     * Sets an ingredient's type.
     *
     * @param ingredient
     *            the ingredient to set
     */
    public void setIngredient ( final IngredientType ingredient ) {
        this.ingredient = ingredient;
    }

    /**
     * Gets the amount of an ingredient.
     *
     * @return the amount
     */
    public int getAmount () {
        return amount;
    }

    /**
     * Sets the amount of an ingredient.
     *
     * @param amount
     *            the amount to set
     */
    public void setAmount ( final Integer amount ) {
        this.amount = amount;
    }

    @Override
    public Long getId () {
        return id;
    }

    /**
     * Set the ID of the Ingredient (Used by Hibernate).
     *
     * @param id
     *            the ID
     */
    @SuppressWarnings ( "unused" )
    private void setId ( final Long id ) {
        this.id = id;
    }

    @Override
    public String toString () {
        return "Ingredient [ingredient=" + ingredient + ", amount=" + amount + "]";
    }

}
