/**
 *
 */
package edu.ncsu.csc.CoffeeMaker.services;

import javax.transaction.Transactional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Component;

import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.repositories.IngredientRepository;

/**
 * IngredientService for interacting with ingredient instances.
 *
 * @author sheel
 *
 */
@Component
@Transactional
public class IngredientService extends Service<Ingredient, Long> {

    /**
     * Instance of ingredient repository being used.
     */
    @Autowired
    private IngredientRepository ingredientRepository;

    /**
     * Gets the ingredient repository being used.
     */
    @Override
    protected JpaRepository<Ingredient, Long> getRepository () {
        return ingredientRepository;
    }

    /**
     * Find a recipe with the provided name
     *
     * @param ingredient
     *            the ingredient type to get Name of the recipe to find
     * @return found recipe, null if none
     */
    public Ingredient getIngredientsByType ( final IngredientType ingredient ) {
        return ingredientRepository.findByIngredient( ingredient );
    }

}
