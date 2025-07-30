package edu.ncsu.csc.CoffeeMaker.repositories;

import org.springframework.data.jpa.repository.JpaRepository;

import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;

/**
 * Interface that requires findByIngredient for an ingredient repository.
 *
 * @author Rithik Kulkarni
 */
public interface IngredientRepository extends JpaRepository<Ingredient, Long> {

    /**
     * Finds a Ingredient object with the provided name. Spring will generate
     * code to make this happen.
     *
     * @param ingredient
     *            the type of ingredient to find Name of the Ingredient
     * @return Found recipe, null if none.
     */
    Ingredient findByIngredient ( IngredientType ingredient );
}
